"""Observation-only monitor validation with measured receipt-time replay.

The source is always ReplayCamera with a bounded pending slot. Controlled image
changes are explicitly simulation, not evidence of physical UI input or footage
of an otherwise unsupported connected screen. No motor transport is imported.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import json
import math
from pathlib import Path
import platform
import time
from unittest.mock import patch

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.display_geometry import detect_displays, rectify_display
from dmi_computer_vision.src.dmi.detection.right_display import _detect_data_field, RECTIFIED_SIZE
from dmi_computer_vision.src.dmi.detection import title_ocr
from dmi_computer_vision.src.dmi.evaluation.compact import validate_compact
from dmi_computer_vision.src.dmi.evaluation.validation import validate_results
from dmi_computer_vision.src.dmi.pipeline import frame_processor
from dmi_robot_master.integration.camera import ReplayCamera
from dmi_robot_master.integration.observe import observe, AnnotationSink
from dmi_robot_master.integration.processing_policy import DetectionPolicy
from dmi_robot_master.integration.targets import atomic_json

ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / 'dmi_computer_vision'


def stats(values) -> dict:
    values = list(values)
    return {'count': len(values), 'mean': float(np.mean(values)),
            'p95': float(np.percentile(values, 95)), 'max': float(max(values))} if values else {}


def remove_source_hud(image: np.ndarray) -> np.ndarray:
    """Exclude known old annotations outside the monitor from change checks."""
    copy = image.copy()
    copy[:129, :961] = 0
    return copy


def map_right_change(image: np.ndarray, change) -> np.ndarray:
    """Map an evaluation-only rectified edit back to unchanged native pixels."""
    geometry = detect_displays(image)['right']
    if geometry is None:
        raise ValueError('Fixture requires independently detected right geometry')
    rectified = rectify_display(image, geometry, RECTIFIED_SIZE)
    changed, mask = change(rectified)
    width, height = RECTIFIED_SIZE
    source = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    inverse = cv2.getPerspectiveTransform(source, geometry.corners)
    size = image.shape[1::-1]
    mapped = cv2.warpPerspective(changed, inverse, size)
    selected = cv2.warpPerspective(mask, inverse, size, flags=cv2.INTER_NEAREST) > 0
    result = image.copy()
    result[selected] = mapped[selected]
    return result


def changed_field(image: np.ndarray, text: str = '47') -> np.ndarray:
    """Synthetic same-title value; letters are drawn, never supplied to OCR."""
    def change(rectified):
        field = _detect_data_field(rectified)
        if field is None:
            raise ValueError('Fixture has no measured field')
        x1, y1, x2, y2 = field[0]
        inset = max(5, round((y2 - y1) * .1))
        x1, y1, x2, y2 = x1 + inset, y1 + inset, x2 - inset, y2 - inset
        changed = rectified.copy()
        background = np.median(rectified[y1:y2, (x1 + x2) // 2:x2], axis=(0, 1))
        changed[y1:y2, x1:x2] = background
        cv2.putText(changed, text, (x1 + 7, y1 + round((y2 - y1) * .7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (70, 40, 10), 2, cv2.LINE_AA)
        mask = np.zeros(rectified.shape[:2], np.uint8)
        mask[y1:y2, x1:x2] = 255
        return changed, mask
    return map_right_change(image, change)


def without_action_border(image: np.ndarray) -> np.ndarray:
    """Erase the measured cancel cell, a synthetic same-title control loss."""
    geometry = detect_displays(image)['right']
    if geometry is None:
        raise ValueError('Fixture requires right geometry')
    direct = frame_processor.FrameProcessor().process(image, 0.)['right_display']
    action = direct['buttons'].get('cancel')
    if action is None:
        raise ValueError('Fixture requires a visible cancel control')
    width, height = RECTIFIED_SIZE
    to_rectified = cv2.getPerspectiveTransform(geometry.corners,
        np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]))
    points = cv2.perspectiveTransform(np.float32([action['corners']]), to_rectified)[0]
    def change(rectified):
        mask = np.zeros(rectified.shape[:2], np.uint8)
        x2 = min(width - 2, math.ceil(float(points[:, 0].max())) + 30)
        y1 = min(height - 1, math.floor(float(points[:, 1].min())) + 5)
        y2 = min(height - 1, math.ceil(float(points[:, 1].max())) + 20)
        # Keep the shared keypad bottom row and monitor outer edge. Place the
        # edit's right seam outside the action-edge search, avoiding a fake edge.
        changed = rectified.copy()
        for y in range(y1, y2):
            background = np.median(rectified[max(0, y - 2):y + 3,
                                             min(width - 20, x2 + 15):min(width - 2, x2 + 45)], axis=(0, 1))
            changed[y, 3:x2] = background
        mask[y1:y2, 3:x2] = 255
        return changed, mask
    return map_right_change(image, change)


def only_region(image: np.ndarray, side: str, *, separated: bool) -> np.ndarray:
    geometry = detect_displays(image)[side]
    if geometry is None:
        raise ValueError('Fixture requires a full measured region')
    points = geometry.corners
    if separated:
        points = cv2.convexHull(np.vstack((points, geometry.oriented_box)))
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.rint(points).astype(np.int32), 255)
    if separated:
        mask = cv2.dilate(mask, np.ones((61, 61), np.uint8))
    return cv2.bitwise_and(image, image, mask=mask)


def controlled_phases(arrangement: str) -> tuple[list[dict], dict[str, np.ndarray]]:
    if arrangement == 'connected':
        directory = VISION / 'data/videos/dev'
        driver = cv2.imread(str(directory / 'dmi_capture_quality_02/last_annotated.png'))
        main = cv2.imread(str(directory / 'dmi_capture_quality_01/last_annotated.png'))
        initial = '23'
    else:
        directory = VISION / 'outputs/monitor_support/step1_20261015_run01/separated'
        driver = cv2.imread(str(directory / 'driver_id_12/accepted_0112_raw.png'))
        main = cv2.imread(str(directory / 'level_to_main/accepted_0698_raw.png'))
        initial = '12'
    if driver is None or main is None:
        raise ValueError('Required reviewed source images are unavailable')
    driver, main = remove_source_hud(driver), remove_source_hud(main)
    field = changed_field(driver)
    occluded = driver.copy()
    quad = detect_displays(driver)['right'].corners
    center = quad.mean(axis=0)
    intrusion = np.rint(center + (quad - center) * .65).astype(np.int32)
    cv2.fillConvexPoly(occluded, intrusion, (25, 50, 95))
    images = {'driver': driver, 'field': field, 'button': without_action_border(field),
              'main': main, 'left_only': only_region(driver, 'left', separated=arrangement == 'separated'),
              'occluded': occluded, 'blank': driver * 0}
    spec = [('driver', 5., 'Driver ID', initial), ('field', 7., 'Driver ID', '47'),
            ('button', 3., 'Driver ID', '47'), ('main', 4., 'Main', None),
            ('driver', .1, 'Driver ID', initial), ('main', 2., 'Main', None),
            ('left_only', 1., 'unknown', None), ('occluded', 1., 'unknown', None),
            ('blank', 1., 'unknown', None), ('driver', 3., 'Driver ID', initial)]
    phases, start = [], 0.
    for index, (key, seconds, state, value) in enumerate(spec):
        phases.append({'phase': index, 'image': key, 'start_seconds': start, 'duration_seconds': seconds,
                       'expected_state': state, 'expected_value': value,
                       'expect_cancel_loss': key == 'button', 'synthetic': key not in ('driver', 'main')})
        start += seconds
    return phases, images


class TimelineCapture:
    """Evaluation fixture pacing; receipt times remain actual local clock reads."""
    def __init__(self, phases: list[dict], images: dict, stop, *, fps: float = 30.) -> None:
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('Fixture FPS must be finite and positive')
        self.phases, self.images, self.stop, self.fps = phases, images, stop, fps
        self.index, self.started = 0, None
        self.arrivals: list[dict] = []
        self.total = round(sum(p['duration_seconds'] for p in phases) * fps)

    def isOpened(self):
        return True

    def get(self, prop):
        return self.fps

    def read(self):
        if self.index >= self.total:
            return False, None
        if self.started is None:
            self.started = time.monotonic()
        elapsed = self.index / self.fps
        if self.stop.wait(max(0., self.started + elapsed - time.monotonic())):
            return False, None
        phase = next(p for p in reversed(self.phases) if elapsed >= p['start_seconds'] - 1e-9)
        image = self.images[phase['image']].copy()
        self.arrivals.append({'capture_index': self.index, 'available_at': time.monotonic(),
                              'source_seconds': elapsed, 'phase': phase['phase']})
        self.index += 1
        return True, image

    def release(self):
        pass


class ReceiptCapture:
    """Replay saved annotations at sidecar receipt offsets, never MP4 5 FPS."""
    def __init__(self, directory: Path, stop) -> None:
        metadata = [json.loads(s) for s in (directory / 'processed_frames.jsonl').read_text().splitlines()]
        receipts = [r['received_at_monotonic'] for r in metadata]
        if (not receipts or any(not math.isfinite(v) for v in receipts)
                or any(b <= a for a, b in zip(receipts, receipts[1:]))):
            raise ValueError('Sidecar receipts must be finite and increasing')
        self.offsets = [value - receipts[0] for value in receipts]
        self.capture = cv2.VideoCapture(str(directory / 'annotated.mp4'))
        self.stop, self.index, self.started = stop, 0, None
        self.arrivals: list[dict] = []

    def isOpened(self):
        return self.capture.isOpened()

    def get(self, prop):
        return self.capture.get(prop)

    def read(self):
        if self.index == len(self.offsets):
            if self.capture.read()[0]:
                raise ValueError('More video frames than sidecar receipts')
            return False, None
        if self.started is None:
            self.started = time.monotonic()
        elapsed = self.offsets[self.index]
        if self.stop.wait(max(0., self.started + elapsed - time.monotonic())):
            return False, None
        ok, image = self.capture.read()
        if not ok:
            raise ValueError('Video ended before sidecar receipts')
        image = remove_source_hud(image)
        self.arrivals.append({'capture_index': self.index, 'available_at': time.monotonic(),
                              'source_seconds': elapsed, 'phase': 0})
        self.index += 1
        return True, image

    def release(self):
        self.capture.release()


class MonitorReplay(ReplayCamera):
    def __init__(self, manifest: Path, *, phases=None, images=None, recording=None) -> None:
        # The fixture owns absolute receipt pacing. The base adapter's minimum
        # loop wait is not a camera FPS request; the actual producer is measured.
        super().__init__(manifest, replay_fps=1000)
        self.phases, self.images, self.recording = phases, images, recording
        self.fixture = None

    def _open_capture(self):
        self.fixture = (ReceiptCapture(self.recording, self._stop) if self.recording is not None
                        else TimelineCapture(self.phases, self.images, self._stop))
        return self.fixture


class Measurements:
    """Optional evaluation telemetry; no detector output/evidence is substituted."""
    def __init__(self, stream, *, preview: bool) -> None:
        self.stream, self.preview = stream, preview
        self.rows, self.preview_events = [], []
        self.ocr_times = []
        self.stages = Counter()
        self.encoding_seconds = []
        self.preview_kind, self.preview_receipt = None, None

    def show(self, image):
        if self.preview and self.preview_receipt is not None:
            now = time.monotonic()
            self.preview_events.append({'kind': self.preview_kind, 'at': now,
                                       'age_seconds': now - self.preview_receipt,
                                       'evidence_received_at': self.preview_receipt})
        return True  # headless preview consumer, not a GUI paint measurement

    def __enter__(self):
        self.stack = ExitStack()
        process = frame_processor.FrameProcessor.process
        recognize = title_ocr._recognize_words
        show, idle = AnnotationSink.show, AnnotationSink.idle
        def measured_stage(name, function):
            def measured(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return function(*args, **kwargs)
                finally:
                    self.stages[name] += time.perf_counter() - start
            return measured
        def timed_ocr(*args, **kwargs):
            start = time.perf_counter()
            try:
                return recognize(*args, **kwargs)
            finally:
                self.ocr_times.append(time.perf_counter() - start)
        def timed_process(processor, image, timestamp):
            self.ocr_times.clear()
            self.stages.clear()
            start = time.perf_counter()
            result = process(processor, image, timestamp)
            row = {'frame_index': result['frame_index'], 'timestamp': timestamp,
                   'analysis_seconds': time.perf_counter() - start,
                   'ocr_calls': len(self.ocr_times), 'ocr_seconds': sum(self.ocr_times),
                   'stages_seconds': dict(self.stages),
                   'direct': dict(processor.target_evidence), 'reset': processor.last_reset_reason}
            self.rows.append(row)
            self.stream.write(json.dumps(row, allow_nan=False) + '\n')
            return result
        def fresh(sink, image):
            if self.preview:
                self.preview_kind = 'fresh'
                self.preview_receipt = sink.source.last_packet.received_at
            start = time.perf_counter()
            try:
                return show(sink, image)
            finally:
                self.encoding_seconds.append(time.perf_counter() - start)
        def reused(sink):
            if self.preview and sink.last_received is not None:
                self.preview_kind = 'reused'
                self.preview_receipt = sink.last_received
            return idle(sink)
        self.stack.enter_context(patch.object(title_ocr, '_recognize_words', side_effect=timed_ocr))
        for name in ('detect_displays', 'analyze_train_left_display', 'analyze_left_display',
                     'analyze_right_display', 'rectify_display'):
            self.stack.enter_context(patch.object(frame_processor, name,
                measured_stage(name, getattr(frame_processor, name))))
        self.stack.enter_context(patch.object(frame_processor.FrameProcessor, 'process', timed_process))
        self.stack.enter_context(patch.object(AnnotationSink, 'show', fresh))
        self.stack.enter_context(patch.object(AnnotationSink, 'idle', reused))
        return self

    def __exit__(self, *args):
        self.stack.close()


def summarize(directory: Path, telemetry: Measurements, source: MonitorReplay, phases: list[dict]) -> dict:
    envelopes = [json.loads(s) for s in (directory / 'results_debug.jsonl').read_text().splitlines()]
    frames = [r['result'] for r in envelopes]
    session = json.loads((directory / 'session.json').read_text())
    arrivals = source.fixture.arrivals
    if len(envelopes) != len(telemetry.rows):
        raise ValueError('Every detected frame must have one telemetry record')
    by_capture = {r['capture_index']: r for r in arrivals}
    delays = []
    for phase in phases:
        actual = [r for r in arrivals if r['phase'] == phase['phase']]
        consumed = [(e, t) for e, t in zip(envelopes, telemetry.rows)
                    if by_capture[e['capture_index']]['phase'] == phase['phase']]
        def first_delay(predicate):
            match = next((e for e, t in consumed if predicate(e['result'], t['direct'])), None)
            return (match['received_at_monotonic'] + match['receipt_to_result_seconds'] - actual[0]['available_at']
                    if match is not None and actual else None)
        delays.append({**phase, 'captured': len(actual), 'detections': len(consumed),
                       'direct_state_delay_seconds': first_delay(lambda r, d: d['right_state'] == phase['expected_state']),
                       'confirmed_state_delay_seconds': first_delay(lambda r, d: r['right_display']['state'] == phase['expected_state']),
                       'direct_value_delay_seconds': (first_delay(lambda r, d: d['right_state'] == phase['expected_state']
                            and d['right_field_value'] == phase['expected_value']) if phase['expected_value'] is not None else None),
                       'confirmed_value_delay_seconds': (first_delay(lambda r, d: r['right_display']['state'] == phase['expected_state']
                            and (r['right_display']['data_field'] or {}).get('value') == phase['expected_value'])
                            if phase['expected_value'] is not None else None),
                       'cancel_loss_delay_seconds': (first_delay(lambda r, d: d['right_state'] == 'Driver ID'
                            and 'cancel' not in d['right_buttons']) if phase.get('expect_cancel_loss') else None)})
    seconds = session['elapsed_seconds']
    report = {'session': session, 'contract': validate_results(frames, None),
              'compact': validate_compact(directory / 'results.jsonl', frames), 'phases': delays,
              'analysis_seconds': stats(r['analysis_seconds'] for r in telemetry.rows),
              'ocr_calls': sum(r['ocr_calls'] for r in telemetry.rows),
              'ocr_seconds': sum(r['ocr_seconds'] for r in telemetry.rows),
              'stages_seconds': {name: stats(r['stages_seconds'].get(name, 0.) for r in telemetry.rows)
                                for name in sorted({key for r in telemetry.rows for key in r['stages_seconds']})},
              'encode_sink_seconds': stats(telemetry.encoding_seconds),
              'receipt_to_result_seconds': stats(r['receipt_to_result_seconds'] for r in envelopes),
              'producer_fps': (len(arrivals) - 1) / (arrivals[-1]['available_at'] - arrivals[0]['available_at']) if len(arrivals) > 1 else None,
              'states': dict(Counter(r['right_display']['state'] for r in frames)),
              'resets': dict(Counter(r['temporal_reset'] for r in envelopes)),
              'preview': {'kind': 'headless callbacks, not GUI paints', 'updates': len(telemetry.preview_events),
                          'updates_per_second': len(telemetry.preview_events) / seconds,
                          'reused_age_seconds': stats(r['age_seconds'] for r in telemetry.preview_events if r['kind'] == 'reused')},
              'output_bytes': {p.name: p.stat().st_size for p in directory.iterdir() if p.is_file()},
              'final_targets_cleared': not json.loads((directory / 'targets.json').read_text())['targets'],
              'limits': 'Local receipt replay; no sensor/network timing, physical calibration or robot motion.'}
    if (directory / 'annotated.mp4').exists():
        capture = cv2.VideoCapture(str(directory / 'annotated.mp4'))
        count = 0
        while capture.read()[0]:
            count += 1
        capture.release()
        if count != len(frames):
            raise ValueError('Annotation video count differs')
        report['decoded_annotations'] = count
    atomic_json(directory / 'source_arrivals.json', {'frames': arrivals})
    atomic_json(directory / 'preview_events.json', {'events': telemetry.preview_events})
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--arrangement', choices=('connected', 'separated'), default='connected')
    parser.add_argument('--recording', type=Path, help='Saved connected session with MP4 and receipt sidecar')
    parser.add_argument('--processing', choices=('regular', 'selective'), default='regular')
    parser.add_argument('--refresh-seconds', type=float, default=.4)
    parser.add_argument('--burst-seconds', type=float, default=3.)
    parser.add_argument('--annotations', action='store_true', help='Equal setting for matched comparisons; includes headless preview')
    args = parser.parse_args(argv)
    directory = args.output_dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    phases, images = (controlled_phases(args.arrangement) if args.recording is None else ([], {}))
    manifest = directory / 'fixture.simulation.json'
    atomic_json(manifest, {'simulation': True, 'arrangement': args.arrangement,
                          'recording': str(args.recording) if args.recording else None,
                          'phases': phases, 'source_hud_mask': [0, 0, 961, 129],
                          'environment': {'python': platform.python_version(), 'opencv': cv2.__version__,
                                          'numpy': np.__version__, 'platform': platform.platform()}})
    for name, image in images.items():
        if not cv2.imwrite(str(directory / f'fixture_{name}.png'), image):
            raise RuntimeError(f'Cannot write fixture image: {name}')
    source = MonitorReplay(manifest, phases=phases, images=images, recording=args.recording)
    policy = (DetectionPolicy(refresh_seconds=args.refresh_seconds, burst_seconds=args.burst_seconds)
              if args.processing == 'selective' else None)
    with (directory / 'telemetry.jsonl').open('x') as stream, Measurements(stream, preview=args.annotations) as telemetry:
        run_dir = directory / 'session'
        observe(source, run_dir, source_info={'kind': 'recorded_replay', 'simulation': True, 'path': str(manifest)},
                processing_policy=policy, annotations=args.annotations, preview=telemetry if args.annotations else None,
                export_targets=True, target_history=True, debug=True)
    report = summarize(run_dir, telemetry, source, phases)
    atomic_json(directory / 'summary.json', report)
    print(json.dumps({k: report[k] for k in ('analysis_seconds', 'ocr_calls', 'producer_fps', 'phases')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
