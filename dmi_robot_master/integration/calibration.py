"""Driver ID screen-plane calibration, independent of acquisition and motors."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

REFERENCE_PATH = Path(__file__).resolve().parents[1] / 'DmiPositions.json'
MODEL = 'DMI_SENSE_TOUCHSCREEN'
KEYS = tuple(f'KEY_{digit}' for digit in range(10))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def reference_points(path: str | Path = REFERENCE_PATH) -> tuple[dict, str]:
    path = Path(path)
    database = read_json(path)
    buttons = database[MODEL]['screens']['DRIVER_ID_WINDOW']['buttons']
    points = {key: _point([buttons[key]['x'], buttons[key]['y']]).tolist() for key in KEYS}
    return points, hashlib.sha256(path.read_bytes()).hexdigest()


def _positive(value: float, name: str) -> None:
    if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')


def _point(value) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf":
        raise ValueError("Point coordinates must be numeric, not strings or booleans")
    array = raw.astype(np.float64)
    if array.shape != (2,) or not np.isfinite(array).all():
        raise ValueError('Expected one finite [x, y] point')
    return array


def _frame_size(value) -> tuple[int, int]:
    if len(value) != 2 or any(type(v) is not int or v <= 0 for v in value):
        raise ValueError('Frame size must be two positive integers [width, height]')
    return tuple(value)


class KeypadObservations:
    """Collect a bounded run of complete, clear, stable identity matches.

    Uses original-image detector centers. Temporal output is not evidence of
    independent/raw detections; hardware capture must check that separately.
    """
    def __init__(self, frame_size: tuple[int, int], *, observations: int,
                 max_spread_px: float) -> None:
        self.frame_size = _frame_size(frame_size)
        if type(observations) is not int or observations < 3:
            raise ValueError('Collect at least three distinct observations')
        _positive(max_spread_px, 'Center spread limit in pixels')
        self.required = observations
        self.max_spread_px = max_spread_px
        self.samples: list[dict] = []
        self.last_capture_index = -1
        self.rejected = 0
        self.last_rejection: str | None = None

    def add(self, record: dict) -> bool:
        """Return False and clear the run on missing/ambiguous/unstable geometry."""
        index = record['capture_index']
        if type(index) is not int or index <= self.last_capture_index:
            raise ValueError('Observation capture indices must increase')
        self.last_capture_index = index
        if _frame_size(record['frame_size']) != self.frame_size:
            raise ValueError('Input image size changed during calibration')
        right = record['result']['right_display']
        try:
            if right['state'] != 'Driver ID' or right['visibility'] != 'clear' or right['geometry'] is None:
                raise ValueError('Need a visible, clear Driver ID screen')
            centers = {f'KEY_{digit}': _point(right['buttons'][f'digit_{digit}']['center'])
                       for digit in range(10)}
            width, height = self.frame_size
            points = np.array(list(centers.values()))
            if not ((points >= 0).all() and (points[:, 0] < width).all() and (points[:, 1] < height).all()):
                raise ValueError('Centers must be in original image bounds')
            if len(np.unique(points, axis=0)) != 10:
                raise ValueError('Ambiguous keys share a center')
            if record.get('temporal_reset') is not None:
                self.samples.clear()
            trial = (self.samples + [centers])[-self.required:]
            for key in KEYS:
                values = np.array([sample[key] for sample in trial])
                spread = np.linalg.norm(values - np.median(values, axis=0), axis=1).max()
                if spread > self.max_spread_px:
                    raise ValueError('Unstable keypad center')
        except (KeyError, TypeError, ValueError) as exc:
            self.last_rejection = str(exc)
            self.rejected += 1
            self.samples.clear()
            return False
        self.samples = trial
        return True

    def summarize(self) -> dict:
        if len(self.samples) < self.required:
            reason = f'; last rejection: {self.last_rejection}' if self.last_rejection else ''
            raise ValueError('Not enough consecutive complete stable observations' + reason)
        return {key: np.median([sample[key] for sample in self.samples], axis=0).tolist()
                for key in KEYS}


def transform_point(matrix, pixel) -> list[float]:
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError('Invalid homography matrix')
    if np.linalg.matrix_rank(matrix) != 3:
        raise ValueError('Singular homography')
    point = np.append(_point(pixel), 1.0)
    projected = matrix @ point
    # Relative denominator check is invariant to arbitrary homography scaling.
    denominator_scale = np.linalg.norm(matrix[2]) * np.linalg.norm(point)
    if denominator_scale == 0 or abs(projected[2]) <= 1e-10 * denominator_scale:
        raise ValueError('Unstable homogeneous division')
    xy = projected[:2] / projected[2]
    if not np.isfinite(xy).all():
        raise ValueError('Nonfinite transformed position')
    return xy.tolist()


def _noncollinear(points) -> None:
    points = np.asarray(points, dtype=np.float64)
    if len(np.unique(points, axis=0)) != len(points):
        raise ValueError('Duplicate correspondence points')
    singular = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
    if len(singular) < 2 or singular[0] == 0 or singular[1] <= singular[0] * 1e-6:
        raise ValueError('Degenerate/collinear correspondences')


def _fit(pixels, millimeters, threshold_mm):
    _noncollinear(pixels)
    _noncollinear(millimeters)
    matrix, mask = cv2.findHomography(np.asarray(pixels, np.float64),
        np.asarray(millimeters, np.float64), cv2.RANSAC, threshold_mm)
    if matrix is None or mask is None or int(mask.sum()) < 4:
        raise ValueError('Insufficient homography inliers')
    for pixel in pixels:
        transform_point(matrix, pixel)
    denominators = np.column_stack((pixels, np.ones(len(pixels)))) @ matrix[2]
    if not ((denominators > 0).all() or (denominators < 0).all()):
        raise ValueError("Homography horizon intersects calibration area")
    return matrix, mask.ravel().astype(bool)


def _identifier(document: dict) -> str:
    body = {k: v for k, v in document.items() if k != 'calibration_id'}
    encoded = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def fit_calibration(centers: dict, *, frame_size: tuple[int, int], camera: dict,
                    origin: dict, ransac_threshold_mm: float,
                    tolerance_mm: float | None = None, tolerance_basis: str | None = None,
                    provenance: str = 'simulation', observation_summary: dict | None = None,
                    reference_path: str | Path = REFERENCE_PATH) -> dict:
    """Fit and independently validate all supplied identities; no motor command.

    At least five keys are needed so each held-out key has four training keys.
    Outliers are reported and rejected, not silently removed to improve validation.
    """
    size = _frame_size(frame_size)
    _positive(ransac_threshold_mm, 'RANSAC threshold in mm')
    if tolerance_mm is not None:
        _positive(tolerance_mm, 'Acceptance tolerance in mm')
        if not isinstance(tolerance_basis, str) or not tolerance_basis.strip():
            raise ValueError('Explain the supplied acceptance tolerance')
    if provenance not in ('simulation', 'hardware'):
        raise ValueError('Calibration provenance must be simulation or hardware')
    if not camera.get('identity') or not isinstance(camera.get('settings'), dict) or not camera.get('mount_id'):
        raise ValueError('Record camera identity, settings and mount revision')
    if not origin.get('identity') or not origin.get('axes'):
        raise ValueError('Record robot origin identity and axis convention')
    if provenance == 'hardware' and camera.get('source_kind') not in ('local_camera', 'remote_bridge'):
        raise ValueError('Recorded/synthetic sources cannot produce hardware calibration')
    keys = [key for key in KEYS if key in centers]
    if len(keys) != len(centers) or len(keys) < 5:
        raise ValueError('Need at least five known unique KEY_n identities for leave-one-out validation')
    reference, reference_hash = reference_points(reference_path)
    pixels = np.array([_point(centers[key]) for key in keys])
    width, height = size
    if not ((pixels >= 0).all() and (pixels[:, 0] < width).all() and (pixels[:, 1] < height).all()):
        raise ValueError('Calibration centers are outside original image')
    millimeters = np.array([reference[key] for key in keys])
    matrix, mask = _fit(pixels, millimeters, ransac_threshold_mm)
    if not mask.all():
        rejected = [key for key, inlier in zip(keys, mask) if not inlier]
        raise ValueError(f'Calibration has inconsistent identities/outliers: {rejected}')
    errors = {}
    for i, key in enumerate(keys):
        keep = np.arange(len(keys)) != i
        held_matrix, held_mask = _fit(pixels[keep], millimeters[keep], ransac_threshold_mm)
        if not held_mask.all():
            raise ValueError(f'Insufficient consistent training inliers while holding out {key}')
        predicted = transform_point(held_matrix, pixels[i])
        errors[key] = float(np.linalg.norm(np.array(predicted) - millimeters[i]))
    training = {key: float(np.linalg.norm(np.array(transform_point(matrix, pixel)) - mm))
                for key, pixel, mm in zip(keys, pixels, millimeters)}
    maximum = max(errors.values())
    document = {'schema_version': 1, 'provenance': provenance, 'model': MODEL,
        'screen': 'Driver ID', 'plane': 'right_touchscreen_keypad',
        'frame_size': list(size), 'camera': deepcopy(camera), 'origin': deepcopy(origin),
        'reference_sha256': reference_hash, 'homography': matrix.tolist(),
        'observation_summary': deepcopy(observation_summary),
        'matched_points': [{'label': key, 'pixel': pixel.tolist(), 'mm': mm.tolist()}
                           for key, pixel, mm in zip(keys, pixels, millimeters)],
        'validated_area_pixels': cv2.convexHull(pixels.astype(np.float32)).reshape(-1, 2).tolist(),
        'validation': {'method': 'leave_one_key_out', 'per_key_error_mm': errors,
            'mean_error_mm': float(np.mean(list(errors.values()))), 'max_error_mm': maximum,
            'training_error_mm': training, 'ransac_threshold_mm': ransac_threshold_mm,
            'inliers': int(mask.sum()), 'tolerance_mm': tolerance_mm,
            'tolerance_basis': tolerance_basis,
            'accepted': tolerance_mm is not None and maximum <= tolerance_mm,
            'hardware_verified': False}}
    document['calibration_id'] = _identifier(document)
    return document


def save_calibration(document: dict, path: str | Path) -> None:
    if document.get('calibration_id') != _identifier(document):
        raise ValueError('Calibration identifier does not match content')
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(document, stream, allow_nan=False, indent=2)
        stream.write('\n')


def _validate_calibration(document: dict, *, frame_size: tuple[int, int], camera: dict,
                         origin: dict, hardware: bool = False,
                         reference_path: str | Path = REFERENCE_PATH) -> None:
    """Fail closed on stale setup/reference or unaccepted/modified calibration."""
    if document.get('calibration_id') != _identifier(document):
        raise ValueError('Invalid calibration identifier/content')
    if document.get('schema_version') != 1 or document.get('model') != MODEL:
        raise ValueError('Unsupported calibration schema/model')
    if document.get('screen') != 'Driver ID' or document.get('plane') != 'right_touchscreen_keypad':
        raise ValueError('Wrong calibration screen plane')
    if document.get('provenance') not in ('simulation', 'hardware'):
        raise ValueError('Unknown calibration provenance')
    if hardware and (document['provenance'] != 'hardware' or
                     document['validation'].get('hardware_verified') is not True):
        raise ValueError('Hardware execution rejects simulation or physically unverified calibration')
    if list(_frame_size(frame_size)) != document['frame_size'] or camera != document['camera'] or origin != document['origin']:
        raise ValueError('Camera settings/mount, frame size or robot origin changed')
    if reference_points(reference_path)[1] != document['reference_sha256']:
        raise ValueError('Reference coordinates changed')
    validation = document['validation']
    tolerance = validation.get('tolerance_mm')
    if tolerance is None or validation.get('accepted') is not True:
        raise ValueError('Calibration has no accepted validation tolerance')
    _positive(tolerance, 'Acceptance tolerance')
    errors = np.array(list(validation['per_key_error_mm'].values()), dtype=float)
    if len(errors) < 5 or not np.isfinite(errors).all() or (errors < 0).any() or errors.max() > tolerance:
        raise ValueError('Invalid held-out validation errors')
    matches = document['matched_points']
    if not isinstance(matches, list) or len(matches) < 5:
        raise ValueError('Missing calibration correspondences')
    centers = {}
    reference, _ = reference_points(reference_path)
    for match in matches:
        label = match['label']
        if label not in KEYS or label in centers:
            raise ValueError('Unknown or duplicate calibration identity')
        if not np.array_equal(_point(match['mm']), _point(reference[label])):
            raise ValueError('Matched robot coordinates differ from reference')
        centers[label] = _point(match['pixel']).tolist()
    recomputed = fit_calibration(centers, frame_size=frame_size, camera=camera,
        origin=origin, ransac_threshold_mm=validation['ransac_threshold_mm'],
        tolerance_mm=tolerance, tolerance_basis=validation['tolerance_basis'],
        provenance=document['provenance'], reference_path=reference_path)
    if validation['method'] != 'leave_one_key_out' or validation['inliers'] != len(matches):
        raise ValueError('Invalid calibration validation method/inliers')
    expected = recomputed['validation']
    if validation['per_key_error_mm'].keys() != expected['per_key_error_mm'].keys():
        raise ValueError('Held-out key identities differ')
    for key, value in expected['per_key_error_mm'].items():
        if not np.isclose(validation['per_key_error_mm'][key], value, atol=1e-6, rtol=1e-6):
            raise ValueError('Stored held-out errors do not match correspondences')
    if validation.get('training_error_mm', {}).keys() != expected['training_error_mm'].keys():
        raise ValueError('Training key identities differ')
    for key, value in expected['training_error_mm'].items():
        if not np.isclose(validation['training_error_mm'][key], value, atol=1e-6, rtol=1e-6):
            raise ValueError('Incorrect training residual')
    for name in ('mean_error_mm', 'max_error_mm'):
        if not np.isclose(validation[name], expected[name], atol=1e-6, rtol=1e-6):
            raise ValueError('Incorrect held-out validation summary')
    if not np.array_equal(document['validated_area_pixels'], recomputed['validated_area_pixels']):
        raise ValueError('Validated area differs from matched keypad hull')
    for point in centers.values():
        if not np.allclose(transform_point(document['homography'], point),
                           transform_point(recomputed['homography'], point), atol=1e-6, rtol=1e-6):
            raise ValueError('Stored homography does not match correspondences')


def validate_calibration(document: dict, *, frame_size: tuple[int, int], camera: dict,
                         origin: dict, hardware: bool = False,
                         reference_path: str | Path = REFERENCE_PATH) -> None:
    if not isinstance(document, dict):
        raise ValueError("Calibration must be a JSON object")
    try:
        _validate_calibration(document, frame_size=frame_size, camera=camera,
                              origin=origin, hardware=hardware, reference_path=reference_path)
    except (KeyError, TypeError, AttributeError, IndexError, cv2.error) as exc:
        raise ValueError(f'Malformed calibration: {exc}') from exc


def load_calibration(path: str | Path, *, frame_size: tuple[int, int], camera: dict,
                     origin: dict, hardware: bool = False,
                     reference_path: str | Path = REFERENCE_PATH) -> dict:
    document = read_json(path)
    validate_calibration(document, frame_size=frame_size, camera=camera,
                         origin=origin, hardware=hardware, reference_path=reference_path)
    return document


def convert_pixel(document: dict, pixel, *, frame_size: tuple[int, int], camera: dict,
                  origin: dict, display: str = 'right', screen: str = 'Driver ID',
                  hardware: bool = False, reference_path: str | Path = REFERENCE_PATH) -> list[float]:
    validate_calibration(document, frame_size=frame_size, camera=camera, origin=origin,
                         hardware=hardware, reference_path=reference_path)
    if display != 'right' or screen != 'Driver ID':
        raise ValueError('Calibration does not validate this display/screen')
    point = _point(pixel)
    hull = np.asarray(document['validated_area_pixels'], np.float32)
    if cv2.pointPolygonTest(hull, tuple(point), False) < 0:
        raise ValueError('Target lies outside validated keypad area')
    return transform_point(document['homography'], point)


def recheck_keypad(document: dict, centers: dict, *, tolerance_px: float) -> None:
    """Required mounting/geometry recheck; resolution alone cannot detect motion."""
    if document.get('calibration_id') != _identifier(document):
        raise ValueError('Invalid calibration identifier/content')
    _positive(tolerance_px, 'Keypad recheck tolerance in pixels')
    for match in document['matched_points']:
        key = match['label']
        if key not in centers or np.linalg.norm(_point(centers[key]) - _point(match['pixel'])) > tolerance_px:
            raise ValueError(f'Keypad recheck failed: {key}')


class ValidatedCalibration:
    """Bounded conversion cache for publication; actions still use full checks."""
    def __init__(self, document: dict, *, frame_size: tuple[int, int], camera: dict,
                 origin: dict, hardware: bool = False,
                 reference_path: str | Path = REFERENCE_PATH) -> None:
        self._document = deepcopy(document)
        self._reference = Path(reference_path)
        self._context = {'frame_size': frame_size, 'camera': deepcopy(camera),
                         'origin': deepcopy(origin), 'hardware': hardware}
        validate_calibration(self._document, **self._context, reference_path=self._reference)
        self._reference_stat = self._fingerprint()
        self._conversions = {}

    def _fingerprint(self):
        stat = self._reference.stat()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    @property
    def calibration_id(self) -> str:
        return self._document['calibration_id']

    @property
    def provenance(self) -> str:
        return self._document['provenance']

    def check_context(self, *, frame_size: tuple[int, int], camera: dict, origin: dict) -> None:
        context = {'frame_size': frame_size, 'camera': camera, 'origin': origin,
                   'hardware': self._context['hardware']}
        if context != self._context or self._fingerprint() != self._reference_stat:
            validate_calibration(self._document, **context, reference_path=self._reference)
            self._context = deepcopy(context)
            self._reference_stat = self._fingerprint()
            self._conversions.clear()

    def contains(self, pixel) -> bool:
        point = _point(pixel)
        hull = np.asarray(self._document['validated_area_pixels'], np.float32)
        return cv2.pointPolygonTest(hull, tuple(point), False) >= 0

    def recheck(self, centers: dict, *, tolerance_px: float) -> None:
        recheck_keypad(self._document, centers, tolerance_px=tolerance_px)

    def convert_centers(self, centers: dict, *, frame_size: tuple[int, int], camera: dict,
                        origin: dict, display: str = 'right', screen: str = 'Driver ID') -> dict:
        self.check_context(frame_size=frame_size, camera=camera, origin=origin)
        if display != 'right' or screen != 'Driver ID':
            raise ValueError('Calibration does not validate this display/screen')
        current = {}
        hull = np.asarray(self._document['validated_area_pixels'], np.float32)
        for label, value in centers.items():
            point = _point(value)
            if cv2.pointPolygonTest(hull, tuple(point), False) < 0:
                raise ValueError('Target lies outside validated keypad area')
            key = tuple(point.tolist())
            cached = self._conversions.get(label)
            xy = cached[1] if cached is not None and cached[0] == key else transform_point(self._document['homography'], point)
            current[label] = (key, xy)
        self._conversions = current
        return {label: list(value[1]) for label, value in current.items()}

    def revalidate_for_action(self, *, frame_size: tuple[int, int], camera: dict,
                              origin: dict, hardware: bool) -> None:
        """Never use cached publication validation to authorize a physical action."""
        validate_calibration(self._document, frame_size=frame_size, camera=camera,
                             origin=origin, hardware=hardware, reference_path=self._reference)
