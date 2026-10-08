"""Observation sources. Acquisition owns frames; detection owns no device."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from threading import Condition, Event, Thread
import time

import cv2

from dmi_computer_vision.src.dmi.io.camera import CapturedFrame, LatestCamera
from dmi_computer_vision.src.dmi.detection.display_geometry import Frame
from dmi_computer_vision.src.dmi.utils.image_ops import validate_frame


@dataclass(frozen=True)
class IntegrationFrame(CapturedFrame):
    received_at_utc: str
    source_video_seconds: float | None = None
    remote_capture_age_seconds: float = 0.0
    transport_round_trip_seconds: float = 0.0


def utc_at_receipt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def orient_image(image: Frame, rotation: int, mirror: bool) -> Frame:
    validate_frame(image)
    if rotation not in (0, 90, 180, 270):
        raise ValueError('Rotation must be 0, 90, 180 or 270 degrees clockwise')
    rotations = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    if rotation:
        image = cv2.rotate(image, rotations[rotation])
    if mirror:
        image = cv2.flip(image, 1)
    return image


class ReplayCamera:
    """Paced decoded frames in one pending slot, with local receipt timestamps.

    Video time is decoded index / source FPS and is preserved separately. A slow
    consumer skips captures, as with LatestCamera. EOF drains the final slot.
    """
    def __init__(self, path: str | Path, *, replay_fps: float | None = None,
                 start_seconds: float = 0.0, rotation: int = 0, mirror: bool = False,
                 timeout: float = 5.0) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        for value in (timeout, replay_fps):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError('Timeout and replay FPS must be finite and positive')
        if not math.isfinite(start_seconds) or start_seconds < 0:
            raise ValueError('Start time must be finite and nonnegative')
        if rotation not in (0, 90, 180, 270):
            raise ValueError('Invalid rotation')
        self.replay_fps, self.start_seconds = replay_fps, start_seconds
        self.rotation, self.mirror, self.timeout = rotation, mirror, timeout
        self._condition, self._stop = Condition(), Event()
        self._thread = None
        self._pending = None
        self._error = None
        self._ended = False
        self._captured = self._delivered = self._overwritten = 0
        self.source_fps = None
        self.last_packet = None

    def __enter__(self) -> ReplayCamera:
        if self._thread is not None:
            raise RuntimeError('Create a new source for each session')
        self._thread = Thread(target=self._capture, name='dmi-replay', daemon=True)
        self._thread.start()
        return self

    def _capture(self) -> None:
        capture = None
        try:
            capture = cv2.VideoCapture(str(self.path))
            if not capture.isOpened():
                raise RuntimeError(f'Cannot open recording: {self.path}')
            self.source_fps = capture.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(self.source_fps) or self.source_fps <= 0:
                raise ValueError('Recording needs valid source FPS for original video time')
            start_index = int(self.start_seconds * self.source_fps)
            # Decode sequentially to avoid backend-dependent keyframe seeking.
            for _ in range(start_index):
                if self._stop.is_set():
                    return
                if not capture.read()[0]:
                    raise ValueError('Start time is past recording EOF')
            period = 1.0 / (self.replay_fps or self.source_fps)
            index = 0
            while not self._stop.is_set():
                started = time.monotonic()
                ok, image = capture.read()
                if not ok:
                    break
                received_at = time.monotonic()
                received_utc = utc_at_receipt()
                image = orient_image(image, self.rotation, self.mirror)
                packet = IntegrationFrame(image, index, received_at, received_utc,
                                          (start_index + index) / self.source_fps)
                with self._condition:
                    if self._stop.is_set():
                        break
                    self._captured += 1
                    if self._pending is not None:
                        self._overwritten += 1
                    self._pending = packet
                    self._condition.notify_all()
                index += 1
                # No catch-up bursts when decoding itself is slower than playback.
                self._stop.wait(max(0.0, period - (time.monotonic() - started)))
        except Exception as exc:
            with self._condition:
                self._error = exc
        finally:
            if capture is not None:
                capture.release()
            with self._condition:
                self._ended = True
                self._condition.notify_all()

    def read(self) -> IntegrationFrame:
        if self._thread is None:
            raise RuntimeError('Open the source with a with block')
        deadline = time.monotonic() + self.timeout
        with self._condition:
            while self._pending is None and not self._ended and not self._stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('Replay timed out waiting for a frame')
                self._condition.wait(remaining)
            if self._error is not None:
                raise RuntimeError(str(self._error)) from self._error
            if self._stop.is_set():
                raise RuntimeError('Replay is closed')
            if self._pending is None:
                raise EOFError('Recording ended')
            packet, self._pending = self._pending, None
            self._delivered += 1
        if time.monotonic() - packet.received_at > self.timeout:
            raise RuntimeError('Replay frame is stale')
        self.last_packet = packet
        return packet

    def stats(self) -> dict:
        with self._condition:
            return {'captured_frames': self._captured, 'dequeued_frames': self._delivered,
                    'overwritten_frames': self._overwritten,
                    'pending_frames': int(self._pending is not None)}

    def close(self) -> None:
        self._stop.set()
        with self._condition:
            self._pending = None
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                raise RuntimeError('Replay decoder is blocked; exit process to release it')

    def __exit__(self, *args):
        self.close()


class RobotCamera:
    """Reuse local integer-index LatestCamera; never treat a URL as an index."""
    def __init__(self, index: int, *, width: int | None = None,
                 height: int | None = None, rotation: int = 0,
                 mirror: bool = False, timeout: float = 5.0) -> None:
        if rotation not in (0, 90, 180, 270):
            raise ValueError('Invalid rotation')
        self.camera = LatestCamera(index, width=width, height=height, timeout=timeout)
        self.rotation, self.mirror = rotation, mirror
        self.last_packet = None
        # Translate the existing camera's local monotonic receipt time to UTC.
        self._utc_offset = time.time() - time.monotonic()

    def __enter__(self) -> RobotCamera:
        self.camera.__enter__()
        return self

    def read(self) -> IntegrationFrame:
        packet = self.camera.read()
        utc = datetime.fromtimestamp(packet.received_at + self._utc_offset, timezone.utc)
        self.last_packet = IntegrationFrame(
            orient_image(packet.image, self.rotation, self.mirror),
            packet.capture_index, packet.received_at,
            utc.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        )
        return self.last_packet

    def stats(self) -> dict:
        return self.camera.stats()

    def __exit__(self, *args):
        self.camera.close()


class RemoteCamera:
    """Poll the Pi's latest JPEG on demand; no growing network frame queue.

    Indices identify actual captures: repeated HTTP replies never renew evidence.
    Server-reported age plus round-trip delay bounds freshness conservatively.
    This source uses the matching frame_bridge, not arbitrary stream URLs.
    """
    MAX_JPEG_BYTES = 16 * 1024 * 1024

    def __init__(self, url: str, *, timeout: float = 5.0, max_age_seconds: float = 1.0,
                 rotation: int = 0, mirror: bool = False) -> None:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path != '/frame.jpg':
            raise ValueError('Use the frame bridge HTTP(S) /frame.jpg URL')
        if any(not math.isfinite(v) or v <= 0 for v in (timeout, max_age_seconds)):
            raise ValueError('Timeout and age limit must be finite and positive')
        if rotation not in (0, 90, 180, 270):
            raise ValueError('Invalid rotation')
        self.url, self.timeout, self.max_age_seconds = url, timeout, max_age_seconds
        self.rotation, self.mirror = rotation, mirror
        self.last_packet = None
        self._stop = Event()
        self._previous_index = -1
        self._base_index = None
        self._remote_session = None
        self._captured = self._delivered = self._skipped = 0
        self._entered = False

    def __enter__(self) -> RemoteCamera:
        if self._entered:
            raise RuntimeError('Create a new remote source for each session')
        self._entered = True
        return self

    def read(self) -> IntegrationFrame:
        from urllib.request import Request, urlopen
        import numpy as np
        if not self._entered or self._stop.is_set():
            raise RuntimeError('Remote source is not open')
        deadline = time.monotonic() + self.timeout
        while not self._stop.is_set():
            started = time.monotonic()
            remaining = deadline - started
            if remaining <= 0:
                raise RuntimeError('Remote camera stopped producing new captures')
            with urlopen(Request(self.url, headers={'Cache-Control': 'no-cache'}), timeout=remaining) as response:
                if response.headers.get('Content-Type') != 'image/jpeg':
                    raise ValueError('Bridge did not supply JPEG')
                session = response.headers['X-Camera-Session']
                index = int(response.headers['X-Capture-Index'])
                source_age = float(response.headers['X-Capture-Age-Seconds'])
                data = response.read(self.MAX_JPEG_BYTES + 1)
            received_at = time.monotonic()
            utc = utc_at_receipt()
            if len(data) > self.MAX_JPEG_BYTES:
                raise ValueError('Remote JPEG exceeds bounded size')
            if not session:
                raise ValueError("Missing remote camera session")
            if self._remote_session is not None and session != self._remote_session:
                raise RuntimeError("Remote camera session changed; start a new PC session")
            if index < 0 or not math.isfinite(source_age) or source_age < 0:
                raise ValueError('Invalid remote capture metadata')
            if index < self._previous_index:
                raise RuntimeError('Remote camera restarted; start a new PC session')
            if source_age + (received_at - started) > self.max_age_seconds:
                raise RuntimeError('Remote source frame is stale including transport delay')
            if index == self._previous_index:
                self._stop.wait(min(0.02, max(0, deadline - time.monotonic())))
                continue
            image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            image = orient_image(image, self.rotation, self.mirror)
            if self._base_index is None:
                self._base_index = index
            else:
                self._skipped += index - self._previous_index - 1
            local_index = index - self._base_index
            self._captured = local_index + 1
            self._delivered += 1
            self._previous_index = index
            self._remote_session = session
            self.last_packet = IntegrationFrame(
                image, local_index, received_at, utc,
                remote_capture_age_seconds=source_age,
                transport_round_trip_seconds=received_at - started,
            )
            return self.last_packet
        raise RuntimeError('Remote source is closed')

    def stats(self) -> dict:
        # Inferred capture span since the first PC observation, not a measured rate.
        return {'captured_frames': self._captured, 'dequeued_frames': self._delivered,
                'overwritten_frames': self._skipped, 'pending_frames': 0}

    def __exit__(self, *args):
        self._stop.set()
        self.last_packet = None
