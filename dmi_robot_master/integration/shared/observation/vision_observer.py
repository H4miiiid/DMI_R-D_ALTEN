"""In-memory observation workers. No robot transport, commands or target files."""
from copy import deepcopy
import json
import math
from pathlib import Path
from threading import Condition, Event, Lock, Thread
import time

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.api import VisionSession
from dmi_computer_vision.src.dmi.shared.mode_observation import ModeHistory, observe_modes, connected_regions
from dmi_computer_vision.src.dmi.shared.output.annotation import annotate_frame
from dmi_computer_vision.src.dmi.shared.output.json_writer import close_coordinates, compact_state
from dmi_computer_vision.src.dmi.shared.output.preview_state import LivePreviewState
from dmi_robot_master.integration.shared.acquisition.camera import IntegrationFrame
from dmi_robot_master.integration.shared.projection.targets import TargetProjector
from dmi_robot_master.integration.shared.projection.publication import project_pixels
from dmi_robot_master.integration.v2.screen_lock import ScreenLock
from dmi_robot_master.integration.v2.frozen_screen import FrozenScreen
from dmi_robot_master.integration.v2 import locked_targets as v2_targets
from dmi_robot_master.integration.v2.screen_monitor import MonitorDecision, ScreenMonitor
from dmi_robot_master.integration.shared.calibration.calibration import REFERENCE_PATH as KEYPAD_REFERENCE_PATH
from dmi_robot_master.integration.shared.calibration.sense_calibration import REFERENCE_PATH as SENSE_REFERENCE_PATH


def _jpeg(image):
    height, width = image.shape[:2]
    scale = min(1., 960 / width)
    small = cv2.resize(image, (round(width*scale), round(height*scale))) if scale < 1 else image
    ok, data = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise ValueError('Preview JPEG encoding failed')
    return data.tobytes()


def _ocr_fields(observation):
    """Display existing field values only when the latest direct read agrees."""
    right = observation.result['right_display']
    direct = observation.direct_evidence
    if (right['geometry'] is None or right['visibility'] != 'clear'
            or right['state'] == 'unknown' or direct.get('right_state') != right['state']
            or direct.get('right_visibility') != 'clear' or direct.get('right_field') is None):
        return {}
    fields = compact_state(observation.result)['right_display']['fields']
    return {name: field['value'] if (
        field['value'] == direct.get('right_field_value')
        and close_coordinates(field['center'], direct['right_field'], 4.)) else None
        for name, field in fields.items()}


