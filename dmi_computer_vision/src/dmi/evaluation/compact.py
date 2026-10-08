"""Validate compact replay against each full detection, including suppressed frames."""
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

from dmi_computer_vision.src.dmi.output.json_writer import compact_state


def assert_equivalent(actual, expected, tolerance, path="state"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError(f"{path}: state keys differ")
        for key in expected:
            assert_equivalent(actual[key], expected[key], tolerance, f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{path}: coordinate shape differs")
        for i, (a, b) in enumerate(zip(actual, expected)):
            assert_equivalent(a, b, tolerance, f"{path}[{i}]")
    elif type(expected) in (int, float):
        if not math.isfinite(actual) or abs(actual - expected) > tolerance:
            raise ValueError(f"{path}: coordinate differs by more than {tolerance}px")
    elif actual != expected:
        raise ValueError(f"{path}: semantic value differs: {actual!r} != {expected!r}")


def validate_compact(path, frames):
    records = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if not records or records[0]['type'] != 'session_start' or records[-1]['type'] != 'session_end':
        raise ValueError('expected complete session boundaries')
    if records[-1]['processed_frames'] != len(frames) or records[-1]['error'] is not None:
        raise ValueError('compact session did not complete expected frames')
    events = records[1:-1]
    if not events or events[0]['type'] != 'snapshot' or events[0]['frame'] != 0:
        raise ValueError('missing initial snapshot')
    indices = [r['frame'] for r in events]
    if indices != sorted(set(indices)) or indices[-1] >= len(frames):
        raise ValueError('invalid compact event frame order')
    tolerance = records[0]['geometry_tolerance_px']
    state, cursor = {}, 0

    def merge(target, patch):
        for key, value in patch.items():
            if isinstance(value, dict):
                if key not in target or not isinstance(target[key], dict):
                    target[key] = {}
                merge(target[key], value)
            else:
                target[key] = deepcopy(value)

    for frame in frames:
        if cursor < len(events) and events[cursor]['frame'] == frame['frame_index']:
            event = events[cursor]
            if event['timestamp'] != frame['timestamp']:
                raise ValueError('compact timestamp differs from detection')
            patch = {k: v for k, v in event.items() if k in ('left_display', 'right_display')}
            if event['type'] == 'snapshot':
                state = deepcopy(patch)
            elif event['type'] == 'update':
                merge(state, patch)
            else:
                raise ValueError('invalid compact event type')
            cursor += 1
        assert_equivalent(state, compact_state(frame), tolerance)
    return {'records': len(records), 'record_types': dict(Counter(r['type'] for r in records)),
            'jsonl_bytes': Path(path).stat().st_size, 'frames_reconstructed': len(frames),
            'geometry_tolerance_px': tolerance, 'semantic_mismatches': 0}
