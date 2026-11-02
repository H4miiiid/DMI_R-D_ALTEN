"""Operator-measured SENSE correspondences; candidates never authorize actions."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import time
import tempfile
import math

import cv2
import numpy as np

from dmi_robot_master.integration.calibration import (
    MODEL, _frame_size, _identifier, _point, _positive, save_calibration,
)
from dmi_robot_master.integration.sense_calibration import _geometry, compare_models, identity

CALIBRATION_TYPE = 'sense_guided_candidate'


def _context_values(context: dict):
    camera, origin, conventions = (context[key] for key in ('camera', 'origin', 'conventions'))
    if (camera.get('source_kind') not in ('recorded_replay', 'local_camera', 'remote_bridge')
            or any(not isinstance(camera.get(k), str) or not camera[k].strip() for k in ('identity', 'mount_id'))
            or not isinstance(camera.get('settings'), dict)
            or any(not isinstance(origin.get(k), str) or not origin[k].strip() for k in ('identity', 'axes'))
            or conventions.get('coordinates') != 'absolute_robot_xy_mm'
            or any(not isinstance(conventions.get(k), str) or not conventions[k].strip() for k in ('panel', 'tool', 'point'))):
        raise ValueError('Record camera, mount, origin, axes and absolute panel/tool/point conventions')
    limits = context['xy_limits_mm']
    if (not isinstance(limits, list) or len(limits) != 2
            or any(type(v) is not int or not 0 < v < 2**31 for v in limits)):
        raise ValueError('Record independent positive integer XY limits in mm')
    return camera, origin, conventions, limits


def _context(context: dict):
    try:
        return _context_values(context)
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Provide camera/origin/conventions and independent XY limits') from exc


def _fit_guided(request: dict) -> dict:
    size = _frame_size(request['frame_size'])
    geometry = _geometry(request['geometry'], size)
    context = deepcopy(request['context'])
    camera, origin, conventions, limits = _context(context)
    if camera['settings'].get('original_size') not in (None,list(size)):
        raise ValueError('Camera context frame size differs from collected native frames')
    rows = deepcopy(request['points'])
    fit, check = [], []
    for row in rows:
        key = identity(row)
        if row['screen'] == 'unknown':
            raise ValueError('Collect a recognized screen identity')
        evidence = row['evidence']
        age = evidence['age_at_collection_seconds']
        if (type(age) not in (int,float) or not np.isfinite(age) or not 0 <= age <= 1.5
                or evidence['session_id'] != request['session_id']
                or not isinstance(request['session_id'], str) or not request['session_id']
                or evidence['origin_epoch'] != request['origin_epoch']
                or evidence['source_info'] != request['source_info']
                or type(evidence['capture_index']) is not int or evidence['capture_index'] < 0):
            raise ValueError('Correspondences mix sessions/origins or lack fresh direct evidence')
        from dmi_robot_master.integration.targets import validate_camera_source, utc_time
        validate_camera_source(camera, evidence['source_info'])
        utc_time(evidence['collected_at_utc'])
        if row['display'] not in ('left', 'right') or row['kind'] not in ('button', 'field'):
            raise ValueError('Collect an identified button/field, not an unqualified box')
        pixel, mm = _point(row['pixel']), _point(row['mm'])
        if (cv2.pointPolygonTest(np.array(geometry[row['display']], np.float32), tuple(pixel), False) < 0
                or any(not 0 <= v < bound for v, bound in zip(mm, limits))):
            raise ValueError('Correspondence outside measured region or configured absolute XY bounds')
        if row['role'] not in ('fit', 'check'):
            raise ValueError('Point role must be fit or independent check')
        (fit if row['role'] == 'fit' else check).append(row)
    if len(fit) < 5 or len(check) < 1:
        raise ValueError('Collect at least five fit controls and one separate held-out control')
    if (len({identity(row) for row in rows}) != len(rows)
            or len({tuple(row['mm']) for row in rows}) != len(rows)
            or len({tuple(row['pixel']) for row in rows}) != len(rows)):
        raise ValueError('Duplicate controls, physical locations or pixels do not add independent coverage')
    tolerance, threshold = request['tolerance_mm'], request['outlier_threshold_mm']
    _positive(tolerance, 'Independent numerical tolerance in mm')
    _positive(threshold, 'Diagnostic outlier threshold in mm')
    if tolerance > 3 or threshold > 3:
        raise ValueError('Current provisional maximum is 3 mm; no relaxed calibration limit')
    if not isinstance(request['tolerance_basis'], str) or not request['tolerance_basis'].strip():
        raise ValueError('Explain the numerical tolerance; it is not physical approval')
    models, selected = compare_models(fit, check, threshold=threshold, tolerance=tolerance)
    document = {'schema_version': 3, 'calibration_type': CALIBRATION_TYPE, 'model': MODEL,
        'provenance': 'guided_unverified', 'request': deepcopy(request), 'frame_size': list(size),
        'camera': camera, 'origin': origin, 'conventions': conventions, 'geometry': geometry,
        'models': models, 'selected_model': selected, 'inspection_model': selected or 'affine',
        'coverage': {'fit_hull_pixels': cv2.convexHull(np.array([r['pixel'] for r in fit], np.float32)).reshape(-1,2).tolist(),
                     'physical_validated_area': None},
        'validation': {'hardware_verified': False, 'action_usable': False,
                       'tolerance_mm': tolerance, 'outlier_threshold_mm': threshold}}
    document['calibration_id'] = _identifier(document)
    return document


def fit_guided(request: dict) -> dict:
    """Fit measured absolute XY; a numerical pass is never physical verification."""
    try:
        return _fit_guided(request)
    except (KeyError, TypeError, AttributeError, IndexError, cv2.error, np.linalg.LinAlgError) as exc:
        raise ValueError(f'Malformed guided correspondences: {exc}') from exc


def validate_guided(document: dict) -> None:
    if (document.get('calibration_type') != CALIBRATION_TYPE
            or document.get('calibration_id') != _identifier(document)
            or document != fit_guided(document['request'])):
        raise ValueError('Guided candidate differs from recomputed measured evidence')


class CalibrationDraft:
    """One source/session/origin basis. Every point needs new direct evidence."""
    def __init__(self, context: dict, *, origin_epoch: str | None):
        _context(context)
        self.context = deepcopy(context)
        self.origin_epoch = origin_epoch
        self._basis = None
        self._points = []
        self.document = None

    def points(self) -> list[dict]:
        return deepcopy(self._points)

    def add(self, sample: dict, mm, *, role: str, origin_epoch: str | None) -> None:
        upstream = sample['upstream_age_seconds']
        if type(upstream) not in (int,float) or not math.isfinite(upstream) or upstream < 0:
            raise ValueError('Invalid upstream evidence age')
        age = time.monotonic()-sample['received_at']+sample['upstream_age_seconds']
        if not 0 <= age <= 1.5 or origin_epoch != self.origin_epoch:
            raise ValueError('Pixel observation expired or robot origin changed; start a new draft')
        geometry = _geometry(sample['geometry'], _frame_size(sample['frame_size']))
        basis = {key: deepcopy(sample[key]) for key in ('session_id', 'source_info', 'frame_size')}
        if self._basis is not None:
            if basis != {k:self._basis[k] for k in basis} or any(
                    np.max(np.abs(np.array(geometry[s])-self._basis['geometry'][s])) > 4 for s in ('left','right')):
                raise ValueError('Camera session/size/geometry changed; start a new draft')
        from dmi_robot_master.integration.targets import validate_camera_source
        validate_camera_source(self.context['camera'], sample['source_info'])
        target = sample['target']
        if target['kind'] not in ('button','field'):
            raise ValueError('Choose a measured button or confirmation field')
        row = {'screen':sample['screen'], 'display':target['display'], 'kind':target['kind'],
            'label':target['label'], 'pixel':_point(target['pixel']).tolist(), 'mm':_point(mm).tolist(), 'role':role,
            'evidence': {'session_id':sample['session_id'], 'capture_index':sample['capture_index'],
                'age_at_collection_seconds':age, 'source_info':deepcopy(sample['source_info']),
                'collected_at_utc':datetime.now(timezone.utc).isoformat(), 'origin_epoch':origin_epoch}}
        if role not in ('fit','check') or any(not 0 <= v < b for v,b in zip(row['mm'], self.context['xy_limits_mm'])):
            raise ValueError('Choose fit/check role and absolute XY inside independent limits')
        identity(row)
        if row['screen'] == 'unknown':
            raise ValueError('Collect a recognized screen identity')
        if row['display'] not in ('left','right') or cv2.pointPolygonTest(
                np.array(geometry[row['display']],np.float32),tuple(row['pixel']),False) < 0:
            raise ValueError('Point outside its current measured display')
        if any(identity(p)==identity(row) or p['mm']==row['mm'] or p['pixel']==row['pixel'] for p in self._points):
            raise ValueError('Duplicate identity/location; remove its earlier point before recollecting')
        if self._basis is None:
            self._basis = {**basis,'geometry':geometry}
        self._points.append(row)
        self.document = None

    def remove(self, index: int) -> None:
        del self._points[index]
        self.document = None

    def fit(self, *, tolerance_mm: float, tolerance_basis: str) -> dict:
        if self._basis is None:
            raise ValueError('Collect correspondences first')
        request = {'context':deepcopy(self.context), 'frame_size':self._basis['frame_size'],
            'geometry':self._basis['geometry'], 'points':self.points(), 'tolerance_mm':tolerance_mm,
            'outlier_threshold_mm':tolerance_mm, 'tolerance_basis':tolerance_basis,
            'session_id':self._basis['session_id'], 'source_info':self._basis['source_info'],
            'origin_epoch':self.origin_epoch}
        self.document = None
        self.document = fit_guided(request)
        return deepcopy(self.document)

    def save(self, path: str | Path) -> None:
        if self.document is None:
            raise ValueError('Fit the current point set before saving')
        path = Path(path).expanduser().resolve()
        if any(path.is_relative_to(root.resolve()) for root in (Path('/tmp'), Path('/var/folders'), Path(tempfile.gettempdir()))):
            raise ValueError('Save durable calibration outside temporary directories')
        validate_guided(self.document)
        path.parent.mkdir(parents=True, exist_ok=True)
        save_calibration(self.document, path)  # Existing no-overwrite contract.
