"""Explicit experimental reuse of an unchanged-camera recorded SENSE mapping.

The original candidate is validated for integrity, never promoted or rewritten.
Numerical accuracy and keypad-only coverage are waived for the operator-authorized
whole-SENSE test. Live evidence, measured monitor bounds and robot travel remain
mandatory. Extrapolated accuracy is never presented as validated coverage.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import time
from uuid import uuid4

import cv2
import numpy as np

from dmi_robot_master.integration.actions import rounded_mm
from dmi_robot_master.integration.calibration import transform_point
from dmi_robot_master.integration.move_only import _load
from dmi_robot_master.integration.publication import project_pixels
from dmi_robot_master.integration.sense_calibration import REFERENCE_PATH, _geometry, validate_offline
from dmi_robot_master.integration.targets import TargetProjector


def _covered(document, target, recorded_pixel):
    if target['kind'] != 'button' or target['display'] not in ('left', 'right'):
        return False
    return cv2.pointPolygonTest(np.asarray(document['geometry'][target['display']], np.float32),
                               tuple(map(float, recorded_pixel)), False) >= 0


class RecordedTestProjector(TargetProjector):
    """Same observation interface and detector; a visibly unverified XY projector."""
    def __init__(self, source_info, calibration_path, origin_epoch):
        super().__init__(source_info=source_info, calibration_path=calibration_path, geometry_tolerance_px=4.)
        self.origin_epoch = origin_epoch
        self._recorded_stamp = None
        self._recorded_document = None
        self._recorded_digest = None
        self._view_anchor = None
        self.load()

    def load(self):
        stamp = tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns)
                      for p in (self.calibration_path, REFERENCE_PATH))
        if stamp != self._recorded_stamp:
            document, digest = _load(self.calibration_path)
            validate_offline(document)
            # A keypad fit must not be extrapolated through its projective horizon.
            corners = np.asarray(document['geometry']['left'] + document['geometry']['right'])
            denominators = np.column_stack((corners, np.ones(len(corners)))) @ np.asarray(
                document['models']['homography']['matrix'])[2]
            if not ((denominators > 1e-9).all() or (denominators < -1e-9).all()):
                raise ValueError('Saved homography is not finite across the SENSE monitor')
            if self.source_info.get('kind') != 'remote_bridge' or self.source_info.get('simulation') is not False:
                raise ValueError('Recorded experimental pressing requires the live Pi HTTP camera')
            settings = document['camera']['settings']
            if (self.source_info.get('rotation_clockwise', 0) != settings['rotation_clockwise']
                    or self.source_info.get('mirror_horizontal', False) != settings['mirror_horizontal']
                    or settings.get('crop') is not None):
                raise ValueError('Camera rotation/crop differs from the recorded mapping')
            self._view_anchor = None
            self._recorded_document, self._recorded_digest = document, digest
            self.context = {'camera': deepcopy(document['camera']), 'origin': deepcopy(document['origin'])}
            self._recorded_stamp = stamp
        return self._recorded_document, self._recorded_digest

    def registration(self, document, geometry, frame_size, *, require_left=False):
        """Map measured current right-plane borders into the recorded pixel plane.

        The session may begin with a differently framed view. Once established,
        its measured joined-region geometry may drift by at most the existing
        four-pixel tolerance. A larger change requires an explicit camera restart.
        """
        if list(frame_size) != document['frame_size']:
            raise ValueError('Current image size differs from the recorded mapping')
        measured = _geometry(geometry, frame_size)
        if self._view_anchor is not None and any(
                np.max(np.abs(np.asarray(measured[side])-self._view_anchor[side])) > 4
                for side in ('left', 'right')):
            raise ValueError('View changed since camera start; stop/start camera to register its measured borders again')
        current = np.asarray(measured['right'], np.float32)
        recorded = np.asarray(document['geometry']['right'], np.float32)
        if cv2.contourArea(current, oriented=True) * cv2.contourArea(recorded, oriented=True) <= 0:
            raise ValueError('Current monitor corner orientation differs from the recorded view')
        matrix = cv2.getPerspectiveTransform(current, recorded)
        if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-12:
            raise ValueError('Current measured monitor cannot define a finite view registration')
        if require_left:
            registered_left = np.asarray([transform_point(matrix, pixel) for pixel in measured['left']])
            if np.max(np.abs(registered_left - np.asarray(document['geometry']['left']))) > 4:
                raise ValueError('Measured left borders do not agree with the saved SENSE mapping within 4 px')
        if self._view_anchor is None:
            self._view_anchor = deepcopy(measured)
        return matrix

    def project(self, result, evidence, *, frame_size):
        snapshot = project_pixels(result, frame_size=frame_size)
        snapshot.update(simulation=False, calibration_valid=False, calibration_provenance='recorded_experimental',
                        experimental_recorded_test=True)
        for target in snapshot['targets'].values():
            target.update(mm=None, usable=False)
        try:
            document, _ = self.load()
            if result['right_display']['visibility'] != 'clear':
                raise ValueError('Clear measured monitor geometry is required for experimental projection')
            geometry = {side: result[f'{side}_display']['geometry']['corners'] for side in ('left', 'right')}
            registration = self.registration(document, geometry, frame_size)
            snapshot.update(calibration_id=document['calibration_id'],
                            experimental_max_error_mm=document['models']['homography']['max_error_mm'],
                            experimental_view_registration=registration.tolist())
            for target in snapshot['targets'].values():
                if target['kind'] != 'button' or target['display'] not in ('left', 'right'):
                    continue
                current_region = np.asarray(geometry[target['display']], np.float32)
                if cv2.pointPolygonTest(current_region, tuple(map(float, target['pixel'])), False) < 0:
                    continue
                if target['display'] == 'left':
                    try:
                        self.registration(document, geometry, frame_size, require_left=True)
                    except ValueError as exc:
                        target['mapping_error'] = str(exc)
                        continue
                # Output pixel centres stay in the current original image. Only
                # the transform input/coverage test uses registered coordinates.
                recorded_pixel = transform_point(registration, target['pixel'])
                if _covered(document, target, recorded_pixel):
                    target['mm'] = transform_point(document['models']['homography']['matrix'], recorded_pixel)
            self.error = None
        except (OSError, ValueError, KeyError, TypeError, cv2.error) as exc:
            self.error = str(exc)
            for target in snapshot['targets'].values():
                target.update(mm=None, usable=False)
            snapshot['calibration_id'] = None
        return snapshot, {}


def _xy(observer, sample, document, origin_epoch):
    projector = observer.projector
    if (projector.origin_epoch != origin_epoch or sample['source_info'] != projector.source_info
            or sample['source_info'].get('kind') != 'remote_bridge'
            or sample['source_info'].get('simulation') is not False):
        raise ValueError('Experimental camera source or robot origin changed; restart observation')
    if (sample['frame_size'] != document['frame_size'] or sample.get('calibration_id') != document['calibration_id']
            or sample.get('calibration_error') is not None):
        raise ValueError('Recorded mapping does not match the current frame/calibration')
    target = sample['target']
    registration = projector.registration(document, sample['geometry'], sample['frame_size'],
                                          require_left=target['display'] == 'left')
    if (sample.get('visibility') != 'clear' or sample.get('direct_visibility') != 'clear'
            or sample['screen'] == 'unknown' or sample.get('direct_screen') != sample['screen']):
        raise ValueError('No clear current direct screen evidence')
    recorded_pixel = transform_point(registration, target['pixel'])
    if not _covered(document, target, recorded_pixel) or target.get('active', True) is not True:
        raise ValueError('Selected button is inactive, uncertain or outside measured SENSE monitor bounds')
    name = f"digit_{target['label'][4:]}" if target['label'].startswith('KEY_') else target['label'].rsplit('/', 1)[-1]
    raw = sample.get('direct_buttons', {}).get(name)
    if (raw is None or len(raw) != 2 or not all(math.isfinite(v) for v in raw)
            or max(abs(a-b) for a,b in zip(raw, target['pixel'])) > 4):
        raise ValueError('Selected button lacks matching current direct evidence')
    xy = transform_point(document['models']['homography']['matrix'], recorded_pixel)
    if target.get('mm') is None or not np.allclose(target['mm'], xy, atol=1e-6, rtol=1e-6):
        raise ValueError('Current target has no matching experimental XY')
    return xy


@dataclass(frozen=True)
class RecordedPressPlan:
    token: str
    created_at: float
    origin_epoch: str
    selection: tuple
    calibration_path: str
    calibration_sha256: str
    anchor_json: str
    command_xy: tuple
    predicted_xy: tuple
    limits: tuple
    max_error_mm: float
    kind: str = 'single_press'
    duration_ms: int = 100

    def preview(self):
        return {'token': self.token, 'selection': list(self.selection),
            'pixel': json.loads(self.anchor_json)['target']['pixel'], 'predicted_xy_mm': list(self.predicted_xy),
            'command_xy_mm': list(self.command_xy), 'calibration_sha256': self.calibration_sha256,
            'numerical_max_error_mm': self.max_error_mm, 'duration_ms': self.duration_ms,
            'action_kind': self.kind, 'experimental_recorded_test': True, 'calibration_model': 'homography + measured view registration',
            'calibration_hardware_verified': False, 'physical_verified': False, 'simulation_only': False,
            'commissioning_only': True, 'normal_action_ready': False, 'hardware_press_enabled': True,
            'independent_envelope': {'minimum_xy_mm': [0, 0],
                'maximum_xy_mm': [v-1 for v in self.limits],
                'maximum_move_mm': math.hypot(*(v-1 for v in self.limits))},
            'bounds_basis': 'Existing configured robot limits, confirmed by operator; not fit-derived'}

    def resolve(self, observer, *, origin_epoch, limits, position=None):
        if (type(observer.projector) is not RecordedTestProjector or origin_epoch != self.origin_epoch
                or tuple(limits) != self.limits or not 0 <= time.monotonic()-self.created_at <= 30
                or self.kind != 'single_press' or self.duration_ms != 100):
            raise ValueError('Experimental press intent expired or robot/context changed')
        document, digest = observer.projector.load()
        if str(observer.projector.calibration_path) != self.calibration_path or digest != self.calibration_sha256:
            raise ValueError('Recorded mapping changed after preview')
        sample = observer.calibration_sample(*self.selection)
        anchor = json.loads(self.anchor_json)
        if (sample['source_info'] != anchor['source_info']
                or sample['target'].get('active') != anchor['target'].get('active')
                or max(abs(a-b) for a,b in zip(sample['target']['pixel'], anchor['target']['pixel'])) > 4
                or any(np.max(np.abs(np.asarray(sample['geometry'][s])-anchor['geometry'][s])) > 4 for s in ('left','right'))):
            raise ValueError('Selected target/source/geometry changed after preview')
        xy = _xy(observer, sample, document, origin_epoch)
        command = tuple(rounded_mm(v) for v in xy)
        if command != self.command_xy or any(not 0 <= v < limit for v,limit in zip(xy, limits)):
            raise ValueError('Current destination changed or exceeds configured robot travel')
        from dmi_robot_common.command_validation import validate_command
        from dmi_robot_common.DmiMessages import DmiMessages
        validate_command(DmiMessages.MOVE_AND_CLICK, [*command, 100], limits)
        if position is not None and (len(position) != 2 or any(type(v) is not int or not 0 <= v < limit for v,limit in zip(position, limits))):
            raise ValueError('Starting position exceeds configured robot travel')
        if position is not None and math.dist(position, command) > math.hypot(*(v-1 for v in limits)):
            raise ValueError('Movement distance exceeds configured robot travel')
        age = time.monotonic()-sample['received_at']+sample['upstream_age_seconds']
        current = observer.snapshot()
        if (not 0 <= age <= 1.5 or not current['fresh'] or current['session_id'] != self.selection[0]
                or current['capture_index'] != sample['capture_index']
                or current['projection']['screen'] != self.selection[1]):
            raise ValueError('Direct target evidence expired before experimental press')
        return command


def prepare_recorded_press(observer, selection, *, origin_epoch, limits):
    document, digest = observer.projector.load()
    sample = observer.calibration_sample(*selection)
    xy = _xy(observer, sample, document, origin_epoch)
    plan = RecordedPressPlan(uuid4().hex, time.monotonic(), origin_epoch, tuple(selection),
        str(observer.projector.calibration_path), digest, json.dumps(sample, allow_nan=False),
        tuple(rounded_mm(v) for v in xy), tuple(xy), tuple(limits), document['models']['homography']['max_error_mm'])
    plan.resolve(observer, origin_epoch=origin_epoch, limits=limits)
    return plan
