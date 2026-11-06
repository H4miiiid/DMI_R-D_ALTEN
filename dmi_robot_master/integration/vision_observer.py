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
from dmi_computer_vision.src.dmi.mode_observation import ModeHistory, observe_modes, connected_regions
from dmi_computer_vision.src.dmi.output.annotation import annotate_frame
from dmi_computer_vision.src.dmi.output.json_writer import close_coordinates, compact_state
from dmi_computer_vision.src.dmi.output.preview_state import LivePreviewState
from dmi_robot_master.integration.camera import IntegrationFrame
from dmi_robot_master.integration.targets import TargetProjector
from dmi_robot_master.integration.publication import project_pixels


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
                 session_factory=VisionSession, stable_preview=False):
        self.source, self.source_info = source, deepcopy(source_info)
        self.projector = TargetProjector(source_info=source_info, calibration_path=calibration_path,
            context=context, geometry_tolerance_px=geometry_tolerance_px)
        self.session_factory = session_factory
        self.stable_preview = stable_preview
        self.debug_jsonl = Path(debug_jsonl) if debug_jsonl else None
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
            with self.session_factory(str(self.source_info)) as session:
                while not self._stop.is_set():
                    with self._condition:
                        self._condition.wait_for(lambda: self._stop.is_set() or (
                            self._packet is not None and self._packet.capture_index > self._last_taken))
                        if self._stop.is_set():
                            break
                        packet = self._packet
                        self._last_taken = packet.capture_index
                    started = time.monotonic()
                    observation = session.process(packet)
                    with self._project_lock:
                        calibration_epoch = self._calibration_epoch
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
                    duration = time.monotonic()-started
                    with self._condition:
                        if self._stop.is_set():
                            break
                        if (calibration_epoch != self._calibration_epoch
                                or observation.received_at - observation.upstream_age_seconds < self._origin_bound_at):
                            self._clear_mm(projection)
                        self._analysis_count += 1
                        self._analysis_total += duration
                        self._samples.append(duration)
                        del self._samples[:-256]
                        if projection.get('experimental_recorded_test'):
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
                        self._condition.notify_all()
                    if stream:
                        # Explicit debugging only; no runtime consumer reads this.
                        stream.write(json.dumps({'capture_index': observation.capture_index,
                            'received_at': observation.received_at,
                            'result': observation.result, 'modes': mode}, allow_nan=False)+'\n')
                        stream.flush()
        except Exception as exc:
            if not self._stop.is_set():
                self.invalidate('analysis_error', str(exc))
        finally:
            if stream:
                stream.close()

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
                if epoch != last_epoch:
                    preview.clear()
                    last_epoch = epoch
                raw = (_jpeg(packet.image) if packet is not None
                       and packet.capture_index != raw_index else None)
                annotated = None
                if stable and observed is not None and detection != last_detection:
                    observation, image = observed
                    # No queue: skipped detector publications count conservatively
                    # as missed updates for any control still absent in this one.
                    analyzed_packet = IntegrationFrame(image, observation.capture_index,
                        observation.received_at, '', remote_capture_age_seconds=observation.upstream_age_seconds)
                    preview.update(observation.result, analyzed_packet, evidence=observation.direct_evidence,
                                   updates=detection-last_detection)
                    last_detection = detection
                if not stable and observed is not None and observed[0].capture_index != annotation_index:
                    image = annotate_frame(observed[1], observed[0].result)
                    for box, icon in modes.get('observations', {}).items():
                        center = tuple(round(v) for v in icon['center'])
                        cv2.putText(image, f"{box}: {icon['mode'] or icon['status']}", center,
                                    cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 200, 255), 1, cv2.LINE_AA)
                    annotated = _jpeg(image)
                elif stable and packet is not None and (packet.capture_index != annotation_index or
                        detection != rendered_detection or time.monotonic() > render_deadline):
                    image = preview.render(packet)
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

    def snapshot(self) -> dict:
        """Fresh action observations and a separate display-only live composite."""
        now = time.monotonic()
        with self._condition:
            observed = self._observation[0] if self._observation else None
            age = observed.age_seconds() if observed else None
            fresh = observed is not None and 0 <= age <= 1.5 and not self._stop.is_set()
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
            if not self.stable_preview:
                annotation = (self._annotation_jpeg if fresh and
                              self._annotation_index == observed.capture_index and
                              (not self.stable_preview or self._annotation_epoch == self._preview_epoch) else None)
            experimental = getattr(self.projector, 'experimental_recorded_test', False)
            calibration_error = self.projector.error
            if self._calibration_invalidated:
                calibration_error = ('Robot origin changed; initialize the robot to restore experimental mapping'
                    if experimental else 'Robot origin/connection changed; reload independent context')
            elif observed and observed.received_at - observed.upstream_age_seconds < self._origin_bound_at:
                calibration_error = 'Waiting for a fresh detection after robot initialization'
            elapsed = max(.001, now-self._started) if self._started else 1.
            return {'state': 'stale' if observed and not fresh else self._state,
                'error': self._error, 'fresh': fresh, 'age_seconds': age,
                'session_id': observed.session_id if fresh else None,
                'capture_index': observed.capture_index if fresh else None,
                'projection': projection, 'modes': deepcopy(self._mode) if fresh else {},
                # Identity continuity only: this never authorizes a press or extends evidence age.
                'experimental_context': ([observed.session_id, self._projection['screen']]
                    if observed and self._projection and experimental else None),
                'ocr_fields': _ocr_fields(observed) if fresh else {},
                'raw_jpeg': raw,
                'raw_index': self._raw_index, 'annotation_jpeg': annotation,
                'calibration_error': calibration_error,
                'action_ready': False,
                'metrics': {'processed': self._analysis_count, 'overwrites': self._overwrites,
                    'analysis_mean_seconds': self._analysis_total/max(1, self._analysis_count),
                    'analysis_p95_seconds': float(np.percentile(self._samples, 95)) if self._samples else 0.,
                    'processed_fps': self._analysis_count/elapsed,
                    'preview_callbacks_fps': self._render_count/elapsed}}

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

    @staticmethod
    def _clear_mm(projection):
        projection.update(calibration_valid=False, calibration_id=None, calibration_provenance=None)
        for target in projection['targets'].values():
            target.update(mm=None, usable=False)

    def _project(self, observation):
        if self._calibration_invalidated:
            projection = project_pixels(observation.result, frame_size=observation.frame_size)
            projection.update(simulation=self.projector.simulation)
            self._clear_mm(projection)
            return projection
        return self.projector.project(observation.result,
            observation.direct_evidence, frame_size=observation.frame_size)[0]

    def invalidate_calibration(self) -> None:
        """Origin/connection changes clear mm, while camera/preview keep running."""
        with self._condition:
            self._calibration_epoch += 1
            self._calibration_invalidated = True
            self._press_history.clear()
            if self._projection:
                self._clear_mm(self._projection)

    def bind_experimental_origin(self, origin_epoch):
        """Called after confirmed homing; require new evidence without moving the camera anchor."""
        from dmi_robot_master.integration.recorded_test import RecordedTestProjector
        with self._condition:
            if type(self.projector) is not RecordedTestProjector or self._stop.is_set() or not origin_epoch:
                return False
            self._calibration_epoch += 1
            self._origin_bound_at = time.monotonic()
            self.projector.origin_epoch = origin_epoch
            self._calibration_invalidated = False
            self._press_history.clear()
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

    def experimental_press_sample(self, session_id, screen, label):
        """Latest direct button, through at most two misses and the original 1.5 s lifetime."""
        from dmi_robot_master.integration.recorded_test import RecordedTestProjector
        from dmi_robot_master.integration.calibration import transform_point
        with self._condition:
            view = self.snapshot()
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
                        or projected.get('calibration_id') != projection.get('calibration_id')):
                    break
                target = deepcopy(projected['targets'].get(label))
                if not target or target['kind'] != 'button':
                    continue
                name = f'digit_{label[4:]}' if label.startswith('KEY_') else label.rsplit('/', 1)[-1]
                direct = observed.direct_evidence.get(f"{target['display']}_buttons", {})
                pixel = direct.get(name)
                if pixel is None:
                    continue
                age = time.monotonic() - observed.received_at + observed.upstream_age_seconds
                if (not 0 <= age <= 1.5 or target.get('active', True) is not True
                        or projected.get('calibration_id') is None):
                    raise ValueError('Latest direct button evidence expired or is ineligible')
                # Use precise direct coordinates, never a displayed/retained annotation centre.
                target['pixel'] = list(pixel)
                sample = {'session_id': session_id, 'screen': screen, 'target': target,
                    'visibility': projected['visibility'],
                    'direct_screen': observed.direct_evidence.get('right_state'),
                    'direct_visibility': observed.direct_evidence.get('right_visibility'),
                    'direct_buttons': deepcopy(direct), 'calibration_id': projected['calibration_id'],
                    'calibration_error': view['calibration_error'], 'capture_index': observed.capture_index,
                    'received_at': observed.received_at, 'upstream_age_seconds': observed.upstream_age_seconds,
                    'frame_size': list(observed.frame_size), 'source_info': deepcopy(source),
                    'geometry': {side: deepcopy(observed.result[f'{side}_display']['geometry']['corners'])
                                 for side in ('left', 'right')},
                    'latest_capture_index': latest.capture_index, 'missed_updates': misses}
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
