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
from dmi_computer_vision.src.dmi.mode_observation import ModeHistory, observe_modes
from dmi_computer_vision.src.dmi.output.annotation import annotate_frame
from dmi_robot_master.integration.targets import TargetProjector


def _jpeg(image):
    height, width = image.shape[:2]
    scale = min(1., 960 / width)
    small = cv2.resize(image, (round(width*scale), round(height*scale))) if scale < 1 else image
    ok, data = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise ValueError('Preview JPEG encoding failed')
    return data.tobytes()


class VisionObserver:
    """One source, one detector, one render worker; each input has one latest slot.

    Stop/loss invalidates readers immediately. In-flight analysis cannot republish
    after invalidation. Lifecycle callers must join before starting a replacement.
    Native acquisition may finish its bounded timeout after stop; never kill threads.
    """
    def __init__(self, source, source_info: dict, *, calibration_path=None,
                 context=None, geometry_tolerance_px=4., debug_jsonl=None,
                 session_factory=VisionSession):
        self.source, self.source_info = source, deepcopy(source_info)
        self.projector = TargetProjector(source_info=source_info, calibration_path=calibration_path,
            context=context, geometry_tolerance_px=geometry_tolerance_px)
        self.session_factory = session_factory
        self.debug_jsonl = Path(debug_jsonl) if debug_jsonl else None
        self._condition = Condition()
        self._project_lock = Lock()
        self._stop = Event()
        self._threads = []
        self._packet = self._observation = self._projection = None
        self._raw_jpeg = self._annotation_jpeg = None
        self._raw_index = self._annotation_index = -1
        self._raw_received = None
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
            self._raw_jpeg = self._annotation_jpeg = None
            self._mode = {}
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
                        projection, _ = self.projector.project(observation.result,
                            observation.direct_evidence, frame_size=observation.frame_size)
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
                    duration = time.monotonic()-started
                    with self._condition:
                        if self._stop.is_set():
                            break
                        self._analysis_count += 1
                        self._analysis_total += duration
                        self._samples.append(duration)
                        del self._samples[:-256]
                        self._observation = (observation, packet.image)
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
        try:
            while not self._stop.wait(.125):
                with self._condition:
                    packet, observed = self._packet, self._observation
                    modes = deepcopy(self._mode)
                    raw_index, annotation_index = self._raw_index, self._annotation_index
                raw = (_jpeg(packet.image) if packet is not None
                       and packet.capture_index != raw_index else None)
                annotated = None
                if observed is not None and observed[0].capture_index != annotation_index:
                    image = annotate_frame(observed[1], observed[0].result)
                    for box, icon in modes.get('observations', {}).items():
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
                        self._annotation_jpeg = annotated
                        self._annotation_index = observed[0].capture_index
        except Exception as exc:
            self.invalidate('preview_error', str(exc))

    def snapshot(self) -> dict:
        """Small detached GUI view; expired evidence has no targets/annotation."""
        now = time.monotonic()
        with self._condition:
            observed = self._observation[0] if self._observation else None
            age = observed.age_seconds() if observed else None
            fresh = observed is not None and 0 <= age <= 1.5 and not self._stop.is_set()
            raw_age = (now-self._raw_received+self._raw_upstream_age
                       if self._raw_received is not None else None)
            projection = deepcopy(self._projection) if fresh else None
            annotation = (self._annotation_jpeg if fresh and
                          self._annotation_index == observed.capture_index else None)
            elapsed = max(.001, now-self._started) if self._started else 1.
            return {'state': 'stale' if observed and not fresh else self._state,
                'error': self._error, 'fresh': fresh, 'age_seconds': age,
                'session_id': observed.session_id if fresh else None,
                'capture_index': observed.capture_index if fresh else None,
                'projection': projection, 'modes': deepcopy(self._mode) if fresh else {},
                'raw_jpeg': self._raw_jpeg if raw_age is not None and raw_age <= 1.5 else None,
                'raw_index': self._raw_index, 'annotation_jpeg': annotation,
                'calibration_error': self.projector.error,
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
            projection, _ = self.projector.project(observation.result,
                observation.direct_evidence, frame_size=observation.frame_size)
        with self._condition:
            current = self.snapshot()
            if (not current['fresh'] or current['session_id'] != session_id
                    or current['capture_index'] != observation.capture_index):
                raise ValueError('Observation changed during selection; select again')
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
