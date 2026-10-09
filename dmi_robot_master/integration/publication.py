"""In-memory change/freshness policy; Phase 4 will supply its target-file sink."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Event, Lock, Thread
import math
import time
import uuid

from dmi_computer_vision.src.dmi.output.json_writer import close_coordinates


def project_pixels(result: dict, *, frame_size: tuple[int, int], calibration_id=None,
                   include_field_values: bool = False) -> dict:
    """Small pixel projection; no calibration or motor eligibility is inferred."""
    left, right = result['left_display'], result['right_display']
    targets = {}
    for display, content in [('left', left), ('right', right)]:
        for name, button in content.get('buttons', {}).items():
            label = (f'KEY_{name[6:]}' if display == 'right' and name in {f'digit_{n}' for n in range(10)}
                     else f'{display}/button/{name}')
            targets[label] = {'label': label, 'kind': 'button', 'display': display,
                              'pixel': list(button['center']), 'usable': False}
    field = right.get('data_field')
    if field is not None:
        label = 'right/field/input'
        targets[label] = {'label': label, 'kind': 'field', 'display': 'right',
                          'pixel': list(field['center']), 'usable': False}
        if include_field_values:
            targets[label]['value'] = field.get('value')
    for name, box in left.get('boxes', {}).items():
        label = f'left/box/{name}'
        targets[label] = {'label': label, 'kind': 'box', 'display': 'left',
                          'pixel': list(box['center']), 'icon': box.get('icon'), 'usable': False}
    return {'screen': right['state'],
            'titles': {'right': right['title']['text'] if right['title'] else None,
                       'left': left['title']['text'] if left.get('title') else None},
            'visibility': right['visibility'],
            'displays_present': {'left': left['geometry'] is not None, 'right': right['geometry'] is not None},
            'frame_size': list(frame_size), 'calibration_id': calibration_id, 'targets': targets}


def meaningful_change(old: dict | None, new: dict, tolerance_px: float = 4.0) -> bool:
    """Semantics bypass tolerance; geometry compares to last published centers."""
    if not math.isfinite(tolerance_px) or tolerance_px < 0:
        raise ValueError('Publication tolerance must be finite and nonnegative')
    if old is None or old.keys() != new.keys():
        return True
    if any(old[key] != new[key] for key in new if key != 'targets'):
        return True
    if old['targets'].keys() != new['targets'].keys():
        return True
    for label, target in new['targets'].items():
        prior = old['targets'][label]
        if prior.keys() != target.keys():
            return True
        if any(prior[key] != target[key] for key in target if key not in ('pixel', 'mm')):
            return True
        if not close_coordinates(prior['pixel'], target['pixel'], tolerance_px):
            return True
        # mm is derived, not an independent jitter threshold. Calibration context
        # changes must update calibration_id/context metadata before comparison.
    return False


class ChangePublisher:
    def __init__(self, emit, *, session_id: str | None = None, tolerance_px: float = 4.0,
                 heartbeat_seconds: float = 0.5, max_evidence_age_seconds: float = 1.5) -> None:
        if not math.isfinite(tolerance_px) or tolerance_px < 0:
            raise ValueError('Invalid publication tolerance')
        for value in (heartbeat_seconds, max_evidence_age_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Heartbeat and evidence age limits must be positive')
        self.emit = emit
        self.session_id = session_id or uuid.uuid4().hex
        self.tolerance = tolerance_px
        self.heartbeat_seconds = heartbeat_seconds
        self.max_age = max_evidence_age_seconds
        self._lock = Lock()
        self._current = self._published = None
        self._received = self._detected = self._observed_utc = None
        self._upstream_age = 0.0
        self._frame_index = self._capture_index = None
        self._support_centers = None
        self._support_tolerance = None
        self._last_heartbeat = None
        self._expired = self._closed = False
        self.revision = self.updates = self.heartbeats = 0

    def _emit_targets(self, snapshot: dict, reason: str) -> None:
        self.revision += 1
        self.updates += 1
        self._published = deepcopy(snapshot)
        self.emit({'type': 'targets', 'session_id': self.session_id, 'revision': self.revision,
                   'reason': reason, 'observed_at': self._observed_utc,
                   'evidence_received_at_monotonic': self._received,
                   'frame_index': self._frame_index, 'capture_index': self._capture_index, **deepcopy(snapshot)})

    def update(self, snapshot: dict, *, received_at: float, detected_at: float,
               observed_at_utc: str | None = None, upstream_age_seconds: float = 0.0,
               frame_index: int | None = None, capture_index: int | None = None,
               support_centers: dict | None = None, support_tolerance_px: float | None = None) -> None:
        if not all(math.isfinite(v) for v in (received_at, detected_at, upstream_age_seconds)) or upstream_age_seconds < 0 or detected_at < received_at:
            raise ValueError('Invalid detection evidence timestamps')
        with self._lock:
            if self._closed:
                raise RuntimeError('Publisher closed')
            if self._received is not None and received_at <= self._received:
                raise ValueError('Evidence receipt times must increase')
            self._frame_index, self._capture_index = frame_index, capture_index
            self._support_centers, self._support_tolerance = deepcopy(support_centers), support_tolerance_px
            self._current = deepcopy(snapshot)
            self._received, self._detected = received_at, detected_at
            self._observed_utc, self._upstream_age = observed_at_utc, upstream_age_seconds
            if detected_at - received_at + upstream_age_seconds > self.max_age:
                self._invalidate('stale')
                return
            previously_usable = ({label for label, target in self._published['targets'].items() if target['usable']}
                                 if self._published is not None else set())
            lost_support = bool(previously_usable - set(self._supported_labels(self._published)))
            if self._expired or lost_support or meaningful_change(self._published, snapshot, self.tolerance):
                reason = 'recovered' if self._expired else 'support_changed' if lost_support else 'change'
                self._emit_targets(snapshot, reason)
            self._expired = False

    def _supported_labels(self, snapshot: dict | None) -> list[str]:
        if snapshot is None or self._expired:
            return []
        labels = []
        for label, target in snapshot['targets'].items():
            if not target['usable']:
                continue
            if self._support_centers is not None:
                observed = self._support_centers.get(label)
                if observed is None or self._support_tolerance is None or not close_coordinates(
                        target['pixel'], observed, self._support_tolerance):
                    continue
            labels.append(label)
        return sorted(labels)

    def _invalidate(self, reason: str) -> None:
        if not self._expired:
            empty = deepcopy(self._current) if self._current is not None else {'targets': {}}
            empty['targets'] = {}
            self._emit_targets(empty, reason)
        self._expired = True

    def tick(self, now: float | None = None, *, force: bool = False) -> None:
        with self._lock:
            now = time.monotonic() if now is None else now
            if self._closed:
                return
            age = None if self._received is None else now - self._received + self._upstream_age
            if age is not None and (age < 0 or age > self.max_age):
                self._invalidate('stale')
            if force or self._last_heartbeat is None or now - self._last_heartbeat >= self.heartbeat_seconds:
                self.emit({'type': 'status', 'session_id': self.session_id, 'revision': self.revision,
                           'last_detection_at_monotonic': self._detected,
                           'evidence_received_at_monotonic': self._received,
                           'observed_at': self._observed_utc, 'evidence_age_seconds': age,
                           'heartbeat_at': datetime.now(timezone.utc).isoformat(),
                           'frame_index': self._frame_index, 'capture_index': self._capture_index,
                           'published_supported_labels': self._supported_labels(self._published),
                           'source_status': 'stale' if self._expired else 'observed' if self._received is not None else 'starting'})
                self._last_heartbeat = now
                self.heartbeats += 1

    def current(self, now: float | None = None) -> dict | None:
        with self._lock:
            now = time.monotonic() if now is None else now
            if self._closed or self._expired or self._received is None or not 0 <= now - self._received + self._upstream_age <= self.max_age:
                return None
            snapshot = deepcopy(self._current)
            snapshot.update(frame_index=self._frame_index, capture_index=self._capture_index,
                            observed_at=self._observed_utc, session_id=self.session_id, revision=self.revision)
            return snapshot

    def close(self, reason: str = 'stopped') -> None:
        with self._lock:
            if not self._closed:
                self._invalidate(reason)
                self.emit({'type': 'status', 'session_id': self.session_id, 'revision': self.revision,
                           'source_status': reason, 'last_detection_at_monotonic': self._detected,
                           'heartbeat_at': datetime.now(timezone.utc).isoformat(),
                           'published_supported_labels': []})
                self._closed = True


class StatusHeartbeat:
    """Expires evidence even while camera/detection is blocked; no GUI calls."""
    def __init__(self, publisher: ChangePublisher) -> None:
        self.publisher = publisher
        self._stop = Event()
        self._thread = None
        self.error = None

    def __enter__(self):
        self._thread = Thread(target=self._run, name='dmi-status', daemon=True)
        self._thread.start()
        return self

    def _run(self):
        try:
            while not self._stop.is_set():
                self.publisher.tick()
                self._stop.wait(min(0.1, self.publisher.heartbeat_seconds))
        except Exception as exc:
            self.error = exc
            self._stop.set()

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join(timeout=1)
        if self._thread.is_alive():
            raise RuntimeError('Status callback is blocked; exit process to release it')
        failed = self.error is not None or (args and args[0] is not None)
        self.publisher.close('error' if failed else 'stopped')
        if self.error is not None and not args[0]:
            raise RuntimeError('Status publication failed') from self.error
