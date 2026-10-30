"""Offline SENSE plane fitting and inspection; never action authorization.

Schema 2 deliberately remains separate from the legacy, executable keypad model.
Inputs are original-frame correspondences, not detector templates or UI slots.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

import cv2
import numpy as np

from dmi_robot_master.integration.calibration import (
    MODEL, _frame_size, _identifier, _noncollinear, _point, _positive,
    read_json, transform_point,
)

REFERENCE_PATH = Path(__file__).resolve().parents[2] / 'TapperWare_Flet' / 'DmiPositions.json'
CALIBRATION_TYPE = 'sense_offline_plane'
# Explicit Step 9 aliases. The database storage screen is not always the UI state.
ALIASES = {
    **{('Driver ID', 'right', 'button', f'digit_{n}'): ('DRIVER_ID_SCREEN', f'KEY_{n}') for n in range(10)},
    ('Driver ID', 'right', 'button', 'delete'): ('DRIVER_ID_SCREEN', 'KEY_DEL'),
    ('Driver ID', 'right', 'field', 'driver_id'): ('DRIVER_ID_SCREEN', 'KEY_CONF_DRIVER'),
    **{('Level', 'right', 'button', f'level_{n}'): ('LEVEL_SCREEN', f'LEVEL_{n}') for n in (0, 1, 2)},
    ('Level', 'right', 'field', 'level'): ('LEVEL_SCREEN', 'LEVEL_CONF'),
    ('Main', 'right', 'button', 'start'): ('MAIN_SCREEN', 'START'),
    ('Main', 'right', 'button', 'train_data'): ('MAIN_SCREEN', 'TRAIN_DATA'),
    **{(state, 'left', 'button', 'yes'): ('TRAIN_DATA_SCREEN', 'KEY_YES_1')
       for state in ('Train Data', 'Train Data (1/2)', 'Train Data (2/2)')},
    ('Validate Train Data', 'right', 'field', 'validation'): ('TRAIN_DATA_SCREEN', 'KEY_YES_2'),
}


def identity(point: dict) -> tuple:
    key = tuple(point[name] for name in ('screen', 'display', 'kind', 'label'))
    if any(not isinstance(value, str) or not value for value in key):
        raise ValueError('Control identities must be nonempty strings')
    return key


def _geometry(value: dict, size: tuple) -> dict:
    """Require measured joined regions; a camera number cannot establish SENSE."""
    result = {}
    for display in ('left', 'right'):
        points = np.array([_point(p) for p in value[display]], dtype=np.float32)
        if points.shape != (4, 2) or not cv2.isContourConvex(points) or cv2.contourArea(points) <= 0:
            raise ValueError('Need convex measured monitor regions')
        if not ((points >= 0).all() and (points[:, 0] < size[0]).all() and (points[:, 1] < size[1]).all()):
            raise ValueError('Monitor corners outside original frame')
        result[display] = points.tolist()
    if not np.allclose(np.array(result['left'])[[1, 2]], np.array(result['right'])[[0, 3]], atol=1, rtol=0):
        raise ValueError('Need measured connected SENSE regions, not separated TWIN')
    return result


def _points(points: list, reference: dict, size: tuple) -> list:
    rows = []
    for raw in points:
        key = identity(raw)
        if key not in ALIASES:
            raise ValueError(f'No audited SENSE reference for {key}')
        screen, button = ALIASES[key]
        source = reference[MODEL]['screens'][screen]['buttons'][button]
        pixel = _point(raw['pixel'])
        mm = _point([source['x'], source['y']])
        if not (0 <= pixel[0] < size[0] and 0 <= pixel[1] < size[1]):
            raise ValueError('Correspondence outside original frame')
        rows.append({**{name: raw[name] for name in ('screen', 'display', 'kind', 'label')},
                     'pixel': pixel.tolist(), 'mm': mm.tolist(), 'reference': [screen, button]})
    return rows


def _matrix(pixels: np.ndarray, mm: np.ndarray, model: str) -> np.ndarray:
    _noncollinear(pixels)
    _noncollinear(mm)
    if model == 'affine':
        coefficients, _, rank, _ = np.linalg.lstsq(np.column_stack((pixels, np.ones(len(pixels)))), mm, rcond=None)
        if rank != 3:
            raise ValueError('Degenerate affine correspondences')
        matrix = np.vstack((coefficients.T, [0., 0., 1.]))
    else:
        # All points participate. Diagnostics never hide/drop a bad correspondence.
        matrix, _ = cv2.findHomography(pixels, mm, method=0)
        if matrix is None:
            raise ValueError('Homography fit failed')
    for pixel in pixels:
        transform_point(matrix, pixel)
    denominators = np.column_stack((pixels, np.ones(len(pixels)))) @ matrix[2]
    if not ((denominators > 0).all() or (denominators < 0).all()):
        raise ValueError('Homography horizon crosses fitted area')
    return matrix


def _errors(matrix, rows):
    return {str(identity(row)): float(np.linalg.norm(np.array(transform_point(matrix, row['pixel']))-row['mm']))
            for row in rows}


def _fit_offline(request: dict, *, reference_path: str | Path) -> dict:
    """Compare affine/homography using whole-control holdouts; export diagnostics.

    Optional tolerance is a numerical screening criterion, never physical approval.
    Repeated frames/locations cannot count as independent calibration points.
    """
    size = _frame_size(request['frame_size'])
    camera, origin, conventions = (deepcopy(request[name]) for name in ('camera', 'origin', 'conventions'))
    if (camera.get('source_kind') != 'recorded_replay' or not camera.get('identity') or
            not camera.get('mount_id') or not isinstance(camera.get('settings'), dict)):
        raise ValueError('Offline SENSE fitting requires a recorded source identity/settings/mount')
    if not origin.get('identity') or not origin.get('axes'):
        raise ValueError('Record robot origin and axes, including explicit unknowns')
    if (conventions.get('coordinates') != 'absolute_robot_xy_mm' or
            any(not isinstance(conventions.get(k), str) or not conventions[k].strip()
                for k in ('panel', 'tool', 'point'))):
        raise ValueError('Record absolute XY, panel/tool and correspondence conventions')
    geometry = _geometry(request['geometry'], size)
    reference = read_json(reference_path)
    fit = _points(request['fit_points'], reference, size)
    check = _points(request.get('check_points', []), reference, size)
    if len(fit) < 5:
        raise ValueError('Need five non-collinear independent locations for leave-one-out')
    all_rows = fit + check
    for row in all_rows:
        if cv2.pointPolygonTest(np.array(geometry[row['display']], np.float32), tuple(row['pixel']), False) < 0:
            raise ValueError('Correspondence outside its measured logical region')
    if len({identity(row) for row in all_rows}) != len(all_rows):
        raise ValueError('Duplicate control identity in fit/held-out points')
    if len({tuple(row['mm']) for row in all_rows}) != len(all_rows):
        raise ValueError('Repeated physical XY does not add independent coverage')
    if len({tuple(row['pixel']) for row in all_rows}) != len(all_rows):
        raise ValueError('Contradictory controls share one pixel')
    threshold = request['outlier_threshold_mm']
    _positive(threshold, 'Diagnostic outlier threshold in mm')
    tolerance = request.get('tolerance_mm')
    if tolerance is not None:
        _positive(tolerance, 'Numerical held-out tolerance')
        if not isinstance(request.get('tolerance_basis'), str) or not request['tolerance_basis'].strip():
            raise ValueError('Explain the numerical tolerance; it is not physical verification')
    pixels = np.array([r['pixel'] for r in fit], dtype=float)
    mm = np.array([r['mm'] for r in fit], dtype=float)
    models = {}
    for model in ('affine', 'homography'):
        matrix = _matrix(pixels, mm, model)
        loo = {}
        for i, row in enumerate(fit):
            keep = np.arange(len(fit)) != i
            held_matrix = _matrix(pixels[keep], mm[keep], model)
            loo.update(_errors(held_matrix, [row]))
        independent = _errors(matrix, check)
        errors = {**loo, **independent}
        outliers = [key for key, error in errors.items() if error > threshold]
        models[model] = {'matrix': matrix.tolist(), 'training_error_mm': _errors(matrix, fit),
                         'leave_one_control_out_mm': loo, 'held_out_control_error_mm': independent,
                         'mean_error_mm': float(np.mean(list(errors.values()))),
                         'max_error_mm': max(errors.values()), 'outliers': outliers,
                         'numerically_accepted': tolerance is not None and max(errors.values()) <= tolerance and not outliers}
    selected = next((name for name in ('affine', 'homography') if models[name]['numerically_accepted']), None)
    document = {'schema_version': 2, 'calibration_type': CALIBRATION_TYPE, 'model': MODEL,
                'provenance': 'offline_recording', 'plane': 'upper_SENSE_screen_candidate',
                'frame_size': list(size), 'camera': camera,
                'origin': origin, 'conventions': conventions, 'geometry': geometry,
                'reference_sha256': hashlib.sha256(Path(reference_path).read_bytes()).hexdigest(),
                'fit_points': fit, 'check_points': check, 'models': models, 'selected_model': selected,
                'inspection_model': selected or 'affine',
                'coverage': {'fit_hull_pixels': cv2.convexHull(pixels.astype(np.float32)).reshape(-1, 2).tolist(),
                             'screens': sorted({r['screen'] for r in fit}),
                             'physical_validated_area': None},
                'validation': {'outlier_threshold_mm': threshold, 'tolerance_mm': tolerance,
                               'tolerance_basis': request.get('tolerance_basis'),
                               'selection': 'simplest model passing all independent errors and outlier screen; no point deletion',
                               'hardware_verified': False, 'action_usable': False},
                'source_evidence': deepcopy(request.get('source_evidence', {}))}
    document['calibration_id'] = _identifier(document)
    return document


def fit_offline(request: dict, *, reference_path: str | Path = REFERENCE_PATH) -> dict:
    """Compare and export an offline candidate; malformed input fails explicitly."""
    try:
        return _fit_offline(request, reference_path=reference_path)
    except (KeyError, TypeError, AttributeError, IndexError, cv2.error) as error:
        raise ValueError(f'Malformed offline SENSE correspondences: {error}') from error


def validate_offline(document: dict, *, reference_path: str | Path = REFERENCE_PATH) -> None:
    """Recompute numerical evidence; a typed verification flag grants nothing."""
    try:
        if (document.get('schema_version') != 2 or document.get('calibration_type') != CALIBRATION_TYPE or
                document.get('model') != MODEL or document.get('provenance') != 'offline_recording' or
                document.get('calibration_id') != _identifier(document)):
            raise ValueError('Invalid offline SENSE calibration identity/schema')
        request = {key: document[key] for key in
                   ('frame_size', 'camera', 'origin', 'conventions', 'geometry', 'fit_points', 'check_points', 'source_evidence')}
        request.update({key: document['validation'][key] for key in
                        ('outlier_threshold_mm', 'tolerance_mm', 'tolerance_basis')})
        expected = fit_offline(request, reference_path=reference_path)
        if document != expected:
            raise ValueError('Offline calibration differs from recomputed evidence/reference')
    except (KeyError, TypeError, AttributeError, IndexError, cv2.error) as error:
        raise ValueError(f'Malformed offline SENSE calibration: {error}') from error


def inspect_result(document: dict, result: dict, *, frame_size: tuple, camera: dict,
                   origin: dict, geometry_tolerance_px: float) -> dict:
    """Inspect mathematically defined mm without renewing evidence or enabling actions.

    The caller validates the document/reference on load. Current source context and
    measured enclosure must still agree on every inspection; never re-anchor a fit.
    """
    from dmi_robot_master.integration.publication import project_pixels

    _positive(geometry_tolerance_px, 'Inspection geometry tolerance')
    if (list(_frame_size(frame_size)) != document['frame_size'] or
            camera != document['camera'] or origin != document['origin']):
        raise ValueError('Offline calibration camera/frame/origin context changed')
    current = _geometry({side: result[f'{side}_display']['geometry']['corners'] for side in ('left', 'right')}, frame_size)
    for side in ('left', 'right'):
        if np.max(np.abs(np.array(current[side])-document['geometry'][side])) > geometry_tolerance_px:
            raise ValueError('Measured monitor moved; offline fit cannot be reused')
    if result['right_display']['visibility'] != 'clear':
        raise ValueError('Occluded/unknown geometry cannot support offline inspection')
    snapshot = project_pixels(result, frame_size=frame_size)
    snapshot.update(simulation=True, calibration_id=document['calibration_id'], calibration_valid=False,
                    calibration_provenance='offline_recording')
    matrix = document['models'][document['inspection_model']]['matrix']
    for target in snapshot['targets'].values():
        target['mm'], target['usable'] = None, False
        if target['kind'] == 'box':
            continue
        try:
            target['mm'] = transform_point(matrix, target['pixel'])
        except ValueError:
            pass  # Outside the model's finite domain stays explicitly unmapped.
    return snapshot
