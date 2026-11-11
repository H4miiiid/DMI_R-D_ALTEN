"""Selective SENSE presentation updates, never robot/action observations.

The analysis worker owns this bounded state. Full VisionSession observations
remain the only source of targets, calibration samples and action feedback.
"""
from copy import deepcopy
from dataclasses import dataclass
import math
import time

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection import right_display as rd
from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry, rectify_display
from dmi_computer_vision.src.dmi.detection.right_layout import field_quad_from_contour
from dmi_computer_vision.src.dmi.detection.title_ocr import read_title, title_state
from dmi_computer_vision.src.dmi.mode_observation import ModeHistory, observe_modes
from dmi_computer_vision.src.dmi.temporal.smoothing import RightDisplayStabilizer
from dmi_robot_master.integration.screen_lock import ScreenLock
from dmi_robot_master.integration.screen_profiles import region_at


@dataclass
class MonitorDecision:
    full: bool
    reason: str
    view: dict | None = None
    semantic_change: bool = False
    invalidate: bool = False


def _crop(image: np.ndarray, region: dict, size=(128, 48), *, inset=0.) -> np.ndarray:
    x1, y1, x2, y2 = region['bbox']
    dx, dy = (x2-x1)*inset, (y2-y1)*inset
    x1, y1, x2, y2 = map(round, (x1+dx, y1+dy, x2-dx, y2-dy))
    if not (0 <= x1 < x2 <= image.shape[1] and 0 <= y1 < y2 <= image.shape[0]):
        raise ValueError('Monitor region outside current image')
    return cv2.resize(image[y1:y2, x1:x2], size, interpolation=cv2.INTER_AREA)


def _descriptor(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Relative local contrast tolerates uniform gain/offset without hiding a
    # changed glyph. A floor prevents sensor noise on blue backgrounds exploding.
    return np.clip((gray-np.median(gray))*40/max(12., float(gray.std())), -128, 127)


def _changed(a: np.ndarray, b: np.ndarray) -> bool:
    change = np.abs(a-b) > 20
    if float(change.mean()) > .025:
        return True
    ys, xs = np.arange(0, change.shape[0], 8), np.arange(0, change.shape[1], 8)
    blocks = np.add.reduceat(np.add.reduceat(change, ys, axis=0), xs, axis=1)
    area = np.minimum(8, change.shape[0]-ys)[:, None]*np.minimum(8, change.shape[1]-xs)[None, :]
    return bool(np.any(blocks > area*.25))


def _structure(image: np.ndarray, result: dict, elements: dict) -> np.ndarray:
    points = np.r_[result['left_display']['geometry']['corners'],
                   result['right_display']['geometry']['corners']]
    lo, hi = np.min(points, axis=0).astype(int), np.max(points, axis=0).astype(int)
    lo = np.maximum(0, lo-8);hi = np.minimum(image.shape[1::-1], hi+9)
    crop = image[lo[1]:hi[1],lo[0]:hi[0]].copy()
    for region in elements.values():
        cv2.fillConvexPoly(crop, np.int32(region['corners'])-lo, (0,0,0))
    return _descriptor(cv2.resize(crop,(320,192),interpolation=cv2.INTER_AREA))


def _activity(image: np.ndarray, region: dict) -> bool | None:
    quad = np.float32(region['corners'])
    target = np.float32([[0,0],[159,0],[159,79],[0,79]])
    crop = cv2.warpPerspective(image, cv2.getPerspectiveTransform(quad, target), (160,80))
    interior = crop[12:-12, 19:-19]
    gray = cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY)
    foreground = (gray > float(np.median(gray))+18).astype(np.uint8)*255
    return rd._level_button_active(interior, foreground)


