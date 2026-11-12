"""Explicit experimental reuse of an unchanged-camera recorded SENSE mapping.

The original candidate is validated for integrity, never promoted or rewritten.
Numerical accuracy and keypad-only coverage are waived for the operator-authorized
whole-SENSE test. Live evidence, measured monitor bounds and robot travel remain
mandatory. Extrapolated accuracy is never presented as validated coverage.
"""
from copy import deepcopy
from collections import deque
from dataclasses import dataclass
from itertools import combinations
import json
import math
import time
from threading import Lock
from uuid import uuid4

import cv2
import numpy as np

from dmi_robot_master.integration.actions import rounded_mm
from dmi_robot_master.integration.calibration import read_json, transform_point
from dmi_robot_master.integration.move_only import _load
from dmi_robot_master.integration.publication import project_pixels
from dmi_robot_master.integration.sense_calibration import ALIASES, MODEL, REFERENCE_PATH, _geometry, validate_offline
from dmi_robot_master.integration.targets import TargetProjector


def _covered(document, target, recorded_pixel):
    if target['kind'] != 'button' or target['display'] not in ('left', 'right'):
        return False
    return cv2.pointPolygonTest(np.asarray(document['geometry'][target['display']], np.float32),
                               tuple(map(float, recorded_pixel)), False) >= 0


def _inspection_reference(reference, screen, target):
    """Explicit read-only reference identities; never detected/action coordinates."""
    key = None
    if (target['display'] == 'left' and target['kind'] == 'button'
            and target['label'] == 'left/button/yes'):
        key = ALIASES.get((screen, 'left', 'button', 'yes'))
    elif (target['display'] == 'left' and target['kind'] == 'box'
            and target['label'] == 'left/box/box_16'
            and screen in ('Driver ID', 'Level', 'Main', 'Train Running Number')):
        key = ('ACK_SCREEN', 'ACK')
    if key is None:
        return None
    entry = reference[MODEL]['screens'][key[0]]['buttons'][key[1]]
    return {'reference_identity': list(key), 'reference_xy_mm': [entry['x'], entry['y']]}


