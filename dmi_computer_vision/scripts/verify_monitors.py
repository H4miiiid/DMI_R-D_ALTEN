"""Sequential offline monitor regression; recordings are read-only evidence.

Use a new output directory. Saved connected captures already contain annotations;
their receipt sidecars, rather than MP4 playback FPS, supply detector timestamps.
Accuracy still requires reviewed image references, separately from JSON validity.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dmi_computer_vision.src.dmi.detection import title_ocr
from dmi_computer_vision.src.dmi.evaluation.baseline import read_recorded_frames
from dmi_computer_vision.src.dmi.evaluation.compact import validate_compact
from dmi_computer_vision.src.dmi.evaluation.validation import validate_results
from dmi_computer_vision.src.dmi.output.annotation import annotate_frame
from dmi_computer_vision.src.dmi.output.json_writer import CompactWriter
from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor

VISION = ROOT / 'dmi_computer_vision'
VIDEOS = VISION / 'data/videos/dev'
BASELINES = {
    'driver_id_12': 'phase7_performance/review',
    'driverID_to_level': 'phase8_validation/recorded',
    'level_to_main': 'phase8_validation/recorded',
    'train_numbers': 'phase7_performance/review',
    'train_data_gamma': 'phase7_performance/review',
    'validate_train_data': 'phase7_performance/review',
}


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def distribution(values: list[float]) -> dict:
    return {'count': len(values), 'mean': float(np.mean(values)),
            'p95': float(np.percentile(values, 95)), 'max': max(values)} if values else {}


def differences(old, new, path='') -> set[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        result = {path + '.keys'} if old.keys() != new.keys() else set()
        for key in old.keys() & new.keys():
            result.update(differences(old[key], new[key], path + '.' + key))
        return result
    return {path} if old != new else set()


def value_counts(values: list[str | None], expected: str) -> dict:
    return {'correct': values.count(expected), 'unknown': values.count(None),
            'incorrect': sum(v not in (None, expected) for v in values),
            'incorrect_indices': [i for i, v in enumerate(values) if v not in (None, expected)]}


def verify_clip(name: str, directory: Path, *, connected: bool, annotations: bool) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    source = VIDEOS / name / 'annotated.mp4' if connected else VIDEOS / (name + '.mp4')
    metadata = ([json.loads(s) for s in (source.parent / 'processed_frames.jsonl').read_text().splitlines()]
                if connected else None)
    accepted = (json.loads((VISION / 'outputs/monitor_support/step4_20261019_review02' / name / 'results_full.json').read_text())
                if connected else read_recorded_frames(VISION / 'outputs/Version 2' / BASELINES[name] / name / 'results_debug.jsonl'))
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f'Cannot decode {source}')
    fps = capture.get(cv2.CAP_PROP_FPS)
    total = len(metadata) if metadata is not None else len(accepted)
    selected = {0, total // 2, total - 1}
    processor = FrameProcessor(max_gap_seconds=1 if connected else None, collect_target_evidence=True)
    frames, raw_values, stable_values, measurements = [], [], [], []
    deltas, paths, jitter = [], Counter(), defaultdict(list)
    writer = None
    ocr_times: list[float] = []
    recognize = title_ocr._recognize

    def timed_ocr(*args, **kwargs):
        started = time.perf_counter()
        try:
            return recognize(*args, **kwargs)
        finally:
            ocr_times.append(time.perf_counter() - started)

    try:
        with (directory / 'results.jsonl').open('x') as compact_stream, \
                (directory / 'results_debug.jsonl').open('x') as debug, \
                patch.object(title_ocr, '_recognize', side_effect=timed_ocr):
            compact = CompactWriter(compact_stream, {'simulation': True, 'source': str(source),
                'timestamp_basis': 'sidecar_receipt' if connected else 'source_frame/fps'})
            while True:
                started = time.perf_counter()
                ok, image = capture.read()
                decode_seconds = time.perf_counter() - started
                if not ok:
                    break
                index = len(frames)
                if index >= total:
                    raise ValueError('Video contains more frames than its evidence metadata')
                timestamp = (metadata[index]['received_at_monotonic'] - metadata[0]['received_at_monotonic']
                             if metadata else index / fps)
                ocr_times.clear()
                started = time.perf_counter()
                result = processor.process(image, timestamp)
                analysis_seconds = time.perf_counter() - started
                direct = dict(processor.target_evidence)
                prior = frames[-1] if frames else None
                if prior is not None:
                    for side, collection in (('right_display', 'buttons'), ('left_display', 'boxes')):
                        if side == 'right_display' and prior[side]['state'] != result[side]['state']:
                            continue
                        for label, region in result[side][collection].items():
                            old = prior[side][collection].get(label)
                            if old:
                                jitter[side + '/' + label].append(float(np.linalg.norm(
                                    np.array(old['center']) - region['center'])))
                frames.append(result)
                raw_values.append(direct['right_field_value'])
                stable_values.append((result['right_display']['data_field'] or {}).get('value'))
                changed = differences(accepted[index], result)
                if changed:
                    deltas.append(index)
                    paths.update(changed)
                compact.process(result, force_snapshot=processor.last_reset_reason is not None)
                annotation_seconds = encoding_seconds = 0.
                if annotations or index in selected or (changed and len(deltas) <= 8):
                    started = time.perf_counter()
                    preview = image.copy()
                    if connected:
                        cv2.rectangle(preview, (0, 0), (image.shape[1] - 1, 225), (0, 0, 0), -1)
                    preview = annotate_frame(preview, result)
                    cv2.putText(preview, f'STEP 5 | saved-image simulation | {name} | frame {index} | {timestamp:.3f}s',
                                (15, 155), 0, .8, (255, 255, 255), 2)
                    cv2.putText(preview, f'Direct field: {raw_values[-1]} | Stabilized field: {stable_values[-1]}',
                                (15, 200), 0, .8, (0, 210, 255), 2)
                    annotation_seconds = time.perf_counter() - started
                    if index in selected or (changed and len(deltas) <= 8):
                        if not cv2.imwrite(str(directory / f'review_{index:04d}.png'), preview):
                            raise RuntimeError('Cannot write review image')
                        write_json(directory / f'result_{index:04d}.json', result)
                    if annotations:
                        if writer is None:
                            height = round(1152 * image.shape[0] / image.shape[1] / 2) * 2
                            writer = cv2.VideoWriter(str(directory / 'review.mp4'),
                                cv2.VideoWriter_fourcc(*'mp4v'), 5., (1152, height))
                            if not writer.isOpened():
                                raise RuntimeError('Cannot create review video')
                        started = time.perf_counter()
                        writer.write(cv2.resize(preview, (1152, height)))
                        encoding_seconds = time.perf_counter() - started
                row = {'source_frame': index, 'receipt_seconds': timestamp, 'result': result,
                       'direct': direct, 'reset': processor.last_reset_reason,
                       'analysis_seconds': analysis_seconds, 'ocr_calls': len(ocr_times),
                       'ocr_seconds': sum(ocr_times), 'decode_seconds': decode_seconds,
                       'annotation_seconds': annotation_seconds, 'encoding_seconds': encoding_seconds,
                       'changed_paths': sorted(changed)}
                debug.write(json.dumps(row, allow_nan=False) + '\n')
                measurements.append({k: v for k, v in row.items() if k not in ('result', 'direct', 'changed_paths')})
                if index % 50 == 0:
                    print(name, index, '/', total, result['right_display']['state'], flush=True)
            compact.finish(processed_frames=len(frames), error=None)
    finally:
        capture.release()
        if writer is not None:
            writer.release()
    if len(frames) != total:
        raise ValueError(f'Frame count differs for {name}: {len(frames)} != {total}')
    report = {'simulation': True, 'source': str(source), 'frames': total,
              'baseline_kind': 'approved Step 4' if connected else 'historical accepted V2 predictions, not ground truth',
              'changed_frames': deltas, 'changed_first24': [i for i in deltas if i < 24],
              'changed_paths': dict(paths), 'contract': validate_results(frames, None),
              'compact': validate_compact(directory / 'results.jsonl', frames),
              'states': dict(Counter(r['right_display']['state'] for r in frames)),
              'button_counts': dict(Counter(len(r['right_display']['buttons']) for r in frames)),
              'left_counts': dict(Counter(len(r['left_display']['boxes']) for r in frames)),
              'resets': dict(Counter(r['reset'] for r in measurements)),
              'analysis_seconds': distribution([r['analysis_seconds'] for r in measurements]),
              'ocr_calls': sum(r['ocr_calls'] for r in measurements),
              'ocr_seconds': sum(r['ocr_seconds'] for r in measurements),
              'jitter_pixels': {key: distribution(values) for key, values in jitter.items()},
              'timing_limit': 'Corpus cost may include other validation load; use serial matched live trials for speed comparisons.'}
    if connected and name in ('dmi_capture_quality_02', 'dmi_capture_quality_03'):
        report.update(direct_values=value_counts(raw_values, '23'), stabilized_values=value_counts(stable_values, '23'))
    if annotations:
        capture = cv2.VideoCapture(str(directory / 'review.mp4'))
        decoded = 0
        while capture.read()[0]:
            decoded += 1
        capture.release()
        if decoded != total:
            raise ValueError('Review video does not decode completely')
        report['review_decoded_frames'] = decoded
    write_json(directory / 'summary.json', report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--suite', choices=('connected', 'separated', 'all'), default='all')
    parser.add_argument('--annotations', action='store_true')
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {'simulation': True, 'environment': {'python': sys.version, 'opencv': cv2.__version__,
              'numpy': np.__version__, 'platform': platform.platform()}, 'clips': {}}
    inputs = ([(f'dmi_capture_quality_{n:02d}', True) for n in range(1, 5)] if args.suite != 'separated' else [])
    if args.suite != 'connected':
        inputs.extend((name, False) for name in BASELINES)
    for name, connected in inputs:
        report['clips'][name] = verify_clip(name, args.output_dir / name, connected=connected, annotations=args.annotations)
        write_json(args.output_dir / 'summary.json', report)
        print('DONE', name, 'changed', len(report['clips'][name]['changed_frames']), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
