"""Validate serialized pipeline output without treating predictions as truth."""
from __future__ import annotations

import math
from copy import deepcopy
import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _require(condition: bool, path: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{path}: {message}")


def _mapping(value: Any, keys: set[str], path: str) -> dict:
    _require(isinstance(value, dict), path, "expected an object")
    _require(keys <= value.keys(), path, f"missing required keys: {keys - value.keys()}")
    return value


def _numbers(value: Any, shape: tuple[int, ...], path: str) -> np.ndarray:
    array = np.asarray(value)
    _require(array.shape == shape and array.dtype.kind in 'iuf', path,
             f"expected numeric shape {shape}")
    array = array.astype(np.float64)
    _require(bool(np.isfinite(array).all()), path, "coordinates must be finite")
    return array


def _region(value: Any, path: str, *, display: bool = False) -> None:
    region = _mapping(value, {'corners', 'bbox', 'center'}, path)
    corners = _numbers(region['corners'], (4, 2), path + '.corners')
    bbox = _numbers(region['bbox'], (4,), path + '.bbox')
    center = _numbers(region['center'], (2,), path + '.center')
    outlines = [corners]
    if display:
        _require('oriented_box' in region, path, 'missing oriented_box')
        outlines.append(_numbers(region['oriented_box'], (4, 2), path + '.oriented_box'))
    _require(bbox[0] < bbox[2] and bbox[1] < bbox[3], path, 'bbox must have positive area')
    for points in outlines:
        contour = points.astype(np.float32)
        _require(cv2.isContourConvex(contour) and cv2.contourArea(contour, oriented=True) > 0,
                 path, 'corners must form a clockwise convex region in image coordinates')
        _require(bool((points.min(axis=0) >= bbox[:2]).all()
                      and (points.max(axis=0) <= bbox[2:]).all()),
                 path, 'bbox does not enclose the reported outline')
        _require(cv2.pointPolygonTest(contour, tuple(center), False) >= 0,
                 path, 'center is outside the reported region')


def _text(value: Any, path: str) -> None:
    _require(value is None or isinstance(value, str), path, 'expected text or null')


def validate_results(frames: list[dict], fps: float | None) -> dict[str, int]:
    """Check frame order, timing, geometry, types and missing/paused semantics.

    This verifies the output contract, not recognition accuracy or border error.
    It does not mutate results, coerce uncertain values, or fill missing regions.
    Pass fps=None for live receipt timestamps (nondecreasing after rounding,
    starting at zero), instead of constant-rate video timestamps.
    """
    if fps is not None:
        _require(math.isfinite(fps) and fps > 0, 'fps', 'must be finite and positive')
    _require(isinstance(frames, list) and len(frames) > 0, 'frames', 'expected nonempty list')
    counts = {'frames': len(frames), 'display_geometries': 0,
              'left_regions': 0, 'right_regions': 0, 'occluded_frames': 0}
    for index, frame in enumerate(frames):
        path = f'frames[{index}]'
        _mapping(frame, {'frame_index', 'timestamp', 'left_display', 'right_display'}, path)
        _require(type(frame['frame_index']) is int and frame['frame_index'] == index,
                 path, 'frame_index must be contiguous from zero')
        timestamp = frame['timestamp']
        _require(type(timestamp) in (int, float) and math.isfinite(timestamp)
                 and timestamp >= 0, path, 'timestamp must be finite and nonnegative')
        if fps is None:
            _require(timestamp == 0 if index == 0 else timestamp >= frames[index - 1]['timestamp'],
                     path, 'live timestamps must start at zero and not decrease')
        else:
            _require(abs(timestamp - index / fps) <= 1e-6,
                     path, 'timestamp does not match source frame index/FPS')
        right = _mapping(frame['right_display'],
                         {'geometry', 'visibility', 'state', 'title', 'buttons', 'data_field'},
                         path + '.right_display')
        left = _mapping(frame['left_display'], {'geometry', 'boxes', 'speed_indicator'},
                        path + '.left_display')
        _require(right['state'] in ('Main', 'Driver ID', 'Level', 'Train Data',
                 'Validate Train Data', 'Train Data (1/2)', 'Train Data (2/2)',
                 'Train Running Number', 'unknown'), path, 'invalid state')
        _require(right['visibility'] in ('clear', 'occluded', 'unknown'), path, 'invalid visibility')
        _mapping(right['buttons'], set(), path + '.buttons')
        _mapping(left['boxes'], set(), path + '.boxes')
        for side, result in (('left', left), ('right', right)):
            if result['geometry'] is not None:
                _region(result['geometry'], path + f'.{side}.geometry', display=True)
                counts['display_geometries'] += 1
        if left['geometry'] is None:
            _require(not left['boxes'] and left['speed_indicator'] is None,
                     path, 'missing left display must not retain content')
        if 'title' in left:
            _require(left['geometry'] is not None, path,
                     'missing left display must not retain a title')
            _mapping(left['title'], {'text'}, path + '.left.title')
            _text(left['title']['text'], path + '.left.title.text')
            _region(left['title'], path + '.left.title')
            counts['left_regions'] += 1
            _mapping(left.get('buttons'), set(), path + '.left.buttons')
            for name, region in left['buttons'].items():
                _require(isinstance(name, str) and bool(name), path,
                         'left button identity must be nonempty text')
                _region(region, path + '.left.buttons.' + name)
                counts['left_regions'] += 1
        if right['geometry'] is None:
            _require(right['visibility'] == 'unknown', path, 'missing right geometry requires unknown visibility')
        else:
            _require(right['visibility'] != 'unknown', path, 'localized display needs visibility evidence')
        if right['visibility'] in ('occluded', 'unknown'):
            _require(right['state'] == 'unknown' and right['title'] is None
                     and right['data_field'] is None and not right['buttons'],
                     path, 'unavailable/occluded display must not retain content')
        if right['visibility'] == 'occluded':
            counts['occluded_frames'] += 1
        for key, text_key in (('title', 'text'), ('data_field', 'value')):
            region = right[key]
            if region is not None:
                _mapping(region, {text_key}, path + '.' + key)
                _text(region[text_key], path + '.' + key + '.' + text_key)
                _region(region, path + '.' + key)
                counts['right_regions'] += 1
        for name, region in right['buttons'].items():
            _require(isinstance(name, str) and bool(name), path, 'button identity must be nonempty text')
            _region(region, path + '.buttons.' + name)
            counts['right_regions'] += 1
        for name, region in left['boxes'].items():
            _require(name in {f'box_{i}' for i in range(1, 23)}, path, 'invalid left box identity')
            _mapping(region, {'icon'}, path + '.boxes.' + name)
            _require(region['icon'] in (None, 'level0_icon', 'level1_icon', 'level2_icon'),
                     path + '.boxes.' + name, 'invalid icon identity')
            _region(region, path + '.boxes.' + name)
            counts['left_regions'] += 1
        if left['speed_indicator'] is not None:
            _region(left['speed_indicator'], path + '.speed_indicator')
            counts['left_regions'] += 1
    return counts


def compare_frames(frames: list[dict], baseline: list[dict]) -> dict[str, list[int]]:
    """Isolate exact display-bbox corrections from other regression differences."""
    _require(len(frames) == len(baseline), 'baseline', 'frame count mismatch')
    changed, bounds_only, other = [], [], []
    for index, (current, previous) in enumerate(zip(frames, baseline)):
        if current == previous:
            continue
        changed.append(index)
        normalized = deepcopy(previous)
        for side in ('left_display', 'right_display'):
            geometry = normalized[side]['geometry']
            if geometry is not None:
                points = np.array(geometry['corners'] + geometry['oriented_box'])
                geometry['bbox'] = [*points.min(axis=0).tolist(), *points.max(axis=0).tolist()]
        (bounds_only if normalized == current else other).append(index)
    return {'changed_frames': changed, 'display_bbox_only_frames': bounds_only,
            'other_changed_frames': other}


def compare_annotated_videos(current: Path, baseline: Path) -> dict | None:
    """Compare saved visuals; identical encodings avoid redundant pixel decoding.

    Frame completeness is validated separately against the JSON by evaluation.
    Different encodings are decoded so container metadata alone is not counted
    as an annotation regression.
    """
    if not baseline.is_file():
        return None
    def digest(path):
        value = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                value.update(chunk)
        return value.hexdigest()
    if digest(current) == digest(baseline):
        return {'identical_file': True, 'changed_frames': []}
    captures = [cv2.VideoCapture(str(path)) for path in (current, baseline)]
    changed = []
    try:
        if not all(cap.isOpened() for cap in captures):
            raise ValueError('cannot decode annotation comparison input')
        index = 0
        while True:
            ok, first = captures[0].read()
            previous_ok, second = captures[1].read()
            if ok != previous_ok:
                raise ValueError('annotation comparison frame count mismatch')
            if not ok:
                break
            if not np.array_equal(first, second):
                changed.append(index)
            index += 1
    finally:
        for capture in captures:
            capture.release()
    return {'identical_file': False, 'changed_frames': changed}
