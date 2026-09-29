"""Bounded live acquisition: one pending frame, no detection or output logic."""
from __future__ import annotations

from dataclasses import dataclass
import math
from threading import Condition, Event, Thread
import time
import warnings

import cv2

from dmi.detection.display_geometry import Frame


@dataclass(frozen=True)
class CapturedFrame:
    image: Frame
    capture_index: int
    received_at: float  # monotonic seconds, measured after read(), not sensor time


class LatestCamera:
    """Continuously drain a camera while consumers process the latest frame.

    Only the worker owns VideoCapture. Open/read stalls time out for consumers;
    a backend stuck inside native code may not stop until the process exits.
    The one-slot buffer bounds application memory, not driver-side latency.
    """

    def __init__(self, camera_index: int = 0, *, width: int | None = None,
                 height: int | None = None, timeout: float = 5.0) -> None:
        if type(camera_index) is not int or camera_index < 0:
            raise ValueError("camera_index must be a non-negative integer")
        if (width is None) != (height is None):
            raise ValueError("request both width and height, or neither")
        for value in (width, height):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError("camera dimensions must be positive integers")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("camera timeout must be finite and positive")
        self.camera_index = camera_index
        self.width, self.height = width, height
        self.timeout = timeout
        self._condition = Condition()
        self._stop = Event()
        self._pending: CapturedFrame | None = None
        self._error: Exception | None = None
        self._thread: Thread | None = None

    def __enter__(self) -> LatestCamera:
        if self._thread is not None:
            raise RuntimeError("create a new LatestCamera for each session")
        self._thread = Thread(target=self._capture, name="dmi-camera", daemon=True)
        self._thread.start()
        return self

    def _capture(self) -> None:
        capture = None
        try:
            capture = cv2.VideoCapture(self.camera_index)
            if not capture.isOpened():
                raise RuntimeError(f"could not open camera {self.camera_index}; "
                                   "check device index and camera permissions")
            if self.width is not None:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            index = 0
            while not self._stop.is_set():
                ok, frame = capture.read()
                received_at = time.monotonic()
                if not ok or frame is None or frame.size == 0:
                    raise RuntimeError(f"camera {self.camera_index} stopped delivering frames")
                packet = CapturedFrame(frame, index, received_at)
                with self._condition:
                    self._pending = packet
                    self._condition.notify_all()
                index += 1
        except Exception as exc:
            with self._condition:
                self._error = exc
                self._condition.notify_all()
        finally:
            if capture is not None:
                capture.release()

    def read(self) -> CapturedFrame:
        if self._thread is None:
            raise RuntimeError("open the camera using a with block before reading")
        deadline = time.monotonic() + self.timeout
        with self._condition:
            while self._pending is None and self._error is None and not self._stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(f"camera {self.camera_index} timed out waiting for a frame")
                self._condition.wait(remaining)
            if self._error is not None:
                raise RuntimeError(str(self._error)) from self._error
            if self._stop.is_set():
                raise RuntimeError("camera is closed")
            packet = self._pending
            self._pending = None
        if time.monotonic() - packet.received_at > self.timeout:
            raise RuntimeError("camera's latest frame is stale")
        return packet

    def close(self) -> None:
        self._stop.set()
        with self._condition:
            self._pending = None
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                warnings.warn("Camera backend is still blocked in open/read; "
                              "exit this process to release the device.", RuntimeWarning)

    def __exit__(self, *args) -> None:
        self.close()
