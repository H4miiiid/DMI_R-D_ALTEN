"""One explicitly confirmed commissioning move; never a calibration promotion.

Ordinary calibrated motion remains unavailable for schema-3 inspection candidates.
Commissioning additionally needs an independently measured convex XY envelope.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time
from uuid import uuid4

import cv2
import numpy as np

from dmi_robot_master.integration.actions import rounded_mm
from dmi_robot_master.integration.calibration import MODEL, read_json, transform_point
from dmi_robot_master.integration.guided_calibration import validate_guided

MOVE_CHECKS = ('z_retracted', 'path_clear', 'starting_position_verified',
               'stop_mechanism_available', 'independent_bounds_verified')


def _load(path):
    path = Path(path).expanduser().resolve()
    raw = path.read_bytes()
    # Use the shared strict JSON reader (duplicate keys are rejected).
    document = read_json(path)
    if path.read_bytes() != raw:
        raise ValueError('Configuration changed while reading; prepare again')
    return document, hashlib.sha256(raw).hexdigest()


def _xy(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('Expected finite XY millimeters')
    return value


def _validate_envelope(document, context, limits):
    """Independent absolute rectangle and maximum displacement, never fit-derived."""
    if (document.get('schema_version') != 1 or document.get('model') != MODEL or
            document.get('commissioning_only') is not True or
            document.get('coordinates') != 'absolute_robot_xy_mm' or
            document.get('origin') != context['origin'] or
            document.get('camera') != {k:context['camera'][k] for k in ('identity','mount_id')} or
            not isinstance(document.get('measurement_basis'), str) or not document['measurement_basis'].strip()):
        raise ValueError('Configure an independently measured commissioning envelope for this camera/origin')
    lower, upper = _xy(document['minimum_xy_mm']), _xy(document['maximum_xy_mm'])
    distance = document['maximum_move_mm']
    if (any(not 0 <= lo < hi < limit for lo, hi, limit in zip(lower, upper, limits)) or
            type(distance) not in (int, float) or not math.isfinite(distance) or distance <= 0):
        raise ValueError('Independent envelope/distance must fit configured robot travel limits')


def validate_envelope(document: dict, context: dict, limits: tuple[int,int]) -> None:
    try:
        _validate_envelope(document,context,limits)
    except (KeyError,TypeError,AttributeError,IndexError) as exc:
        raise ValueError('Incomplete independent commissioning bounds/camera/origin configuration') from exc


def _within(point, envelope):
    return all(lo <= v <= hi for lo,v,hi in zip(
        envelope['minimum_xy_mm'],_xy(point),envelope['maximum_xy_mm']))


def _calibrated_candidate(document, sample, context, origin_epoch):
    # Neither rejected fits nor legacy reference-file calibrations enter this path.
    validate_guided(document)
    name = document['selected_model']
    if (name is None or not document['models'][name]['numerically_accepted'] or
            document['models'][name]['max_error_mm'] > 3):
        raise ValueError('Rejected calibration: commissioning movement is blocked')
    if document['request']['origin_epoch'] != origin_epoch:
        raise ValueError('Robot origin changed since collection; collect a new candidate')
    if (context != document['request']['context'] or
            document['request']['source_info'] != sample['source_info']):
        raise ValueError('Independent source/context differs from collected calibration')
    if sample['frame_size'] != document['frame_size'] or any(
            np.max(np.abs(np.array(sample['geometry'][side])-document['geometry'][side])) > 4
            for side in ('left','right')):
        raise ValueError('Measured source geometry changed since calibration')
    target = sample['target']
    if sample.get('calibration_id') != document['calibration_id'] or sample.get('calibration_error') is not None:
        raise ValueError('Current calibration inspection is invalidated or differs from the candidate')
    if (sample.get('visibility') != 'clear' or sample.get('direct_screen') != sample['screen']
            or sample.get('direct_visibility') != 'clear'):
        raise ValueError('Current direct screen evidence is unclear or disagrees with the selected identity')
    if 'active' in target and target['active'] is not True:
        raise ValueError('Selected button is inactive or its activity is uncertain')
    if cv2.pointPolygonTest(np.array(document['coverage']['fit_hull_pixels'],np.float32),
                           tuple(map(float,target['pixel'])),False) < 0:
        raise ValueError('Selected button is outside the fitted control hull')
    # Reuse existing transform math; this never changes candidate action eligibility.
    xy = transform_point(document['models'][document['selected_model']]['matrix'],target['pixel'])
    if target.get('mm') is None or not np.allclose(_xy(target['mm']),xy,atol=1e-6,rtol=1e-6):
        raise ValueError('Current inspected coordinates are unavailable or disagree with the candidate')
    return xy


def _candidate(document, sample, context, origin_epoch):
    xy = _calibrated_candidate(document,sample,context,origin_epoch)
    target = sample['target']
    if target['kind'] != 'button' or target['display'] != 'right' or sample['screen'] == 'unknown':
        raise ValueError('Commissioning currently supports measured right-region buttons only')
    matches = [p for p in document['request']['points'] if
               all(p[k] == target[k] for k in ('label','kind','display')) and p['screen'] == sample['screen']]
    if len(matches) != 1 or max(abs(a-b) for a,b in zip(matches[0]['pixel'],target['pixel'])) > 4:
        raise ValueError('Selected button has no matching measured calibration control')
    return xy


@dataclass(frozen=True)
class MovePlan:
    token: str
    created_at: float
    origin_epoch: str
    selection: tuple
    calibration_path: str
    calibration_sha256: str
    envelope_path: str
    envelope_sha256: str
    envelope_json: str
    calibration_id: str
    max_error_mm: float
    anchor_json: str
    command_xy: tuple[int, int]
    predicted_xy: tuple[float, float]

    def preview(self):
        sample = json.loads(self.anchor_json)
        return {'token':self.token,'selection':list(self.selection),'pixel':sample['target']['pixel'],
            'predicted_xy_mm':list(self.predicted_xy),'command_xy_mm':list(self.command_xy),
            'calibration_sha256':self.calibration_sha256,'origin_epoch':self.origin_epoch,
            'calibration_id':self.calibration_id,'numerical_max_error_mm':self.max_error_mm,
            'independent_envelope':json.loads(self.envelope_json),
            'commissioning_only':True,'normal_action_ready':False,'physical_verified':False}

    def resolve(self, observer, *, origin_epoch, limits, simulation, position=None, _resolve_target=None):
        if origin_epoch != self.origin_epoch or not 0 <= time.monotonic()-self.created_at <= 30:
            raise ValueError('Move confirmation expired or robot origin changed; prepare again')
        if str(observer.projector.calibration_path) != self.calibration_path:
            raise ValueError('Loaded calibration changed; prepare again')
        document, digest = _load(self.calibration_path)
        envelope, envelope_digest = _load(self.envelope_path)
        if digest != self.calibration_sha256 or envelope_digest != self.envelope_sha256:
            raise ValueError('Calibration or independent bounds changed; prepare again')
        context = observer.projector.context
        validate_envelope(envelope,context,limits)
        sample = observer.calibration_sample(*self.selection)
        source = sample['source_info']
        if not simulation and (source.get('simulation') is not False or source.get('kind') not in ('local_camera','remote_bridge')):
            raise ValueError('Hardware movement rejects recorded/simulated sources')
        anchor = json.loads(self.anchor_json)
        if (sample['target'].get('active') != anchor['target'].get('active') or
                max(abs(a-b) for a,b in zip(sample['target']['pixel'],anchor['target']['pixel'])) > 4 or
                any(np.max(np.abs(np.array(sample['geometry'][s])-anchor['geometry'][s])) > 4 for s in ('left','right'))):
            raise ValueError('Selected button/geometry changed since preview; prepare again')
        xy = (_resolve_target or _candidate)(document,sample,context,origin_epoch)
        command = tuple(rounded_mm(v) for v in xy)
        if command != self.command_xy or not _within(xy,envelope) or not _within(command,envelope):
            raise ValueError('Current/rounded destination changed or exceeds independent bounds')
        if position is not None:
            if not _within(position,envelope) or math.dist(position,command) > envelope['maximum_move_mm']:
                raise ValueError('Start position or move distance exceeds independent bounds')
        age = time.monotonic()-sample['received_at']+sample['upstream_age_seconds']
        current = observer.snapshot()
        if (not 0 <= age <= 1.5 or not current['fresh'] or
                current['session_id'] != self.selection[0] or
                current['capture_index'] != sample['capture_index'] or
                current['projection']['screen'] != self.selection[1]):
            raise ValueError('Direct target evidence expired before transmission')
        return command


def _prepare_target(observer, selection, envelope_path, *, origin_epoch, limits, simulation, _resolve_target=None):
    if observer.projector.calibration_path is None or observer.projector.context is None:
        raise ValueError('Load an independently collected guided candidate/context first')
    calibration_path = str(observer.projector.calibration_path)
    document, digest = _load(calibration_path)
    envelope_path = str(Path(envelope_path).expanduser().resolve())
    envelope, envelope_digest = _load(envelope_path)
    sample = observer.calibration_sample(*selection)
    validate_envelope(envelope,observer.projector.context,limits)
    xy = (_resolve_target or _candidate)(document,sample,observer.projector.context,origin_epoch)
    plan = MovePlan(token=uuid4().hex,created_at=time.monotonic(),origin_epoch=origin_epoch,
        selection=tuple(selection),calibration_path=calibration_path,calibration_sha256=digest,
        envelope_path=envelope_path,envelope_sha256=envelope_digest,
        envelope_json=json.dumps(envelope,allow_nan=False),calibration_id=document['calibration_id'],
        max_error_mm=document['models'][document['selected_model']]['max_error_mm'],
        anchor_json=json.dumps(sample,allow_nan=False),
        command_xy=tuple(rounded_mm(v) for v in xy),predicted_xy=tuple(xy))
    plan.resolve(observer,origin_epoch=origin_epoch,limits=limits,simulation=simulation,_resolve_target=_resolve_target)
    return plan


def prepare_move(observer, selection, envelope_path, *, origin_epoch, limits, simulation):
    return _prepare_target(observer,selection,envelope_path,origin_epoch=origin_epoch,
        limits=limits,simulation=simulation)