def _field_read(image: np.ndarray, result: dict, locked: dict, screen: str, *,
                diagnostics: dict | None = None) -> dict | None:
    """Reuse current measured-field localization and unchanged digit recognition."""
    region = result['right_display']['geometry']
    corners = np.float32(region['corners'])
    geometry = DisplayGeometry(corners, np.float32(region.get('oriented_box', corners)), tuple(region['bbox']))
    rectified = rectify_display(image, geometry, rd.RECTIFIED_SIZE)
    if screen in {'Train Data', 'Validate Train Data'}:
        detected = rd._detect_train_field(rectified, unique=screen == 'Validate Train Data')
    elif screen in {'Driver ID', 'Level'}:
        evidence = rd._field_evidence(image, geometry)
        detected = rd._detect_data_field(rectified, contrast_fallback=True, evidence_frame=evidence)
    else:
        detected = rd._detect_data_field(rectified)
    if detected is None:
        if diagnostics is not None:
            diagnostics['reason'] = 'field_border_missing'
        return None
    field = rd._region_result(field_quad_from_contour(detected[1]), geometry, image.shape[:2])
    if (np.max(np.abs(np.asarray(field['center'])-locked['center'])) > 4 or
            np.max(np.abs(np.asarray(field['corners'])-locked['corners'])) > 4):
        if diagnostics is not None:
            diagnostics['reason'] = 'field_geometry_changed'
        return None
    if screen == 'Train Data':
        value = rd._read_train_field_value(rectified, detected[0], screen)
    elif screen == 'Validate Train Data':
        value = rd._read_validation_value(rd._crop_box(rectified, detected[0]))
    else:
        value = rd._read_digits(rd._crop_box(rectified, detected[0]), last_only=screen=='Level')
    field['value'] = f'Level {value}' if value is not None and screen=='Level' else value
    return field