class VisionObserver:
    """One source, one detector, one render worker; each input has one latest slot.

    Stop/loss invalidates readers immediately. In-flight analysis cannot republish
    after invalidation. Lifecycle callers must join before starting a replacement.
    Native acquisition may finish its bounded timeout after stop; never kill threads.
    """
    def __init__(self, source, source_info: dict, *, calibration_path=None,
                 context=None, geometry_tolerance_px=4., debug_jsonl=None,
                 session_factory=VisionSession, stable_preview=False, comparison=None,
                 origin_epoch=None, contrast_fallback=False, progressive_lock=False,
                 selective_updates=False, locked_actions=False, freeze_on_lock=False):
        self.source, self.source_info = source, deepcopy(source_info)
        self.projector = TargetProjector(source_info=source_info, calibration_path=calibration_path,
            context=context, geometry_tolerance_px=geometry_tolerance_px, origin_epoch=origin_epoch)
        self.session_factory = session_factory
        self.stable_preview = stable_preview
        self.debug_jsonl = Path(debug_jsonl) if debug_jsonl else None
        self._comparison = deepcopy(comparison)
        if freeze_on_lock and not (progressive_lock and locked_actions):
            raise ValueError("Frozen actions require progressive locking and locked actions")
        self._freeze_on_lock = freeze_on_lock
        self._frozen = None
        self._frozen_action = False
        self._locked_actions = locked_actions
        self._action_full_request = None
        self._contrast_fallback = contrast_fallback
        self._screen_lock = ScreenLock() if progressive_lock else None
        self._lock_layout = None
        if selective_updates and not progressive_lock:
            raise ValueError('Selective updates require progressive SENSE locking')
        self._monitor = ScreenMonitor() if selective_updates else None
        self._monitor_epoch = 0
        self._monitor_bound_epoch = None
        self._monitor_view = None
        self._monitor_field = None
        self._monitor_admitted = False
        self._monitor_stats = {}
        self._action_invalidated_capture = -1
        self._annotation_from_monitor = False
        self._annotation_monitor_epoch = -1
        self._condition = Condition()
        self._project_lock = Lock()
        self._calibration_epoch = 0
        self._calibration_invalidated = False
        self._origin_bound_at = -math.inf
        self._stop = Event()
        self._threads = []
        self._packet = self._observation = self._projection = None
        self._press_history = []  # At most three experimental detections; no images/annotations.
        self._raw_jpeg = self._annotation_jpeg = None
        self._raw_index = self._annotation_index = -1
        self._raw_received = None
        self._annotation_context = None
        self._annotation_expires = 0.
        self._preview_epoch = self._annotation_epoch = 0
        self._raw_upstream_age = 0.
        self._last_taken = -1
        self._error = None
        self._state = 'stopped'
        self._mode = {}
        self._samples = []
        # Timing samples are bounded; totals/counters cover the whole session.
        self._analysis_count = self._overwrites = self._render_count = 0
        self._analysis_total = 0.
        self._started = None

    @property
    def running(self):
        return any(thread.is_alive() for thread in self._threads)

    def start(self) -> None:
        if self._threads:
            raise RuntimeError('Create a new observer for each session')
        self._started = time.monotonic()
        self._state = 'starting'
        for name, function in (('analysis', self._detect), ('render', self._render),
                               ('acquisition', self._acquire)):
            thread = Thread(target=function, name=f'dmi-gui-{name}', daemon=True)
            self._threads.append(thread)
            thread.start()

    def invalidate(self, state: str = 'stopped', error: str | None = None) -> None:
        with self._condition:
            self._stop.set()
            self._state, self._error = state, error
            self._packet = self._observation = self._projection = None
            self._press_history.clear()
            self._raw_jpeg = self._annotation_jpeg = None
            self._mode = {}
            if getattr(self.projector, 'stable_registration', False):
                self.projector.invalidate_registration(state)
            self._invalidate_layout(state)
            self._preview_epoch += 1
            self._condition.notify_all()

    def close(self, timeout: float = 3.) -> None:
        self.invalidate()
        deadline = time.monotonic()+timeout
        for thread in self._threads:
            thread.join(max(0., deadline-time.monotonic()))
        if self.running:
            raise RuntimeError('Vision worker still stopping; do not start another source')

    def _acquire(self):
        try:
            with self.source:
                while not self._stop.is_set():
                    packet = self.source.read()
                    with self._condition:
                        if self._stop.is_set():
                            break
                        if self._packet is not None and self._packet.capture_index > self._last_taken:
                            self._overwrites += 1
                        self._packet = packet
                        self._condition.notify_all()
        except EOFError:
            self.invalidate('ended')
        except Exception as exc:
            if not self._stop.is_set():
                self.invalidate('source_error', str(exc))

    def _detect(self):
        stream = None
        history = ModeHistory()
        try:
            if self.debug_jsonl:
                self.debug_jsonl.parent.mkdir(parents=True, exist_ok=True)
                stream = self.debug_jsonl.open('a', encoding='utf-8')
                if self._comparison is not None:
                    stream.write(json.dumps({'type': 'session_start', 'comparison': self._comparison},
                                            allow_nan=False) + '\n')
                    stream.flush()
            options = {'contrast_fallback': True} if self._contrast_fallback else {}
            if self._screen_lock is not None:
                options['collect_layout_evidence'] = True
            with self.session_factory(str(self.source_info), **options) as session:
                while not self._stop.is_set():
                    with self._condition:
                        self._condition.wait_for(lambda: self._stop.is_set() or (
                            self._packet is not None and self._packet.capture_index > self._last_taken
                            and self._frozen is None and not self._frozen_action))
                        if self._stop.is_set():
                            break
                        packet = self._packet
                        self._last_taken = packet.capture_index
                        layout_epoch = self._calibration_epoch
                        monitor_epoch = self._monitor_epoch
                        current_layout = deepcopy(self._lock_layout)
                        action_request = self._action_full_request
                    started = time.monotonic()
                    decision = (None if action_request is not None else self._check_monitored_packet(
                        session, packet, monitor_epoch, current_layout, history))
                    if decision is not None and not decision.full:
                        if stream and not self._stop.is_set():
                            stream.write(json.dumps({'type':'monitor_update',
                                'capture_index':packet.capture_index, 'reason':decision.reason,
                                'presentation_only':True,
                                'field_value': ((decision.view['result']['right_display'].get('data_field') or {}).get('value')
                                                if decision.view else None)}, allow_nan=False)+'\n')
                            stream.flush()
                        continue
                    observation = session.process(packet)
                    with self._project_lock:
                        calibration_epoch = self._calibration_epoch
                        if (getattr(self.projector, 'stable_registration', False)
                                and not self._calibration_invalidated
                                and observation.received_at-observation.upstream_age_seconds >= self._origin_bound_at):
                            self.projector.observe_geometry(observation)
                        projection = self._project(observation)
                    # This API is observation-only, including for legacy valid fits.
                    for target in projection['targets'].values():
                        target['usable'] = False
                    if observation.temporal_reset:
                        history.reset()
                    icons = observe_modes(packet.image, observation.result)
                    geometry = [observation.result[f'{side}_display']['geometry']['corners']
                                for side in ('left', 'right')] if icons else None
                    mode = history.update(packet.received_at, icons, geometry)
                    mode['observations'] = icons
                    if icons:
                        mode['history_epoch'] = history.epoch
                    with self._condition:
                        if self._stop.is_set():
                            break
                        if (calibration_epoch != self._calibration_epoch
                                or observation.received_at - observation.upstream_age_seconds < self._origin_bound_at):
                            self._clear_mm(projection)
                        if (self._screen_lock is not None and layout_epoch == self._calibration_epoch
                                and calibration_epoch == self._calibration_epoch
                                and observation.received_at-observation.upstream_age_seconds >= self._origin_bound_at):
                            self._screen_lock.observe_full(observation, context=self._layout_context())
                            self._lock_layout = self._screen_lock.cached_layout()
                            if not self._lock_layout['alignment_valid']:
                                self._action_invalidated_capture = max(
                                    self._action_invalidated_capture, observation.capture_index+1)
                                self._press_history.clear()
                                self._preview_epoch += 1
                        lock_layout = deepcopy(self._lock_layout)
                        if self._monitor is not None:
                            self._monitor_admitted = bool(
                                observation.layout_evidence and
                                observation.layout_evidence.get('right_display') and
                                connected_regions(observation.result))
                            self._monitor.bind_full(observation, packet, lock_layout,
                                context=self._layout_context())
                            self._monitor_view = None
                            self._monitor_field = self._monitor.field_snapshot()
                            self._monitor_stats = self._monitor.stats()
                        duration = time.monotonic()-started
                        self._analysis_count += 1
                        self._analysis_total += duration
                        self._samples.append(duration)
                        del self._samples[:-256]
                        if (projection.get('experimental_recorded_test') and
                                (not lock_layout or lock_layout.get('alignment_valid', True))):
                            if (observation.temporal_reset or not self._press_history
                                    or not self._same_press_context(self._press_history[-1][0], observation)):
                                self._press_history.clear()
                            self._press_history.append((observation, deepcopy(projection), deepcopy(self.source_info)))
                            del self._press_history[:-3]
                        self._observation = (observation, packet.image)
                        if observation.temporal_reset:
                            self._preview_epoch += 1
                        self._projection = projection
                        self._mode = mode
                        self._state = 'observed'
                        if (self._freeze_on_lock and lock_layout and lock_layout['state'] == 'LOCKED'
                                and lock_layout.get('alignment_valid') and connected_regions(observation.result)
                                and projection.get('experimental_registration_id')
                                and projection.get('calibration_id') and not self.projector.error
                                and 0 <= observation.age_seconds() <= 2.):
                            self._frozen = FrozenScreen(observation, lock_layout, self._frozen_context(), mode,
                                history=[item[0] for item in self._press_history])
                            self._frozen.fields = _ocr_fields(observation)
                            self._state = 'locked_snapshot'
                        if self._action_full_request == action_request:
                            self._action_full_request = None
                        self._condition.notify_all()
                    if stream:
                        # Explicit debugging only; no runtime consumer reads this.
                        stream.write(json.dumps({'capture_index': observation.capture_index,
                            'received_at': observation.received_at,
                            'result': observation.result, 'modes': mode,
                            **({'screen_lock': lock_layout} if self._screen_lock else {})},
                            allow_nan=False)+'\n')
                        stream.flush()
        except Exception as exc:
            if not self._stop.is_set():
                self.invalidate('analysis_error', str(exc))
        finally:
            if stream:
                stream.close()

    def _check_monitored_packet(self, session, packet, epoch, layout, history) -> MonitorDecision | None:
        """Run one admitted ROI check and publish presentation under its epoch."""
        if self._monitor is None or not hasattr(session, 'read_regions'):
            return None
        if self._monitor_bound_epoch != epoch:
            self._monitor.clear()
            self._monitor_bound_epoch = epoch
        if self._monitor.active:
            age = (time.monotonic()-packet.received_at
                   + getattr(packet, 'remote_capture_age_seconds', 0.)
                   + getattr(packet, 'transport_round_trip_seconds', 0.))
            decision = (session.read_regions(packet, lambda: self._monitor.check_frame(packet))
                        if 0 <= age <= 1.5 else self._monitor.check_frame(packet))
        elif self._monitor_admitted and layout and layout['screen'] is not None:
            decision = self._monitor.check_frame(packet)
        else:
            return None  # Unsupported screens and TWIN retain full processing.
        with self._condition:
            if self._stop.is_set() or epoch != self._monitor_epoch:
                return MonitorDecision(False, 'context_invalidated_during_check')
            if decision.invalidate:
                # Missing OCR/borders or changed control pixels require fresh
                # analysis, but do not themselves prove the static layout moved.
                self._invalidate_layout(decision.reason, preserve_geometry=decision.reason in (
                    'source_stale', 'title_unreadable', 'title_change_before_audit',
                    'field_border_missing', 'control_or_other_region_changed',
                    'monitor_or_unmodeled_change', 'field_geometry_changed'))
                self._observation = self._projection = None
                self._press_history.clear()
                self._mode = {}
                history.reset()
                self._monitor.clear()
                self._monitor_bound_epoch = self._monitor_epoch
            if decision.semantic_change:
                # Preserve historical identity continuity, but revoke all older
                # action eligibility until a genuinely new full observation.
                self._action_invalidated_capture = packet.capture_index
                self._press_history.clear()
                self._mode = {}
            self._monitor_view = deepcopy(decision.view)
            self._monitor_field = self._monitor.field_snapshot()
            self._monitor_stats = self._monitor.stats()
            self._condition.notify_all()
        return decision

    def _render(self):
        preview = LivePreviewState()
        last_detection, last_epoch = 0, -1
        rendered_detection, render_deadline = -1, float('inf')
        try:
            while not self._stop.wait(.125):
                with self._condition:
                    packet, observed = self._packet, self._observation
                    modes = deepcopy(self._mode)
                    raw_index, annotation_index = self._raw_index, self._annotation_index
                    detection, epoch = self._analysis_count, self._preview_epoch
                    stable = self.stable_preview
                    layout = deepcopy(self._lock_layout)
                    monitor_view = deepcopy(self._monitor_view)
                    monitor_epoch = self._monitor_epoch
                    frozen = self._valid_frozen()
                if epoch != last_epoch:
                    preview.clear()
                    last_epoch = epoch
                raw = (_jpeg(packet.image) if packet is not None
                       and packet.capture_index != raw_index else None)
                annotated = None
                monitor_composite = False
                if layout and not layout.get('alignment_valid', True):
                    preview.clear()
                    last_detection = detection
                if stable and observed is not None and detection != last_detection:
                    observation, image = observed
                    # No queue: skipped detector publications count conservatively
                    # as missed updates for any control still absent in this one.
                    analyzed_packet = IntegrationFrame(image, observation.capture_index,
                        observation.received_at, '', remote_capture_age_seconds=observation.upstream_age_seconds)
                    display_result = (ScreenLock.measured_display(observation.result, observation.layout_evidence,
                                      layout=layout, frame_size=observation.frame_size)
                                      if layout is not None and layout['screen'] else observation.result)
                    display_evidence = ScreenLock.display_evidence(observation.direct_evidence,
                        observation.layout_evidence, display_result) if layout is not None else observation.direct_evidence
                    preview.update(display_result, analyzed_packet, evidence=display_evidence,
                                   updates=detection-last_detection)
                    if layout is not None:
                        ScreenLock.apply_display(preview.result, layout)
                    last_detection = detection
                monitor_valid = (stable and packet is not None and monitor_view is not None
                    and monitor_view['capture_index'] == packet.capture_index
                    and self._monitor_fresh(monitor_view, time.monotonic())
                    and 0 <= time.monotonic()-monitor_view['full_received_at']+
                        monitor_view['full_upstream_age_seconds'] <= 1.5)
                frozen_composite = frozen is not None and packet is not None
                if frozen_composite:
                    image = annotate_frame(packet.image, frozen.result)
                    ScreenLock.draw_missing(image, frozen.result, layout)
                    self._draw_display_modes(image, frozen.modes)
                    cv2.putText(image, "SENSE LOCKED SNAPSHOT | analysis paused until action",
                                (20, image.shape[0]-25), cv2.FONT_HERSHEY_SIMPLEX, .8, (0,190,255), 2)
                    annotated = _jpeg(image)
                elif monitor_valid:
                    if packet.capture_index != annotation_index or not self._annotation_from_monitor:
                        image = annotate_frame(packet.image, monitor_view['result'])
                        if layout:
                            ScreenLock.draw_missing(image, monitor_view['result'], layout)
                        self._draw_display_modes(image, monitor_view['modes'])
                        cv2.putText(image, 'SENSE LOCKED | ROI updates / cached geometry | DISPLAY ONLY',
                                    (20,image.shape[0]-25),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,190,255),2)
                        annotated = _jpeg(image)
                    monitor_composite = True
                elif not stable and observed is not None and observed[0].capture_index != annotation_index:
                    image = annotate_frame(observed[1], observed[0].result)
                    for box, icon in modes.get('observations', {}).items():
                        center = tuple(round(v) for v in icon['center'])
                        cv2.putText(image, f"{box}: {icon['mode'] or icon['status']}", center,
                                    cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 200, 255), 1, cv2.LINE_AA)
                    annotated = _jpeg(image)
                elif stable and packet is not None and (packet.capture_index != annotation_index or
                        detection != rendered_detection or time.monotonic() > render_deadline):
                    image = preview.render(packet)
                    if layout and preview.overlay_valid:
                        ScreenLock.draw_missing(image, preview.result, layout)
                    elif (layout and layout['screen'] and observed is not None
                            and 0 <= observed[0].age_seconds() <= 1.5
                            and 0 <= time.monotonic()-packet.received_at+
                                getattr(packet,'remote_capture_age_seconds',0.)+
                                getattr(packet,'transport_round_trip_seconds',0.) <= 1.5
                            and ScreenMonitor.static_visible(observed[1],packet.image,observed[0].result,layout)):
                        # Changed dynamic pixels can hide old OCR/activity while
                        # independently checked static coordinates remain fixed.
                        ScreenLock.draw_missing(image, observed[0].result, layout, all_static=True)
                    if layout is not None and preview.overlay_valid and layout['screen']:
                        cv2.putText(image, f"SENSE {layout['state']} | cached geometry only | generation {layout['generation']}",
                                    (20, image.shape[0]-25), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 190, 255), 2)
                    render_deadline = preview.expires_at if preview.overlay_valid else float('inf')
                    for box, icon in (modes.get('observations', {}) if preview.overlay_valid else {}).items():
                        center = tuple(round(v) for v in icon['center'])
                        cv2.putText(image, f"{box}: {icon['mode'] or icon['status']}", center,
                                    cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 200, 255), 1, cv2.LINE_AA)
                    annotated = _jpeg(image)
                with self._condition:
                    if self._stop.is_set():
                        break
                    if raw is not None:
                        self._raw_jpeg, self._raw_index = raw, packet.capture_index
                        self._raw_received = packet.received_at
                        self._raw_upstream_age = (getattr(packet, 'remote_capture_age_seconds', 0.)
                                                 + getattr(packet, 'transport_round_trip_seconds', 0.))
                        self._render_count += 1
                    if annotated is not None:
                        if frozen_composite:
                            if frozen is self._frozen and epoch == self._preview_epoch:
                                self._annotation_jpeg = annotated
                                self._annotation_index = packet.capture_index
                                self._annotation_epoch = epoch
                            continue
                        if monitor_composite:
                            if (monitor_epoch == self._monitor_epoch and self._monitor_view is not None
                                    and monitor_view['capture_index'] == self._monitor_view['capture_index']):
                                self._annotation_jpeg = annotated
                                self._annotation_index = packet.capture_index
                                self._annotation_from_monitor = True
                                self._annotation_monitor_epoch = monitor_epoch
                                self._annotation_expires = min(
                                    monitor_view['received_at']-monitor_view['upstream_age_seconds'],
                                    monitor_view['full_received_at']-monitor_view['full_upstream_age_seconds'])+1.5
                            continue
                        self._annotation_from_monitor = False
                        if not stable:
                            if epoch != self._preview_epoch:
                                continue
                            self._annotation_jpeg = annotated
                            self._annotation_index = observed[0].capture_index
                            self._annotation_epoch = epoch
                            continue
                        # A new detection/reset during encoding invalidates this
                        # composite. Raw preview publication remains independent.
                        if detection == self._analysis_count and epoch == self._preview_epoch:
                            self._annotation_jpeg = annotated
                            self._annotation_index = packet.capture_index
                            self._annotation_context = deepcopy(preview.basis)
                            self._annotation_expires = preview.expires_at
                            self._annotation_epoch = epoch
                            rendered_detection = detection
        except Exception as exc:
            self.invalidate('preview_error', str(exc))

    def snapshot(self, *, experimental_action: bool = False) -> dict:
        """Fresh action observations and a separate display-only live composite."""
        now = time.monotonic()
        with self._condition:
            frozen = self._valid_frozen()
            observed = self._observation[0] if self._observation else None
            age = observed.age_seconds() if observed else None
            lifetime = self.experimental_action_limits()[1] if experimental_action else 1.5
            fresh = (observed is not None and 0 <= age <= lifetime and not self._stop.is_set()
                     and observed.capture_index >= self._action_invalidated_capture
                     and (not self._lock_layout or self._lock_layout.get('alignment_valid', True)))
            monitor_fresh = (self._monitor_fresh(self._monitor_view, now) and not self._stop.is_set())
            field_fresh = (self._monitor_field is not None and not self._stop.is_set()
                           and 0 <= now-self._monitor_field['evidence_at'] <= 1.5)
            raw_age = (now-self._raw_received+self._raw_upstream_age
                       if self._raw_received is not None else None)
            projection = deepcopy(self._projection) if fresh else None
            raw = self._raw_jpeg if raw_age is not None and 0 <= raw_age <= 1.5 else None
            context = (LivePreviewState.context(observed.result, observed.direct_evidence,
                       observed.frame_size) if observed else None)
            compatible = (LivePreviewState.compatible(self._annotation_context, context)
                          and self._annotation_epoch == self._preview_epoch
                          and self._packet is not None
                          and tuple(self._packet.image.shape[1::-1]) == self._annotation_context['size'])
            # Only the video can bridge a miss. Targets and selections above
            # still come exclusively from the latest unmodified observation.
            annotation = (self._annotation_jpeg if raw is not None and compatible and
                          now <= self._annotation_expires else raw)
            if self._annotation_from_monitor:
                annotation = (self._annotation_jpeg if raw is not None and monitor_fresh
                    and self._annotation_monitor_epoch == self._monitor_epoch
                    and now <= self._annotation_expires else raw)
            if not self.stable_preview:
                annotation = (self._annotation_jpeg if fresh and
                              self._annotation_index == observed.capture_index and
                              (not self.stable_preview or self._annotation_epoch == self._preview_epoch) else None)
            if frozen is not None and raw is not None and self._annotation_epoch == self._preview_epoch:
                annotation = self._annotation_jpeg or raw
            experimental = getattr(self.projector, 'experimental_recorded_test', False)
            calibration_error = self.projector.error
            if self._calibration_invalidated:
                calibration_error = ('Robot origin changed; initialize the robot to restore experimental mapping'
                    if experimental else 'Robot origin/connection changed; reload independent context')
            elif observed and observed.received_at - observed.upstream_age_seconds < self._origin_bound_at:
                calibration_error = 'Waiting for a fresh detection after robot initialization'
            elapsed = max(.001, now-self._started) if self._started else 1.
            return {'state': 'locked_snapshot' if frozen else 'stale' if observed and not fresh else self._state,
                'locked_snapshot': frozen is not None, 'freeze_on_lock': self._freeze_on_lock,
                'error': self._error, 'fresh': fresh, 'age_seconds': age,
                'session_id': observed.session_id if fresh else None,
                'capture_index': observed.capture_index if fresh else None,
                'projection': projection, 'modes': deepcopy(self._mode) if fresh else {},
                # Identity continuity only: this never authorizes a press or extends evidence age.
                'experimental_context': ([observed.session_id, self._projection['screen']]
                    if observed and self._projection and experimental else None),
                'ocr_fields': (deepcopy(frozen.fields) if frozen else {self._monitor_field['name']:self._monitor_field['value']}
                    if field_fresh else _ocr_fields(observed) if fresh and self._monitor_field is None else {}),
                **({'display_fresh':monitor_fresh or field_fresh,
                    'display_held': frozen is not None,
                    'display_modes':deepcopy(frozen.modes) if frozen else
                        deepcopy(self._monitor_view['modes']) if monitor_fresh else {}}
                    if self._monitor or frozen else {}),
                'raw_jpeg': raw,
                'raw_index': self._raw_index, 'annotation_jpeg': annotation,
                'calibration_error': calibration_error,
                'action_ready': False,
                **({'screen_lock': deepcopy(self._lock_layout)} if self._screen_lock else {}),
                'metrics': {'processed': self._analysis_count, 'overwrites': self._overwrites,
                    'analysis_mean_seconds': self._analysis_total/max(1, self._analysis_count),
                    'analysis_p95_seconds': float(np.percentile(self._samples, 95)) if self._samples else 0.,
                    'processed_fps': self._analysis_count/elapsed,
                    'preview_callbacks_fps': self._render_count/elapsed,
                    **({'selective':deepcopy(self._monitor_stats)} if self._monitor else {})}}

    @staticmethod
    def _monitor_fresh(view, now: float) -> bool:
        return bool(view is not None and 0 <= now-view['received_at']+view['upstream_age_seconds'] <= 1.5)

    @staticmethod
    def _draw_display_modes(image, modes):
        for box, icon in modes.get('observations', {}).items():
            center = tuple(round(v) for v in icon['center'])
            cv2.putText(image, f"{box}: {icon['mode'] or icon['status']}", center,
                        cv2.FONT_HERSHEY_SIMPLEX,.5,(0,200,255),1,cv2.LINE_AA)

    def inspect_target(self, session_id: str, screen: str, label: str) -> dict:
        """Resolve from latest state, never cached UI pixels. No action authority."""
        with self._condition:
            view = self.snapshot()
            if not view['fresh'] or view['session_id'] != session_id:
                raise ValueError('Observation expired or session changed')
            observation = self._observation[0]
        # Re-read calibration/context/geometry through the same resolver used by
        # analysis, so changing a model file cannot leave a selected cached XY.
        with self._project_lock:
            calibration_epoch = self._calibration_epoch
            projection = self._project(observation)
        with self._condition:
            current = self.snapshot()
            if (not current['fresh'] or current['session_id'] != session_id
                    or current['capture_index'] != observation.capture_index):
                raise ValueError('Observation changed during selection; select again')
            if calibration_epoch != self._calibration_epoch:
                raise ValueError('Calibration/origin changed during selection; select again')
            if projection['screen'] != screen or label not in projection['targets']:
                raise ValueError('Selected identity disappeared or screen changed')
            # Pixel/mm inspection is not action authorization. Fields/boxes
            # remain observations; only later guarded actions may promote them.
            target = deepcopy(projection['targets'][label])
            pixel = target['pixel']
            width, height = projection['frame_size']
            if (not all(math.isfinite(v) for v in pixel)
                    or not (0 <= pixel[0] < width and 0 <= pixel[1] < height)):
                raise ValueError('Selected center outside current source geometry')
            content = observation.result[f"{target['display']}_display"]
            geometry = content.get('geometry')
            quad = np.asarray(geometry['corners'] if geometry else [], np.float32)
            if (quad.shape != (4, 2) or not cv2.isContourConvex(quad)
                    or cv2.pointPolygonTest(quad, tuple(map(float, pixel)), False) < 0):
                raise ValueError('Selected center lacks current region geometry')
            if target['display'] == 'right' and target['kind'] == 'button':
                name = f"digit_{label[4:]}" if label.startswith('KEY_') else label.rsplit('/', 1)[-1]
                raw = observation.direct_evidence.get('right_buttons', {}).get(name)
                if raw is None or max(abs(a-b) for a, b in zip(raw, pixel)) > 4:
                    raise ValueError('Selected button lacks matching current direct evidence')
            target.update(usable=False, action_ready=False,
                          capture_index=view['capture_index'], age_seconds=view['age_seconds'])
            return target

    def inspection_snapshot(self) -> dict:
        """GUI-only locked pixels/XY, separate from fresh targets and calibration.

        Derive from the single lock cache on demand; store no second coordinate
        cache and never synthesize an Observation or direct evidence.
        """
        view = self.snapshot()
        with self._condition:
            frozen = self._valid_frozen()
            layout = deepcopy(self._lock_layout)
            observed = self._observation[0] if self._observation else None
            epoch = self._calibration_epoch
            if (not self._locked_actions or not getattr(self.projector, 'stable_registration', False)
                    or observed is None or not layout or not layout.get('alignment_valid')
                    or layout.get('screen') != observed.result['right_display']['state']
                    or self._stop.is_set() or self._calibration_invalidated
                    or not (frozen is not None or 0 <= observed.age_seconds() <= 2.
                            or self._monitor_fresh(self._monitor_view, time.monotonic()))):
                return view
            result = (frozen.targets_result(layout) if frozen else
                      v2_targets.inspection_result(observed.result, layout))
            session_id = observed.session_id
        with self._project_lock:
            projection = self.projector.project(result, {}, frame_size=observed.frame_size)[0]
        with self._condition:
            if (self._stop.is_set() or epoch != self._calibration_epoch or self._calibration_invalidated
                    or not self._lock_layout or layout != self._lock_layout
                    or self._observation is None or self._observation[0] is not observed
                    or projection.get('calibration_id') is None):
                return view
            for target in projection['targets'].values():
                target.update(usable=False, action_ready=False, cached_geometry=True,
                              lock_generation=layout['generation'])
                if frozen:
                    target['locked_snapshot'] = True
                else:
                    target.pop('active', None)  # Geometry-only cache has no activity evidence.
            projection.update(session_id=session_id, capture_index=observed.capture_index,
                              lock_generation=layout['generation'], cached_geometry=True)
            view['locked_inspection'] = projection
        return view

    def inspect_selection(self, session_id: str, screen: str, label: str) -> dict:
        """Selection/inspection only; calibration still calls inspect_target."""
        view = self.inspection_snapshot()
        cached = view.get('locked_inspection') or {}
        target = cached.get('targets', {}).get(label)
        if (target is not None and cached.get('session_id') == session_id and cached.get('screen') == screen):
            try:
                direct = self.inspect_target(session_id, screen, label)
            except ValueError:
                direct = None
            return {**target, 'capture_index': cached['capture_index'], 'age_seconds': view['age_seconds'],
                    'direct_capture_index': direct['capture_index'] if direct else None}
        return self.inspect_target(session_id, screen, label)

    @staticmethod
    def _clear_mm(projection):
        projection.update(calibration_valid=False, calibration_id=None, calibration_provenance=None)
        for target in projection['targets'].values():
            target.update(mm=None, usable=False)
            target.pop('inspection_xy_mm', None)
            target.pop('reference_error_mm', None)
            target.pop('left_border_disagreement_px', None)

    def _project(self, observation):
        if self._calibration_invalidated:
            projection = project_pixels(observation.result, frame_size=observation.frame_size)
            projection.update(simulation=self.projector.simulation)
            self._clear_mm(projection)
            return projection
        return self.projector.project(observation.result,
            observation.direct_evidence, frame_size=observation.frame_size)[0]

    def _layout_context(self) -> tuple:
        """Stable model/origin identity, separate from per-frame mapping rejection."""
        files = []
        for path in (self.projector.calibration_path, KEYPAD_REFERENCE_PATH, SENSE_REFERENCE_PATH):
            try:
                stat = path.stat() if path is not None else None
                stamp = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) if stat else None
            except OSError:
                stamp = None
            files.append((str(path), stamp))
        return (deepcopy(self.source_info), self._calibration_epoch,
                deepcopy(self.projector.context), tuple(files))

    def _invalidate_layout(self, reason: str, *, preserve_geometry: bool = False) -> None:
        """Caller holds the condition; never alter detector/action observations."""
        self._frozen = None
        if self._screen_lock is not None:
            if not preserve_geometry:
                self._screen_lock.invalidate(reason)
            self._lock_layout = self._screen_lock.cached_layout()
            self._preview_epoch += 1
        if self._monitor is not None:
            self._monitor_epoch += 1
            self._monitor_view = None
            self._monitor_field = None
            self._monitor_admitted = False

    def invalidate_calibration(self) -> None:
        """Origin/connection changes clear mm, while camera/preview keep running."""
        with self._condition:
            self._calibration_epoch += 1
            self._calibration_invalidated = True
            self._press_history.clear()
            if getattr(self.projector, 'stable_registration', False):
                self.projector.invalidate_registration('Robot origin or connection invalidated')
            self._invalidate_layout('calibration_or_origin_changed')
            if self._projection:
                self._clear_mm(self._projection)

    def bind_experimental_origin(self, origin_epoch):
        """Confirmed homing requires new evidence; Version 2 reacquires registration."""
        from dmi_robot_master.integration.shared.projection.recorded_test import RecordedTestProjector
        with self._project_lock, self._condition:
            if type(self.projector) is not RecordedTestProjector or self._stop.is_set() or not origin_epoch:
                return False
            self._calibration_epoch += 1
            self._origin_bound_at = time.monotonic()
            self.projector.origin_epoch = origin_epoch
            if self.projector.stable_registration:
                self.projector.reset_registration()
            self._calibration_invalidated = False
            self._press_history.clear()
            self._invalidate_layout('origin_rebound')
            if self._projection:
                self._clear_mm(self._projection)
            return True

    @staticmethod
    def _same_press_context(a, b):
        return (a.session_id == b.session_id and a.frame_size == b.frame_size
            and connected_regions(a.result) and connected_regions(b.result)
            and a.result['right_display']['state'] == b.result['right_display']['state'] != 'unknown'
            and all(ob.direct_evidence.get('right_state') == ob.result['right_display']['state']
                    and ob.direct_evidence.get('right_visibility') == 'clear'
                    and all(ob.result[f'{side}_display'].get('visibility', 'clear') == 'clear'
                            for side in ('left', 'right')) for ob in (a, b))
            and all((a.result[f'{side}_display'].get('title') or {}).get('text')
                    == (b.result[f'{side}_display'].get('title') or {}).get('text')
                    for side in ('left', 'right'))
            and all(np.max(np.abs(np.asarray(a.result[f'{side}_display']['geometry']['corners'])
                                  - np.asarray(b.result[f'{side}_display']['geometry']['corners']))) <= 4
                    for side in ('left', 'right')))

    def experimental_action_limits(self) -> tuple[float, float]:
        """Version 2 SENSE experiment only; calibration/publication keep their limits."""
        with self._condition:
            enabled = (self._locked_actions and getattr(self.projector, 'stable_registration', False)
                       and self._observation is not None and connected_regions(self._observation[0].result))
            return (10., 2.) if enabled else (4., 1.5)

    def _frozen_context(self):
        return (self._layout_context(), getattr(self.projector, "origin_epoch", None),
                getattr(self.projector, "_registration_id", None))

    def _valid_frozen(self):
        """Caller holds condition. Context checks inspect metadata, never image pixels."""
        frozen = self._frozen
        if frozen is not None and (self._stop.is_set() or self._calibration_invalidated
                or frozen.context != self._frozen_context()
                or (self._packet is not None and tuple(self._packet.image.shape[1::-1]) != frozen.observation.frame_size)):
            self._invalidate_layout('frozen_context_changed')
            self._press_history.clear()
            self._condition.notify_all()
            return None
        return frozen

    def _frozen_press_sample(self, session_id, screen, label):
        from dmi_robot_master.integration.shared.projection.recorded_test import RecordedTestProjector
        with self._condition:
            frozen = self._valid_frozen()
            if (frozen is None or type(self.projector) is not RecordedTestProjector
                    or not self.projector.stable_registration or self.projector.error
                    or frozen.observation.session_id != session_id or self._lock_layout['screen'] != screen):
                raise ValueError('Wait for a complete locked snapshot before pressing')
            layout = deepcopy(self._lock_layout)
            result = frozen.targets_result(layout)
            observation = frozen.observation
        with self._project_lock:
            projection = self.projector.project(result, {}, frame_size=observation.frame_size)[0]
        target = projection['targets'].get(label)
        if target is None or target.get('mm') is None or not projection.get('calibration_id'):
            raise ValueError('Selected locked control has no compatible experimental mapping')
        element = frozen.element(target, screen, layout)
        sample = dict(session_id=session_id, screen=screen, target=target,
            visibility=projection['visibility'], calibration_id=projection['calibration_id'],
            experimental_registration_id=projection.get('experimental_registration_id'),
            calibration_error=self.projector.error, capture_index=observation.capture_index,
            received_at=observation.received_at, upstream_age_seconds=observation.upstream_age_seconds,
            frame_size=list(observation.frame_size), source_info=deepcopy(self.source_info),
            geometry={side:deepcopy(observation.result[side+'_display']['geometry']['corners'])
                      for side in ('left','right')},
            lock_generation=layout['generation'], locked_element=element,
            locked_snapshot_token=frozen.token, authorization='operator_fixed_setup_locked_snapshot')
        self.validate_frozen_sample(sample)
        return sample

    def validate_frozen_sample(self, sample):
        with self._condition:
            frozen = self._valid_frozen()
            if (frozen is None or sample.get('locked_snapshot_token') != frozen.token
                    or sample['session_id'] != frozen.observation.session_id
                    or sample['source_info'] != self.source_info):
                raise ValueError('Locked snapshot invalidated; reacquire before pressing')
            v2_targets.validate_layout(self._lock_layout, sample, enabled=self._locked_actions)

    def begin_locked_action(self):
        with self._condition:
            if self._freeze_on_lock:
                if self._valid_frozen() is None or self._frozen_action:
                    raise ValueError('No available completed lock for this action')
                self._frozen_action = True

    def end_locked_action(self, *, uncertain=False):
        with self._condition:
            if not self._freeze_on_lock:
                return
            self._frozen_action = False
            self._invalidate_layout('action_uncertain' if uncertain else 'action_completed')
            self._observation = self._projection = None
            self._press_history.clear()
            self._mode = {}
            self._state = 'action_recovery_required' if uncertain else 'acquiring'
            if uncertain:
                self._calibration_invalidated = True
            # Frames acquired during motion cannot seed the next lock.
            if self._packet is not None:
                self._last_taken = self._packet.capture_index
            self._condition.notify_all()

    def prepare_experimental_sample(self, session_id, screen, label) -> dict:
        """Reuse direct evidence, or ask the sole worker for one full verification.

        No camera is opened here and no old observation is renewed. Timeout/loss
        fails this request; there is no retry loop or physical command.
        """
        if self._freeze_on_lock:
            # Never request a fresh frame for the operator-authorized frozen route.
            return self.experimental_press_sample(session_id, screen, label)
        if not self._locked_actions:
            return self.experimental_press_sample(session_id, screen, label)
        try:
            return self.experimental_press_sample(session_id, screen, label)
        except ValueError:
            with self._condition:
                if self._stop.is_set() or self._calibration_invalidated or not self.running:
                    raise
                if self._action_full_request is not None:
                    raise ValueError('An action verification is already running')
                request = object()
                baseline = self._last_taken
                self._action_full_request = request
                self._condition.notify_all()
                try:
                    completed = self._condition.wait_for(lambda: self._stop.is_set() or (
                        self._action_full_request is not request and self._observation is not None
                        and self._observation[0].capture_index > baseline), timeout=3.)
                    if not completed or self._stop.is_set():
                        raise ValueError('No fresh full action verification; no press sent')
                finally:
                    if self._action_full_request is request:
                        self._action_full_request = None
            return self.experimental_press_sample(session_id, screen, label)

    def validate_locked_sample(self, sample: dict) -> None:
        """Recheck the same cache generation; a cache never supplies direct proof."""
        if 'lock_generation' not in sample:
            return
        with self._condition:
            v2_targets.validate_layout(self._lock_layout or {}, sample, enabled=self._locked_actions)

    def experimental_press_sample(self, session_id, screen, label):
        """Direct button proof with an independently confirmed V2 destination."""
        from dmi_robot_master.integration.shared.projection.recorded_test import RecordedTestProjector
        from dmi_robot_master.integration.shared.calibration.calibration import transform_point
        if self._freeze_on_lock:
            return self._frozen_press_sample(session_id, screen, label)
        with self._condition:
            view = self.snapshot(experimental_action=True)
            projection = view.get('projection') or {}
            if (type(self.projector) is not RecordedTestProjector or not view['fresh']
                    or view['session_id'] != session_id or projection.get('screen') != screen
                    or view['calibration_error'] or self._calibration_invalidated):
                raise ValueError('No fresh experimental screen/mapping for the selected button')
            latest = self._observation[0]
            current_target = projection.get('targets', {}).get(label)
            if current_target and current_target.get('active', True) is not True:
                raise ValueError('Selected button is inactive or uncertain')
            sample = None
            for misses, (observed, projected, source) in enumerate(reversed(self._press_history)):
                if (not self._same_press_context(observed, latest) or source != self.source_info
                        or projected.get('calibration_id') != projection.get('calibration_id')
                        or projected.get('experimental_registration_id') != projection.get('experimental_registration_id')):
                    break
                target = deepcopy(projected['targets'].get(label))
                confirmation = bool(target and self._locked_actions and self.projector.stable_registration
                                    and v2_targets.is_confirmation(target, screen))
                if not target or (target['kind'] != 'button' and not confirmation):
                    continue
                name = f'digit_{label[4:]}' if label.startswith('KEY_') else label.rsplit('/', 1)[-1]
                direct = observed.direct_evidence.get(f"{target['display']}_buttons", {})
                pixel = observed.direct_evidence.get('right_field') if confirmation else direct.get(name)
                if pixel is None:
                    continue
                age = time.monotonic() - observed.received_at + observed.upstream_age_seconds
                tolerance, lifetime = self.experimental_action_limits()
                if (not 0 <= age <= lifetime or target.get('active', True) is not True
                        or projected.get('calibration_id') is None):
                    raise ValueError('Latest direct button evidence expired or is ineligible')
                # Use precise direct coordinates, never a displayed/retained annotation centre.
                target['pixel'] = list(pixel)
                locked = None
                element = "right_display/data_field" if confirmation else f"{target['display']}_display/buttons/{name}"
                layout = self._lock_layout or {}
                if self._locked_actions and self.projector.stable_registration:
                    locked = v2_targets.locked_center(
                        layout, screen=screen, observation=observed, display=target['display'],
                        name=name, pixel=pixel, direct=({'input': pixel, **{f'button/{key}': value for key, value in direct.items()}}
                                if confirmation else direct),
                        tolerance=tolerance, field=confirmation)
                if confirmation and locked is None:
                    raise ValueError('Input confirmation field is not locked yet')
                if locked is not None:
                    target['pixel'] = locked
                sample = {'session_id': session_id, 'screen': screen, 'target': target,
                    'visibility': projected['visibility'],
                    'direct_screen': observed.direct_evidence.get('right_state'),
                    'direct_visibility': observed.direct_evidence.get('right_visibility'),
                    'direct_buttons': deepcopy(direct), 'calibration_id': projected['calibration_id'],
                    **({'experimental_registration_id': projected.get('experimental_registration_id')}
                       if self.projector.stable_registration else {}),
                    'calibration_error': view['calibration_error'], 'capture_index': observed.capture_index,
                    'received_at': observed.received_at, 'upstream_age_seconds': observed.upstream_age_seconds,
                    'frame_size': list(observed.frame_size), 'source_info': deepcopy(source),
                    'geometry': {side: deepcopy(observed.result[f'{side}_display']['geometry']['corners'])
                                 for side in ('left', 'right')},
                    'latest_capture_index': latest.capture_index, 'missed_updates': misses}
                if confirmation:
                    sample['direct_field'] = deepcopy(pixel)
                if locked is not None:
                    sample.update(lock_generation=layout['generation'], locked_element=element)
                break
            if sample is None:
                raise ValueError('Selected button missing from the latest three detections; no press sent')
        with self._project_lock:
            document, _ = self.projector.load()
            registration = self.projector.registration(document, sample['geometry'], sample['frame_size'],
                                                      require_left=target['display'] == 'left')
            target['mm'] = transform_point(document['models']['homography']['matrix'],
                                          transform_point(registration, target['pixel']))
        return sample

    def calibration_sample(self, session_id: str, screen: str, label: str) -> dict:
        """Detach one current point; collection must recheck its age before use."""
        target = self.inspect_target(session_id, screen, label)
        with self._condition:
            view = self.snapshot()
            if (not view['fresh'] or view['session_id'] != session_id
                    or view['capture_index'] != target['capture_index']):
                raise ValueError('Observation changed while collecting; select again')
            observed = self._observation[0]
            if not connected_regions(observed.result):
                raise ValueError('Calibration requires current measured joined SENSE regions')
            if target['display'] == 'right' and target['kind'] == 'field':
                raw = observed.direct_evidence.get('right_field')
                if raw is None or max(abs(a-b) for a,b in zip(raw,target['pixel'])) > 4:
                    raise ValueError('Field lacks matching current direct geometry')
            return {'session_id':session_id, 'screen':screen, 'target':target,
                'visibility':view['projection']['visibility'],
                'direct_screen':observed.direct_evidence.get('right_state'),
                'direct_visibility':observed.direct_evidence.get('right_visibility'),
                'direct_buttons':deepcopy(observed.direct_evidence.get(f"{target['display']}_buttons", {})),
                'calibration_id':view['projection'].get('calibration_id'),
                **({'experimental_registration_id': view['projection'].get('experimental_registration_id')}
                   if getattr(self.projector, 'stable_registration', False) else {}),
                'calibration_error':view['calibration_error'],
                'modes':deepcopy(self._mode),
                'capture_index':observed.capture_index, 'received_at':observed.received_at,
                'upstream_age_seconds':observed.upstream_age_seconds,
                'frame_size':list(observed.frame_size), 'source_info':deepcopy(self.source_info),
                'geometry':{side:deepcopy(observed.result[f'{side}_display']['geometry']['corners'])
                            for side in ('left','right')}}

    def action_observation(self) -> dict:
        """Detached fresh SENSE feedback; this method never grants action authority."""
        with self._condition:
            view = self.snapshot()
            if not view['fresh'] or not connected_regions(self._observation[0].result):
                raise ValueError('No fresh measured SENSE feedback')
            observed = self._observation[0]
            return {'session_id':observed.session_id,'capture_index':observed.capture_index,
                'received_at':observed.received_at,'upstream_age_seconds':observed.upstream_age_seconds,
                'source_info':deepcopy(self.source_info),'frame_size':list(observed.frame_size),
                'calibration_id':view['projection'].get('calibration_id'),
                'calibration_error':view['calibration_error'],'modes':deepcopy(self._mode),
                'geometry':{side:deepcopy(observed.result[f'{side}_display']['geometry']['corners'])
                            for side in ('left','right')}}