class RecordedTestProjector(TargetProjector):
    """Same observation interface and detector; a visibly unverified XY projector."""
    experimental_recorded_test = True  # Stable mode identity, including while XY is invalidated.

    def __init__(self, source_info, calibration_path, origin_epoch, *, stable_registration=False,
                 recover_alignment=False, allow_unverified_left=False):
        if recover_alignment and not stable_registration:
            raise ValueError('Alignment recovery requires fixed session registration')
        if allow_unverified_left and not stable_registration:
            raise ValueError('Unverified left-button testing requires fixed session registration')
        super().__init__(source_info=source_info, calibration_path=calibration_path, geometry_tolerance_px=4.)
        self.origin_epoch = origin_epoch
        self._recorded_stamp = None
        self._recorded_document = None
        self._recorded_digest = None
        self.stable_registration = stable_registration
        self.recover_alignment = recover_alignment
        self.allow_unverified_left = allow_unverified_left
        self._recorded_reference = None
        self._registration_lock = Lock()
        self._registration_epoch = 0
        self._registration_setups = 0
        self.reset_registration()
        self.load()

    def reset_registration(self):
        """Explicit new setup/origin: no old matrix or observations may survive."""
        with self._registration_lock:
            self._registration_setups += 1
            self._clear_registration()

    def _clear_registration(self):
        """Caller holds the short state lock; no loading or geometry work here."""
        self._registration_epoch += 1
        self._view_anchor = None
        self._session_registration = None
        self._registration_samples = deque(maxlen=5)
        self._registration_context = None
        self._registration_session = None
        self._registration_index = -1
        self._registration_receipt = None
        self._registration_id = None
        self._registration_invalidated = False
        self._registration_invalid_reason = None
        self._registration_state = 'acquiring'
        self._registration_reason = 'Waiting for three consistent current monitor measurements'

    def _registration_basis(self):
        return (json.dumps(self.source_info, sort_keys=True), self.origin_epoch,
                self._recorded_digest, str(self.calibration_path),
                json.dumps(self.context, sort_keys=True), self.recover_alignment,
                self.allow_unverified_left)

    @staticmethod
    def _close_geometry(a, b):
        return all(np.max(np.abs(np.asarray(a[s])-b[s])) <= 4 for s in ('left', 'right'))

    def _aligned_geometry(self, a, b):
        # Operator-approved fixed-setup experiment only. Acquisition and direct
        # target evidence retain their separate four-pixel consistency bounds.
        if not self.recover_alignment:
            return self._close_geometry(a, b)
        return all(np.max(np.abs(np.asarray(a[s])-b[s])) <= 20 for s in ('left', 'right'))

    @staticmethod
    def _median_geometry(group):
        return {s: np.median([g[s] for g in group], axis=0).tolist() for s in ('left', 'right')}

    @staticmethod
    def _finite_monitor(document, matrix, geometry):
        corners = np.asarray(geometry['left']+geometry['right'])
        calibration = np.asarray(document['models']['homography']['matrix'])
        for transform in (matrix, calibration @ matrix):
            denominators = np.column_stack((corners, np.ones(8))) @ transform[2]
            if not ((denominators > 1e-9).all() or (denominators < -1e-9).all()):
                raise ValueError('Registration is not finite across the SENSE monitor')

    def invalidate_registration(self, reason):
        """Latch invalidation without waiting for loading or geometry work."""
        with self._registration_lock:
            self._invalidate_registration(reason)

    def _invalidate_registration(self, reason):
        """Caller holds the state lock."""
        self._registration_epoch += 1
        self._registration_invalidated = True
        self._registration_invalid_reason = reason+'; stop/start observation to register again'
        self._registration_samples.clear()
        self._session_registration = None
        self._registration_state = 'invalidated'
        self._registration_reason = self._registration_invalid_reason

    def _evaluate_registration(self, document, samples, anchor, needs_matrix, frame_size, *, recovering=False):
        """Calculate a proposed update from detached bounded state; no writes."""
        matrix = None
        if needs_matrix:
            for group in reversed(list(combinations(samples, 3))):
                median = self._median_geometry(group)
                if not all(self._close_geometry(item, median) for item in group):
                    continue
                anchor = _geometry(median, frame_size)
                matrix = self._view_matrix(document, anchor)
                self._finite_monitor(document, matrix, anchor)
                break
            if matrix is None:
                return anchor, None, 'acquiring', 'Waiting for three consistent current monitor measurements', None
        if not self._aligned_geometry(samples[-1], anchor):
            group = samples[-3:]
            median = self._median_geometry(group)
            moved = (len(group) == 3 and all(not self._aligned_geometry(g, anchor) for g in group)
                     and not self._aligned_geometry(median, anchor)
                     and all(self._close_geometry(g, median) for g in group))
            return (anchor, matrix, 'alignment_pending', 'Monitor alignment uncertain; mapping suspended',
                    'Confirmed monitor movement' if moved and not self.recover_alignment else None)
        if self.recover_alignment and recovering and not needs_matrix:
            good = [g for g in samples[:-1] if self._aligned_geometry(g, anchor)]
            consistent = any(all(self._close_geometry(g, self._median_geometry(group)) for g in group)
                             for pair in combinations(good, 2) for group in [(*pair, samples[-1])])
            if not consistent:
                return anchor, None, 'alignment_pending', 'Waiting for three fresh measurements agreeing with the original monitor pose', None
        return anchor, matrix, 'locked', None, None

    def observe_geometry(self, observation):
        """Only the full worker admits fresh geometry, never inspection reads.

        Snapshot and commit are short and atomic. File/geometry work runs outside
        the lock; an intervening invalidation or reset discards that entire update.
        """
        if not self.stable_registration:
            return
        with self._registration_lock:
            epoch = self._registration_epoch
            setup = self._registration_setups
        geometry_check = False
        try:
            document, digest = self.load()
            with self._registration_lock:
                if self._registration_invalidated or setup != self._registration_setups:
                    return
                if document is not self._recorded_document or digest != self._recorded_digest:
                    return
                epoch = self._registration_epoch
                old_context, old_session = self._registration_context, self._registration_session
                last_index, last_receipt = self._registration_index, self._registration_receipt
                samples = list(self._registration_samples)
                anchor = deepcopy(self._view_anchor)
                needs_matrix = self._session_registration is None
                recovering = self._registration_state == 'alignment_pending'
            basis = self._registration_basis()
            session = (observation.source_id, observation.session_id, observation.frame_size)
            if ((old_context is not None and basis != old_context)
                    or (old_session is not None and session != old_session)):
                with self._registration_lock:
                    if epoch == self._registration_epoch and not self._registration_invalidated:
                        self._invalidate_registration('Registration source, session or origin changed')
                return
            age = time.monotonic()-observation.received_at+observation.upstream_age_seconds
            if not math.isfinite(age) or not 0 <= age <= 1.5:
                with self._registration_lock:
                    if epoch == self._registration_epoch and not self._registration_invalidated:
                        self._registration_epoch += 1
                        self._registration_samples.clear()
                        self._registration_state = 'alignment_pending'
                        self._registration_reason = 'Registration requires fresh measured geometry'
                return
            if (observation.capture_index <= last_index or
                    (last_receipt is not None and observation.received_at <= last_receipt)):
                return
            if list(observation.frame_size) != document['frame_size']:
                raise ValueError('Current image size differs from the recorded mapping')
            geometry_check = True
            raw = (observation.layout_evidence or {}).get('monitor_geometry', {})
            if (observation.direct_evidence.get('right_visibility') != 'clear'
                    or any(observation.result[s+'_display'].get('visibility', 'clear') != 'clear'
                           for s in ('left', 'right'))):
                raise ValueError('Clear current measured monitor geometry is required')
            measured = _geometry({s: raw[s+'_display']['corners'] for s in ('left', 'right')},
                                 observation.frame_size)
            if last_receipt is not None and observation.received_at-last_receipt > 1.5:
                samples.clear()
            samples = (samples+[measured])[-5:]
            anchor, matrix, state, reason, invalid = self._evaluate_registration(
                document, samples, anchor, needs_matrix, observation.frame_size, recovering=recovering)
            with self._registration_lock:
                if (epoch != self._registration_epoch or self._registration_invalidated
                        or observation.capture_index <= self._registration_index
                        or (self._registration_receipt is not None and
                            observation.received_at <= self._registration_receipt)):
                    return
                if invalid:
                    self._invalidate_registration(invalid)
                    return
                # Another acquisition cannot replace a matrix established since
                # this calculation's snapshot (the full worker is its sole owner).
                if matrix is not None and self._session_registration is not None:
                    return
                self._registration_context, self._registration_session = basis, session
                self._registration_index, self._registration_receipt = observation.capture_index, observation.received_at
                self._registration_samples = deque(samples, maxlen=5)
                if (self.recover_alignment and state == 'alignment_pending'
                        and self._registration_state != 'alignment_pending'):
                    self._registration_samples.clear()
                if matrix is not None:
                    self._view_anchor, self._session_registration = anchor, matrix
                    self._registration_id = uuid4().hex
                if state != self._registration_state and self._session_registration is not None:
                    self._registration_epoch += 1
                self._registration_state, self._registration_reason = state, reason
        except (OSError, ValueError, KeyError, TypeError, cv2.error) as exc:
            with self._registration_lock:
                if epoch != self._registration_epoch or self._registration_invalidated:
                    return
                if self._view_anchor is not None:
                    if self.recover_alignment and geometry_check:
                        self._registration_epoch += 1
                        self._registration_samples.clear()
                        self._registration_state = 'alignment_pending'
                        self._registration_reason = str(exc)+'; waiting for the original monitor pose'
                    else:
                        self._invalidate_registration(str(exc))
                else:
                    self._registration_samples.clear()
                    self._registration_state, self._registration_reason = 'acquiring', str(exc)

    def load(self):
        with self._registration_lock:
            invalidations = self._registration_epoch
        stamp = tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns)
                      for p in (self.calibration_path, REFERENCE_PATH))
        if stamp != self._recorded_stamp:
            document, digest = _load(self.calibration_path)
            validate_offline(document)
            reference = read_json(REFERENCE_PATH) if self.stable_registration else None
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
            with self._registration_lock:
                # Loading/validation ran outside the lock. A concurrent stop or
                # origin invalidation must survive this older reload operation.
                if (invalidations == self._registration_epoch
                        and not self._registration_invalidated):
                    self._clear_registration()
                else:
                    self._registration_epoch += 1
                self._recorded_document, self._recorded_digest = document, digest
                self._recorded_reference = reference
                self.context = {'camera': deepcopy(document['camera']), 'origin': deepcopy(document['origin'])}
                self._recorded_stamp = stamp
        with self._registration_lock:
            return self._recorded_document, self._recorded_digest

    @staticmethod
    def _view_matrix(document, measured):
        current = np.asarray(measured['right'], np.float32)
        recorded = np.asarray(document['geometry']['right'], np.float32)
        if cv2.contourArea(current, oriented=True) * cv2.contourArea(recorded, oriented=True) <= 0:
            raise ValueError('Current monitor corner orientation differs from the recorded view')
        matrix = cv2.getPerspectiveTransform(current, recorded)
        if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-12:
            raise ValueError('Current measured monitor cannot define a finite view registration')
        return matrix

    @staticmethod
    def _left_border_disagreement(document, matrix, measured):
        registered = np.asarray([transform_point(matrix, pixel) for pixel in measured['left']])
        return float(np.max(np.abs(registered - np.asarray(document['geometry']['left']))))

    def _registered_view(self, document, geometry, frame_size, *, require_left=False):
        """Snapshot matrix/anchor/identity atomically; validate geometry outside."""
        if list(frame_size) != document['frame_size']:
            raise ValueError('Current image size differs from the recorded mapping')
        measured = _geometry(geometry, frame_size)
        if self.stable_registration:
            with self._registration_lock:
                if document['calibration_id'] != self._recorded_document['calibration_id']:
                    raise ValueError('Recorded model changed during projection')
                basis = self._registration_basis()
                if self._session_registration is not None and self._registration_context != basis:
                    self._invalidate_registration('Registration model, source or origin changed')
                if self._registration_invalidated:
                    raise ValueError(self._registration_invalid_reason)
                if self._registration_state != 'locked' or self._session_registration is None:
                    raise ValueError(self._registration_reason)
                matrix = self._session_registration.copy()
                anchor = deepcopy(self._view_anchor)
                registration_id, epoch = self._registration_id, self._registration_epoch
        else:
            anchor, registration_id, epoch = self._view_anchor, None, None
        if anchor is not None and not self._aligned_geometry(measured, anchor):
            raise ValueError('View changed since camera start; stop/start camera to register its measured borders again')
        if not self.stable_registration:
            matrix = self._view_matrix(document, measured)
        else:
            self._finite_monitor(document, matrix, measured)
        if require_left:
            discrepancy = self._left_border_disagreement(document, matrix, measured)
            if discrepancy > 4 and not self.allow_unverified_left:
                raise ValueError('Measured left borders do not agree with the saved SENSE mapping within 4 px')
        if self.stable_registration:
            with self._registration_lock:
                if (epoch != self._registration_epoch or self._registration_invalidated
                        or self._registration_state != 'locked'):
                    raise ValueError(self._registration_invalid_reason or 'Registration changed during projection')
        elif self._view_anchor is None:
            self._view_anchor = deepcopy(measured)
        return matrix, registration_id, epoch

    def registration(self, document, geometry, frame_size, *, require_left=False):
        """Return a detached matrix; reads never acquire or refresh registration."""
        return self._registered_view(document, geometry, frame_size, require_left=require_left)[0]

    def project(self, result, evidence, *, frame_size):
        snapshot = project_pixels(result, frame_size=frame_size)
        snapshot.update(simulation=False, calibration_valid=False, calibration_provenance='recorded_experimental',
                        experimental_recorded_test=True)
        for target in snapshot['targets'].values():
            target.update(mm=None, usable=False)
        epoch = None
        try:
            document, _ = self.load()
            if self.stable_registration:
                with self._registration_lock:
                    reference = self._recorded_reference
                for target in snapshot['targets'].values():
                    info = _inspection_reference(reference, snapshot['screen'], target)
                    if info is not None:
                        target.update(info)
            if result['right_display']['visibility'] != 'clear':
                raise ValueError('Clear measured monitor geometry is required for experimental projection')
            geometry = {side: result[f'{side}_display']['geometry']['corners'] for side in ('left', 'right')}
            registration, registration_id, epoch = self._registered_view(document, geometry, frame_size)
            snapshot.update(calibration_id=document['calibration_id'],
                            experimental_max_error_mm=document['models']['homography']['max_error_mm'],
                            experimental_view_registration=registration.tolist())
            left_disagreement = (self._left_border_disagreement(document, registration, geometry)
                                 if self.stable_registration else None)
            for target in snapshot['targets'].values():
                if target['display'] == 'left' and left_disagreement is not None:
                    target['left_border_disagreement_px'] = left_disagreement
                if ('reference_xy_mm' in target and target['display'] == 'left'
                        and cv2.pointPolygonTest(np.asarray(geometry['left'], np.float32),
                            tuple(map(float, target['pixel'])), False) >= 0):
                    probe = transform_point(registration, target['pixel'])
                    if cv2.pointPolygonTest(np.asarray(document['geometry']['left'], np.float32), probe, False) >= 0:
                        target['inspection_xy_mm'] = transform_point(document['models']['homography']['matrix'], probe)
                        target['reference_error_mm'] = math.dist(target['inspection_xy_mm'], target['reference_xy_mm'])
                        if target['kind'] == 'box':
                            try:
                                self.registration(document, geometry, frame_size, require_left=True)
                            except ValueError as exc:
                                target['mapping_error'] = str(exc)
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
            if self.stable_registration:
                with self._registration_lock:
                    if (epoch != self._registration_epoch or self._registration_invalidated
                            or self._registration_state != 'locked'):
                        raise ValueError(self._registration_invalid_reason or 'Registration changed during projection')
                    snapshot['experimental_registration_id'] = registration_id
            self.error = None
        except (OSError, ValueError, KeyError, TypeError, cv2.error) as exc:
            self.error = str(exc)
            for target in snapshot['targets'].values():
                target.update(mm=None, usable=False)
                target.pop('inspection_xy_mm', None)
                target.pop('reference_error_mm', None)
                target.pop('left_border_disagreement_px', None)
            snapshot['calibration_id'] = None
            if self.stable_registration:
                snapshot.pop('experimental_view_registration', None)
        if self.stable_registration:
            with self._registration_lock:
                if epoch is not None and (epoch != self._registration_epoch or self._registration_invalidated
                                          or self._registration_state != 'locked'):
                    self.error = self._registration_invalid_reason or 'Registration changed during projection'
                    for target in snapshot['targets'].values():
                        target.update(mm=None, usable=False)
                        target.pop('inspection_xy_mm', None)
                        target.pop('reference_error_mm', None)
                        target.pop('left_border_disagreement_px', None)
                    snapshot['calibration_id'] = None
                    snapshot.pop('experimental_view_registration', None)
                snapshot.update(experimental_registration_id=self._registration_id,
                                experimental_registration_state=self._registration_state,
                                experimental_registration_samples=len(self._registration_samples),
                                experimental_alignment_recovery=self.recover_alignment,
                                experimental_monitor_tolerance_px=20 if self.recover_alignment else 4)
                snapshot['experimental_allow_unverified_left'] = self.allow_unverified_left
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
    if (projector.stable_registration and
            sample.get('experimental_registration_id') != projector._registration_id):
        raise ValueError('Selected target belongs to another session registration')
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
    one_click: bool = False

    def preview(self):
        anchor = json.loads(self.anchor_json)
        return {'token': self.token, 'selection': list(self.selection),
            'pixel': anchor['target']['pixel'], 'predicted_xy_mm': list(self.predicted_xy),
            **({key: anchor[key] for key in ('experimental_monitor_tolerance_px', 'experimental_alignment_recovery')
                if key in anchor}),
            **({key: anchor[key] for key in ('experimental_allow_unverified_left',
                                            'experimental_left_border_disagreement_px') if key in anchor}),
            'command_xy_mm': list(self.command_xy), 'calibration_sha256': self.calibration_sha256,
            'numerical_max_error_mm': self.max_error_mm, 'duration_ms': self.duration_ms,
            'action_kind': self.kind, 'experimental_recorded_test': True, 'calibration_model': 'homography + measured view registration',
            'calibration_hardware_verified': False, 'physical_verified': False, 'simulation_only': False,
            'commissioning_only': True, 'normal_action_ready': False, 'hardware_press_enabled': True,
            'independent_envelope': {'minimum_xy_mm': [0, 0],
                'maximum_xy_mm': [v-1 for v in self.limits],
                'maximum_move_mm': math.hypot(*(v-1 for v in self.limits))},
            'bounds_basis': 'Existing configured robot limits, confirmed by operator; not fit-derived'}

    def resolve(self, observer, *, origin_epoch, limits, position=None, with_sample=False):
        if (type(observer.projector) is not RecordedTestProjector or origin_epoch != self.origin_epoch
                or tuple(limits) != self.limits or not 0 <= time.monotonic()-self.created_at <= 30
                or self.kind != 'single_press' or self.duration_ms != 100):
            raise ValueError('Experimental press intent expired or robot/context changed')
        document, digest = observer.projector.load()
        if str(observer.projector.calibration_path) != self.calibration_path or digest != self.calibration_sha256:
            raise ValueError('Recorded mapping changed after preview')
        sample = (observer.experimental_press_sample(*self.selection) if self.one_click
                  else observer.calibration_sample(*self.selection))
        anchor = json.loads(self.anchor_json)
        if (sample['source_info'] != anchor['source_info']
                or sample.get('experimental_registration_id') != anchor.get('experimental_registration_id')
                or sample['target'].get('active') != anchor['target'].get('active')
                or (not self.one_click and max(abs(a-b) for a,b in zip(sample['target']['pixel'], anchor['target']['pixel'])) > 4)
                or any(np.max(np.abs(np.asarray(sample['geometry'][s])-anchor['geometry'][s])) > 4 for s in ('left','right'))):
            raise ValueError('Selected target/source/geometry changed after preview')
        xy = _xy(observer, sample, document, origin_epoch)
        command = tuple(rounded_mm(v) for v in xy)
        if ((not self.one_click and command != self.command_xy)
                or any(not 0 <= v < limit for v,limit in zip(xy, limits))):
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
                or current['capture_index'] != sample.get('latest_capture_index', sample['capture_index'])
                or current.get('calibration_error')
                or current['projection']['screen'] != self.selection[1]):
            raise ValueError('Direct target evidence expired before experimental press')
        return (command, sample) if with_sample else command


def prepare_recorded_press(observer, selection, *, origin_epoch, limits, one_click=False):
    document, digest = observer.projector.load()
    sample = (observer.experimental_press_sample(*selection) if one_click
              else observer.calibration_sample(*selection))
    xy = _xy(observer, sample, document, origin_epoch)
    if observer.projector.stable_registration:
        sample.update(experimental_alignment_recovery=observer.projector.recover_alignment,
                      experimental_monitor_tolerance_px=20 if observer.projector.recover_alignment else 4,
                      experimental_allow_unverified_left=observer.projector.allow_unverified_left)
        if sample['target'].get('left_border_disagreement_px') is not None:
            sample['experimental_left_border_disagreement_px'] = sample['target']['left_border_disagreement_px']
    plan = RecordedPressPlan(uuid4().hex, time.monotonic(), origin_epoch, tuple(selection),
        str(observer.projector.calibration_path), digest, json.dumps(sample, allow_nan=False),
        tuple(rounded_mm(v) for v in xy), tuple(xy), tuple(limits), document['models']['homography']['max_error_mm'],
        one_click=one_click)
    plan.resolve(observer, origin_epoch=origin_epoch, limits=limits)
    return plan
