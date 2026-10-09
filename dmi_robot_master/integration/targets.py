"""Current robot-consumer projection, atomic files and conservative readers."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
from threading import Lock
import tempfile

from dmi_robot_master.integration.calibration import ValidatedCalibration, REFERENCE_PATH, read_json
from dmi_robot_master.integration.publication import ChangePublisher, project_pixels
from dmi_computer_vision.src.dmi.output.json_writer import close_coordinates


def utc_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Missing source-frame UTC timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('Timestamp must have UTC timezone')
    return parsed


def _point(value) -> list:
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('Expected finite numeric [x, y] coordinates')
    return list(value)


class TargetProjector:
    """Use the current detector result/evidence, never a historical log record."""
    def __init__(self, *, source_info: dict, calibration_path: str | Path | None = None,
                 context: dict | None = None, geometry_tolerance_px: float | None = None) -> None:
        if geometry_tolerance_px is not None and (not math.isfinite(geometry_tolerance_px) or geometry_tolerance_px <= 0):
            raise ValueError('Evidence geometry tolerance must be finite and positive')
        self.source_info = deepcopy(source_info)
        self.simulation = bool(source_info.get('simulation', source_info.get('kind') == 'recorded_replay'))
        self.calibration_path = Path(calibration_path).expanduser().resolve() if calibration_path is not None else None
        self.context = deepcopy(context)
        self.geometry_tolerance = geometry_tolerance_px
        self._file_stat = None
        self._document = None
        self._cache = None
        self.error = None
        self._prepare_failure = None

    def _prepare_uncached(self, size: tuple[int, int]) -> None:
        if self.calibration_path is None:
            raise ValueError('No calibration configured')
        stat = self.calibration_path.stat()
        fingerprint = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if fingerprint != self._file_stat:
            self._cache = None
            self._document = read_json(self.calibration_path)
            self._file_stat = fingerprint
        if not self.context or not isinstance(self.context.get('camera'), dict) or not isinstance(self.context.get('origin'), dict):
            raise ValueError('Independent current camera/origin context is required')
        camera, origin = self.context['camera'], self.context['origin']
        settings = camera.get('settings', {})
        if (settings.get('rotation_clockwise', 0) != self.source_info.get('rotation_clockwise', 0) or
                settings.get('mirror_horizontal', False) != self.source_info.get('mirror_horizontal', False) or
                settings.get('crop') is not None):
            raise ValueError('Current image orientation/crop differs from context')
        source_kind = self.source_info.get('kind')
        if source_kind not in ('recorded_replay', 'local_camera', 'remote_bridge', 'synthetic'):
            raise ValueError('Unsupported calibration source kind')
        if camera.get('source_kind') != source_kind:
            raise ValueError('Current source kind differs from calibration camera context')
        if source_kind == 'local_camera':
            index = self.source_info.get('index')
            requested_size = self.source_info.get('requested_size')
            if (type(index) is not int or index < 0 or type(settings.get('camera_index')) is not int or
                    settings['camera_index'] != index):
                raise ValueError('Current local camera index differs from calibration context')
            if (not isinstance(requested_size, list) or len(requested_size) != 2 or
                    any(v is not None and (type(v) is not int or v <= 0) for v in requested_size) or
                    (requested_size[0] is None) != (requested_size[1] is None) or
                    'requested_size' not in settings or settings['requested_size'] != requested_size):
                raise ValueError('Current requested camera size differs from calibration context')
        elif source_kind == 'remote_bridge':
            endpoint = self.source_info.get('url')
            if not isinstance(endpoint, str) or not endpoint or settings.get('bridge_url') != endpoint:
                raise ValueError('Current bridge endpoint differs from calibration context')
        elif source_kind == 'recorded_replay':
            identity = 'simulation:' + str(Path(self.source_info['path']).expanduser().resolve())
            if camera.get('identity') != identity or camera.get('source_kind') != 'recorded_replay':
                raise ValueError('Recording identity differs from independent current context')
        if self._cache is None:
            self._cache = ValidatedCalibration(self._document, frame_size=size, camera=camera,
                                               origin=origin, hardware=not self.simulation)
        self._cache.check_context(frame_size=size, camera=camera, origin=origin)

    def _prepare(self, size: tuple[int, int]) -> None:
        def fingerprint(path):
            try:
                stat = path.stat()
                return stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
            except OSError:
                return None
        key = (size, json.dumps(self.context, sort_keys=True),
               json.dumps(self.source_info, sort_keys=True),
               fingerprint(self.calibration_path) if self.calibration_path else None,
               fingerprint(REFERENCE_PATH))
        if self._prepare_failure is not None and self._prepare_failure[0] == key:
            raise ValueError(self._prepare_failure[1])
        try:
            self._prepare_uncached(size)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._prepare_failure = (key, str(exc))
            raise
        self._prepare_failure = None

    def project(self, result: dict, evidence: dict, *, frame_size: tuple[int, int]) -> tuple[dict, dict]:
        snapshot = project_pixels(result, frame_size=frame_size)
        snapshot.update(simulation=self.simulation, calibration_valid=False,
                        calibration_provenance=None)
        for target in snapshot['targets'].values():
            target.pop('icon', None)
            target['mm'] = None
            _point(target['pixel'])
        support = {}
        error = None
        try:
            self._prepare(frame_size)
            snapshot.update(calibration_id=self._cache.calibration_id,
                            calibration_provenance=self._cache.provenance, calibration_valid=True)
            # Calibration applies only to the current right Driver ID plane.
            if snapshot['screen'] == 'Driver ID' and snapshot['visibility'] == 'clear':
                centers = {label: target['pixel'] for label, target in snapshot['targets'].items()
                           if target['display'] == 'right' and self._cache.contains(target['pixel'])}
                millimeters = self._cache.convert_centers(centers, frame_size=frame_size,
                    camera=self.context['camera'], origin=self.context['origin'])
                for label, mm in millimeters.items():
                    snapshot['targets'][label]['mm'] = mm
                if self.geometry_tolerance is not None and evidence.get('right_state') == 'Driver ID' and evidence.get('right_visibility') == 'clear':
                    observed = {f'KEY_{name[6:]}': _point(pixel)
                                for name, pixel in evidence.get('right_buttons', {}).items()
                                if name in {f'digit_{n}' for n in range(10)}}
                    self._cache.recheck(observed, tolerance_px=self.geometry_tolerance)
                    if evidence.get('right_field') is not None:
                        observed['right/field/input'] = _point(evidence['right_field'])
                    for label, raw_pixel in observed.items():
                        target = snapshot['targets'].get(label)
                        if target is not None and target['mm'] is not None and close_coordinates(
                                target['pixel'], raw_pixel, self.geometry_tolerance):
                            target['usable'] = True
                            support[label] = raw_pixel
        except (OSError, ValueError, KeyError, TypeError) as exc:
            error = str(exc)
            # Invalid calibration/context/geometry cannot retain previously mapped mm.
            for target in snapshot['targets'].values():
                target['mm'], target['usable'] = None, False
            support.clear()
            snapshot['calibration_valid'] = False
        if error != self.error and error is not None and self.calibration_path is not None:
            logging.warning('Target calibration unavailable: %s', error)
        self.error = error
        return snapshot, support


def atomic_json(path: str | Path, document: dict) -> None:
    """Serialize first and replace in the same directory; no partially read JSON."""
    path = Path(path)
    encoded = json.dumps(document, separators=(',', ':'), allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.'+path.name,
                                         suffix='.tmp', encoding='utf-8', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def target_snapshot(event: dict, simulation: bool) -> dict:
    targets = [{key: target[key] for key in ('label', 'kind', 'display', 'pixel', 'mm', 'usable')}
               for _, target in sorted(event['targets'].items())]
    return {'session_id': event['session_id'], 'revision': event['revision'],
            'frame_index': event.get('frame_index'), 'observed_at': event.get('observed_at'),
            'screen': event.get('screen', 'unknown'), 'calibration_id': event.get('calibration_id'),
            'simulation': event.get('simulation', simulation),
            'calibration_provenance': event.get('calibration_provenance'),
            'frame_size': event.get('frame_size'), 'targets': targets}


class CurrentTargets:
    """Retain this small interface to read the live in-memory exact centers."""
    def __init__(self) -> None:
        self._publisher = None
        self._lock = Lock()

    def bind(self, publisher: ChangePublisher) -> None:
        with self._lock:
            if self._publisher is not None:
                raise RuntimeError('CurrentTargets already belongs to a session')
            self._publisher = publisher

    def get(self) -> dict | None:
        with self._lock:
            publisher = self._publisher
        current = publisher.current() if publisher is not None else None
        return target_snapshot(current, current['simulation']) if current is not None else None

    def close(self) -> None:
        with self._lock:
            self._publisher = None


class TargetFiles:
    """Sink for change snapshots/status; each file has one authoritative revision."""
    def __init__(self, directory: str | Path, session_id: str, *, simulation: bool,
                 history: bool = False) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.session_id, self.simulation = session_id, simulation
        self.target_writes = self.status_writes = 0
        self._history = None
        if history:
            self._history = (self.directory / 'targets_history.jsonl').open('x', encoding='utf-8')
        try:
            self.emit({'type': 'targets', 'session_id': session_id, 'revision': 0,
                       'targets': {}, 'screen': 'unknown', 'observed_at': None,
                       'frame_index': None, 'calibration_id': None})
            self.emit({'type': 'status', 'session_id': session_id, 'revision': 0,
                       'source_status': 'starting', 'heartbeat_at': datetime.now(timezone.utc).isoformat(),
                       'published_supported_labels': []})
        except BaseException:
            self.close()
            raise

    def emit(self, event: dict) -> None:
        if event['session_id'] != self.session_id:
            raise ValueError('Target writer session mismatch')
        if event['type'] == 'targets':
            snapshot = target_snapshot(event, self.simulation)
            atomic_json(self.directory / 'targets.json', snapshot)
            self.target_writes += 1
            if self._history is not None:
                self._history.write(json.dumps(snapshot, separators=(',', ':'), allow_nan=False)+'\n')
                self._history.flush()
        elif event['type'] == 'status':
            atomic_json(self.directory / 'target_status.json', event)
            self.status_writes += 1
        else:
            raise ValueError('Unknown target publication event')

    def close(self) -> None:
        if self._history is not None:
            self._history.close()


def validate_current(snapshot: dict, status: dict, *, max_age_seconds: float = 1.5,
                     now_utc: datetime | None = None, hardware: bool = False) -> None:
    if not isinstance(snapshot, dict) or not isinstance(status, dict):
        raise ValueError('Current target/status documents must be objects')
    if not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ValueError('Consumer age limit must be finite and positive')
    now = now_utc or datetime.now(timezone.utc)
    if not isinstance(snapshot.get('session_id'), str) or not snapshot['session_id'] or type(snapshot.get('revision')) is not int or snapshot['revision'] < 0:
        raise ValueError('Invalid target session/revision')
    if type(status.get('revision')) is not int:
        raise ValueError('Invalid heartbeat revision')
    supported = status.get('published_supported_labels')
    if not isinstance(supported, list) or any(not isinstance(label, str) for label in supported) or len(supported) != len(set(supported)):
        raise ValueError('Invalid supporting label set')
    if snapshot['session_id'] != status['session_id'] or snapshot['revision'] != status['revision']:
        raise ValueError('Target/status session or revision mismatch; read again')
    if status['source_status'] != 'observed':
        raise ValueError('Target evidence is not current')
    elapsed = (now - utc_time(status['heartbeat_at'])).total_seconds()
    evidence_age = status['evidence_age_seconds']
    if (type(evidence_age) not in (int, float) or not math.isfinite(evidence_age) or
            evidence_age < 0 or elapsed < 0 or elapsed > max_age_seconds or
            evidence_age + elapsed > max_age_seconds):
        raise ValueError('Target/status evidence is stale or clocks disagree')
    # Snapshot receipt may be older than the heartbeat after a suppressed write.
    # The revision and supported labels prove current geometry agreement.
    source_time = utc_time(status['observed_at'])
    snapshot_time = utc_time(snapshot['observed_at'])
    heartbeat_time = utc_time(status['heartbeat_at'])
    if not snapshot_time <= source_time <= heartbeat_time <= now or (now - source_time).total_seconds() > max_age_seconds:
        raise ValueError('Source receipt UTC is stale, future or inconsistent')
    if type(snapshot['frame_index']) is not int or snapshot['frame_index'] < 0:
        raise ValueError('Invalid source frame index')
    if type(status.get('frame_index')) is not int or status['frame_index'] < snapshot['frame_index']:
        raise ValueError('Heartbeat does not support the snapshot source frame')
    if hardware and (snapshot.get('simulation') is not False or snapshot.get('calibration_provenance') != 'hardware'):
        raise ValueError('Hardware consumers reject simulation targets')
    if not isinstance(snapshot['targets'], list) or type(snapshot.get('simulation')) is not bool:
        raise ValueError('Invalid target snapshot schema')
    size = snapshot.get('frame_size')
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError('Invalid original frame dimensions')
    labels = set()
    for target in snapshot['targets']:
        label = target['label']
        if not isinstance(label, str) or not label or label in labels:
            raise ValueError('Missing or duplicate target label')
        labels.add(label)
        if target['kind'] not in ('button', 'field', 'box') or target['display'] not in ('left', 'right'):
            raise ValueError('Invalid target kind/display')
        _point(target['pixel'])
        if target['mm'] is not None:
            _point(target['mm'])
        if type(target['usable']) is not bool:
            raise ValueError('Target usability must be boolean')


def select_target(snapshot: dict, status: dict, label: str, *, max_age_seconds: float = 1.5,
                  now_utc: datetime | None = None, hardware: bool = False) -> dict:
    try:
        validate_current(snapshot, status, max_age_seconds=max_age_seconds, now_utc=now_utc, hardware=hardware)
        matches = [target for target in snapshot['targets'] if target['label'] == label]
        if len(matches) != 1:
            raise ValueError('Requested label is missing or ambiguous')
        target = matches[0]
        width, height = snapshot['frame_size']
        x, y = target['pixel']
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError('Selected target is outside original image')
        if (not snapshot['calibration_id'] or target['mm'] is None or not target['usable'] or
                label not in status.get('published_supported_labels', [])):
            raise ValueError('Target is uncalibrated, unusable or lacks recent supporting evidence')
        return deepcopy(target)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f'Malformed current targets/status: {exc}') from exc


def read_target(directory: str | Path, label: str, *, max_age_seconds: float = 1.5,
                now_utc: datetime | None = None, hardware: bool = False) -> dict:
    directory = Path(directory).expanduser().resolve()
    try:
        snapshot = read_json(directory / 'targets.json')
        status = read_json(directory / 'target_status.json')
    except (OSError, ValueError) as exc:
        raise ValueError(f'Current target/status files unavailable: {exc}') from exc
    return select_target(snapshot, status, label, max_age_seconds=max_age_seconds,
                         now_utc=now_utc, hardware=hardware)