class ScreenMonitor:
    """Small bounded ROI scheduler; no synthetic Observation or evidence ages."""
    full_audit_seconds = 1.
    partial_retry_seconds = .5
    field_refresh_seconds = 1.
    field_retry_seconds = .15
    title_check_seconds = 1.

    def __init__(self) -> None:
        self.checked = self.skipped = self.field_reads = self.title_reads = 0
        self.check_seconds = self.field_seconds = self.title_seconds = 0.
        self.clear()

    def clear(self) -> None:
        self.active = False
        self._basis = self._result = self._layout = None
        self._field_key = self._title_key = None
        self._refs = {}
        self._last_full = self._last_field = self._last_title = -math.inf
        self._field_seen = -math.inf
        self._field_capture = -1
        self._last_index = -1
        self._field_value = None
        self._direct_field_value = None
        self._pending_field = False
        self._unknown_field_reads = 0
        self._values = RightDisplayStabilizer()
        self._modes = ModeHistory()

    def bind_full(self, observation, packet, layout: dict, *, context=None, now=None) -> None:
        now = time.monotonic() if now is None else now
        age = now-observation.received_at+observation.upstream_age_seconds
        if (not layout or layout['state'] != 'LOCKED' or not layout.get('alignment_valid', True)
                or not 0 <= age <= 1.5):
            self.clear()
            self._last_full = packet.received_at
            return
        profile = layout['profile']
        field_key = tuple(profile['dynamic_ocr'].split('/')) if profile['dynamic_ocr'] else None
        if field_key and (region_at(observation.result, field_key) is None or
                          region_at(observation.layout_evidence or {}, field_key) is None):
            # A lock may retain geometry through brief misses. That is not a
            # current dynamic field; retry full analysis at the bounded partial
            # cadence rather than fabricating a field or dereferencing None.
            self.clear()
            self._last_full = packet.received_at
            return
        basis = (observation.source_id, observation.session_id, observation.frame_size,
                 layout['screen'], deepcopy(context))
        same = self._basis == basis and self._result is not None and all(
            np.max(np.abs(np.asarray(observation.result[side]['geometry']['corners'])-
                          self._result[side]['geometry']['corners'])) <= 4
            for side in ('left_display','right_display'))
        if not same:
            self.clear()
        self.active = True
        self._basis = basis
        self._result = ScreenLock.measured_display(observation.result, observation.layout_evidence,
                                                  layout=layout, frame_size=observation.frame_size)
        self._layout = deepcopy(layout)
        self._field_key = field_key
        self._title_key = profile['title_side'] + '_display/title'
        ScreenLock.apply_display(self._result, layout)
        self._last_full = packet.received_at
        self._full_upstream = observation.upstream_age_seconds
        self._last_title = packet.received_at
        self._last_index = packet.capture_index
        self._refs = {key: self._region_descriptor(packet.image, key, region)
                      for key, region in layout['elements'].items()}
        # A separate whole-monitor check detects overlays/changes outside known
        # controls. Dynamic ROIs are masked; their current crops are checked below.
        self._structure = self._structural(packet.image)
        field = region_at(observation.layout_evidence or {}, self._field_key) if self._field_key else None
        if field is not None:
            self._accept_field(field, packet)

    def _structural(self, image):
        # Padding includes actual outer borders; no synthetic division is drawn.
        return _structure(image, self._result, self._layout['elements'])

    @staticmethod
    def static_visible(reference: np.ndarray, image: np.ndarray, result: dict, layout: dict) -> bool:
        """Read-only static overlay checks; not recognition or action evidence."""
        if (not layout.get('alignment_valid', True) or reference.shape != image.shape
                or tuple(image.shape[1::-1]) != layout.get('frame_size')
                or result['right_display']['state'] != layout['screen']):
            return False
        elements = layout['elements']
        title = elements.get(layout['profile']['title_side']+'_display/title')
        return bool(title and not _changed(_descriptor(_crop(reference,title)), _descriptor(_crop(image,title)))
                    and not _changed(_structure(reference,result,elements), _structure(image,result,elements)))

    def _accept_field(self, field: dict, packet) -> bool:
        if packet.capture_index <= self._field_capture:
            return False
        self._field_capture = packet.capture_index
        changed = self._direct_field_value != field['value']
        self._direct_field_value = field['value']
        self._unknown_field_reads = self._unknown_field_reads+1 if field['value'] is None else 0
        content = {'visibility':'clear','state':self._layout['screen'], 'title':None,
                   'data_field':field,'buttons':{}}
        confirmed = self._values.update(content)['data_field']['value']
        self._field_value = field['value'] if field['value'] == confirmed else None
        self._pending_field = field['value'] != confirmed or field['value'] is None
        self._last_field = packet.received_at
        self._field_seen = packet.received_at-getattr(packet,'remote_capture_age_seconds',0.)-getattr(packet,'transport_round_trip_seconds',0.)
        return changed

    def field_snapshot(self) -> dict | None:
        if not self.active or not math.isfinite(self._field_seen):
            return None
        return {'name':self._layout['profile']['field_name'],
                'value':self._field_value,'evidence_at':self._field_seen,
                'pending_confirmation':self._pending_field,'presentation_only':True}

    def _region_descriptor(self, image, key, region):
        crop = _crop(image, region)
        if self._layout['screen']=='Level' and key.startswith('right_display/buttons/'):
            interior=crop[7:-7,15:-15]
            gray=cv2.cvtColor(interior,cv2.COLOR_BGR2GRAY)
            return ((gray > float(np.median(gray))+18)*255).astype(np.float32)
        return _descriptor(crop)

    def check_frame(self, packet, *, now: float | None = None) -> MonitorDecision:
        started = time.perf_counter()
        now = time.monotonic() if now is None else now
        try:
            return self._check(packet, now)
        finally:
            self.check_seconds += time.perf_counter()-started

    def _check(self, packet, now) -> MonitorDecision:
        self.checked += 1
        if not self.active:
            due = packet.received_at-self._last_full >= self.partial_retry_seconds
            self.skipped += int(not due)
            return MonitorDecision(due,'partial_retry')
        age = now-packet.received_at+getattr(packet,'remote_capture_age_seconds',0.)+getattr(packet,'transport_round_trip_seconds',0.)
        if tuple(packet.image.shape[1::-1]) != self._basis[2]:
            return MonitorDecision(True,'source_changed',invalidate=True)
        if not 0 <= age <= 1.5:
            return MonitorDecision(True,'source_stale',invalidate=True)
        if packet.capture_index <= self._last_index:
            return MonitorDecision(False,'duplicate')
        self._last_index = packet.capture_index
        if _changed(self._structural(packet.image),self._structure):
            return MonitorDecision(True,'monitor_or_unmodeled_change',invalidate=True)
        descriptors = {key:self._region_descriptor(packet.image,key,region)
                       for key,region in self._layout['elements'].items()}
        changes = {key for key,desc in descriptors.items() if _changed(desc,self._refs[key])}
        field_key = '/'.join(self._field_key) if self._field_key else None
        title_key = self._title_key
        mode_keys = {'left_display/boxes/box_14','left_display/boxes/box_16'}
        # A blink/identity change is presentation evidence only; it also revokes
        # older full-observation action eligibility until an independent audit.
        semantic = bool(changes & mode_keys)
        title_due = packet.received_at-self._last_title >= self.title_check_seconds
        if title_key in changes and title_due:
            start=time.perf_counter()
            crop=_crop(packet.image,self._layout['elements'][title_key],(384,64))
            title=read_title(crop,(0,0,crop.shape[1],crop.shape[0]))
            self.title_reads+=1;self.title_seconds+=time.perf_counter()-start
            self._last_title=packet.received_at
            state = title_state(title)
            if state != self._layout['screen']:
                return MonitorDecision(True,'title_unreadable' if state == 'unknown' else 'title_changed',
                                       invalidate=True)
            self._refs[title_key]=descriptors[title_key]
        elif title_key in changes:
            # A transition must not wait for a title timer to expire.
            return MonitorDecision(True,'title_change_before_audit',invalidate=True)
        unknown_changes = changes-{field_key,title_key}-mode_keys
        if unknown_changes:
            if unknown_changes <= set(self._layout['profile']['optional']):
                # Audit optional changes once without clearing unrelated locked
                # geometry. A fresh full result supplies identity/action proof;
                # subsequent audits release missing optional cells independently.
                return MonitorDecision(True,'optional_control_changed',semantic_change=True)
            return MonitorDecision(True,'control_or_other_region_changed',invalidate=True)
        changed_field = field_key in changes
        if changed_field:
            self._field_value=None
            self._pending_field=True
            self._unknown_field_reads=0
            semantic=True
        interval = (self.field_retry_seconds if self._pending_field and self._unknown_field_reads < 3
                    else self.field_refresh_seconds)
        due = self._field_key is not None and packet.received_at-self._last_field >= interval
        full_due = packet.received_at-self._last_full >= self.full_audit_seconds
        if due and not full_due:
            start=time.perf_counter()
            diagnostics = {}
            field=_field_read(packet.image,self._result,self._layout['elements'][field_key],self._layout['screen'],
                              diagnostics=diagnostics)
            self.field_reads+=1;self.field_seconds+=time.perf_counter()-start
            if field is None:
                return MonitorDecision(True,diagnostics.get('reason','field_border_missing_or_changed'),
                                       invalidate=True)
            semantic |= self._accept_field(field,packet)
            self._refs[field_key]=descriptors[field_key]
        result=deepcopy(self._result)
        if self._field_key:
            region_at(result, self._field_key)['value'] = self._field_value if 0 <= now-self._field_seen <= 1.5 else None
        if self._layout['screen']=='Level':
            for name,region in result['right_display']['buttons'].items():
                active=_activity(packet.image,region)
                semantic |= active != region.get('active')
                region['active']=active
        # Only independently locked mode-box geometry is used for display reads.
        mode_result=deepcopy(result)
        boxes=mode_result['left_display']['boxes']
        mode_result['left_display']['boxes']={key.split('/')[-1]:
            {**boxes.get(key.split('/')[-1], {}), **self._layout['elements'][key]}
            for key in mode_keys if key in self._layout['elements']}
        icons=observe_modes(packet.image,mode_result)
        geometry=[result[side]['geometry']['corners'] for side in ('left_display','right_display')] if icons else None
        modes=self._modes.update(packet.received_at,icons,geometry)
        modes['observations']=icons
        for name,icon in icons.items():
            result['left_display']['boxes'].setdefault(name,
                deepcopy(self._layout['elements']['left_display/boxes/'+name]))
            result['left_display']['boxes'][name]['icon']=None
        view={'result':result,'modes':modes,'capture_index':packet.capture_index,
              'received_at':packet.received_at,'upstream_age_seconds':age-(now-packet.received_at),
              'full_received_at':self._last_full,'full_upstream_age_seconds':self._full_upstream,
              'field_evidence_at':self._field_seen,'presentation_only':True,
              'generation':self._layout['generation']}
        self.skipped += int(not full_due)
        return MonitorDecision(full_due,'structural_audit' if full_due else 'roi_update',view,semantic)

    def stats(self) -> dict:
        return {'checked_frames':self.checked,'policy_skipped_frames':self.skipped,
                'cheap_check_seconds':self.check_seconds,'field_reads':self.field_reads,
                'field_read_seconds':self.field_seconds,'title_reads':self.title_reads,
                'title_read_seconds':self.title_seconds,'full_audit_seconds':self.full_audit_seconds}
