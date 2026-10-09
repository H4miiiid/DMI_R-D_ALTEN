"""Offline regular/selective comparison using identical controlled recordings."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import cv2

from dmi_robot_master.integration.camera import ReplayCamera
from dmi_robot_master.integration.observe import observe
from dmi_robot_master.integration.processing_policy import DetectionPolicy
from dmi_robot_master.integration.publication import project_pixels
from dmi_computer_vision.src.dmi.evaluation.validation import validate_results
from dmi_computer_vision.src.dmi.evaluation.compact import validate_compact

ROOT = Path(__file__).resolve().parents[2]
VIDEO_ROOT = ROOT / 'dmi_computer_vision/data/videos/dev'


def read_frame(path: Path, index: int):
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise RuntimeError(f'Cannot open recording {path}')
        for _ in range(index + 1):
            ok, image = capture.read()
            if not ok:
                raise RuntimeError('Recording ended before selected frame')
        return image
    finally:
        capture.release()


class ScheduledCapture:
    """Repeat decoded BGR frames without another lossy encoding pass."""
    def __init__(self, phases):
        self.phases = phases
        self.index = 0

    def isOpened(self):
        return True

    def get(self, prop):
        return 30.0

    def release(self):
        pass

    def read(self):
        remaining = self.index
        for state, duration, image in self.phases:
            if remaining < duration * 30:
                self.index += 1
                return True, image.copy()
            remaining -= duration * 30
        return False, None


class ScheduledReplay(ReplayCamera):
    def __init__(self, manifest, phases):
        super().__init__(manifest)
        self.phases = phases

    def _open_capture(self):
        return ScheduledCapture(self.phases)


def create_fixture(path: Path):
    """Four fixed decoded images; producer still has one latest pending slot."""
    driver = read_frame(VIDEO_ROOT / 'driver_id_12.mp4', 73)
    main = read_frame(VIDEO_ROOT / 'level_to_main.mp4', 630)
    phases = [('Driver ID', 8, driver), ('Main', 7, main),
              ('unknown', 2, driver * 0), ('Driver ID', 6, driver)]
    schedule, seconds = [], 0
    for state, duration, image in phases:
        schedule.append({'expected_screen': state, 'start_video_seconds': seconds,
                         'duration_seconds': duration})
        seconds += duration
    path.write_text(json.dumps({'simulation': True, 'schedule': schedule, 'fps': 30,
                               'driver_source': 'driver_id_12.mp4 frame 73',
                               'main_source': 'level_to_main.mp4 frame 630'}, indent=2)+'\n')
    return schedule, phases


def summarize(directory: Path, schedule: list[dict]) -> dict:
    records = [json.loads(line) for line in (directory / 'results_debug.jsonl').read_text().splitlines()]
    frames = [record['result'] for record in records]
    session = json.loads((directory / 'session.json').read_text())
    events = [json.loads(line) for line in (directory / 'publication_review.jsonl').read_text().splitlines()]
    contract = validate_results(frames, None)
    compact = validate_compact(directory / 'results.jsonl', frames)
    delays = []
    for phase in schedule:
        start = phase['start_video_seconds']
        matches = [r for r in records if start <= r['source_video_seconds'] < start + phase['duration_seconds']
                   and r['result']['right_display']['state'] == phase['expected_screen']]
        delays.append({**phase, 'first_recognition_delay_seconds':
                       matches[0]['source_video_seconds'] - start if matches else None,
                       'first_result_delay_upper_seconds':
                       matches[0]['source_video_seconds'] - start + matches[0]['receipt_to_result_seconds'] if matches else None})
    return {'run': session['run'], 'policy': session['policy'], 'contract': contract,
            'compact': compact, 'recognition': delays,
            'max_measured_recognition_delay_seconds': max((p['first_recognition_delay_seconds'] for p in delays
                                                          if p['first_recognition_delay_seconds'] is not None), default=None),
            'screens': dict(Counter(f['right_display']['state'] for f in frames)),
            'target_updates': sum(e['type'] == 'targets' for e in events),
            'unsuppressed_projection_updates': len(records),
            'unsuppressed_projection_bytes': sum(len(json.dumps(project_pixels(r['result'],
                frame_size=tuple(r['frame_size'])), separators=(',', ':')).encode())+1 for r in records),
            'target_update_bytes': sum(len(json.dumps(e, separators=(',', ':')).encode())+1
                                       for e in events if e['type'] == 'targets'),
            'heartbeat_bytes': sum(len(json.dumps(e, separators=(',', ':')).encode())+1
                                   for e in events if e['type'] == 'status'),
            'compact_bytes': (directory / 'results.jsonl').stat().st_size,
            'annotation_bytes': (directory / 'annotated.mp4').stat().st_size if (directory / 'annotated.mp4').exists() else 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    fixture = directory / 'controlled_replay.json'
    schedule, phases = create_fixture(fixture)
    reports = {}
    for mode in ('regular', 'selective'):
        policy = DetectionPolicy() if mode == 'selective' else None
        observe(ScheduledReplay(fixture, phases), directory / mode,
                source_info={'kind': 'recorded_replay', 'simulation': True, 'path': str(fixture)},
                processing_policy=policy, annotations=mode == 'regular', publication=True, debug=True)
        reports[mode] = summarize(directory / mode, schedule)
    reports['limits'] = ('Repeated original decoded BGR frames with controlled transitions; serial trials on local PC. '
                        'Recognition delays are measured in source video seconds; no physical camera/action evidence.')
    (directory / 'comparison.json').write_text(json.dumps(reports, indent=2, default=str)+'\n')
    print(json.dumps(reports, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
