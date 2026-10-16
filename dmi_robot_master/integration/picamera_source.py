"""Picamera2 acquisition for the Pi bridge; one copied, most recent BGR frame."""
from __future__ import annotations

import math
from threading import Condition
import time

from dmi_robot_master.integration.camera import IntegrationFrame, utc_at_receipt
from dmi_computer_vision.src.dmi.utils.image_ops import validate_frame

CAPTURE_SIZE = (2304, 1728)
CAPTURE_FPS = 30.0
EXPOSURE_EV = -2.0


class PicameraSource:
    def __init__(self, index: int, *, width: int | None = None,
                 height: int | None = None, timeout: float = 5.0) -> None:
        if type(index) is not int or index < 0:
            raise ValueError('Picamera2 camera index must be a nonnegative integer')
        if (width is None) != (height is None) or any(
                value is not None and (type(value) is not int or value <= 0)
                for value in (width, height)):
            raise ValueError('Supply both positive width and height, or neither')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Camera timeout must be finite and positive')
        self.index, self.size, self.timeout = index, (width or CAPTURE_SIZE[0], height or CAPTURE_SIZE[1]), timeout
        self.capture_settings = None
        self._condition = Condition()
        self._camera = self._pending = self._error = None
        self._closed = False
        self._entered = False
        self._captured = self._delivered = self._overwritten = 0

    def __enter__(self):
        if self._entered or self._closed:
            raise RuntimeError('Create a new camera source for each session')
        # Pi dependencies must not prevent imports/tests on the Windows/Linux PC.
        from picamera2 import Picamera2
        from libcamera import Transform, controls
        self._entered = True
        try:
            self._camera = Picamera2(camera_num=self.index)
            # Picamera2 RGB888 arrays are BGR, as required by OpenCV and the detector.
            # Match CameraTool2's request; libcamera selects the closest sensor
            # mode when 2304x1728/10-bit is not an exact native mode.
            config = self._camera.create_video_configuration(
                main={'size': self.size, 'format': 'RGB888'},
                sensor={'output_size': CAPTURE_SIZE, 'bit_depth': 10},
                transform=Transform(hflip=True, vflip=True),
                controls={'AfMode': controls.AfModeEnum.Continuous,
                          'ExposureValue': EXPOSURE_EV, 'FrameRate': CAPTURE_FPS},
                queue=False)
            self._camera.configure(config)
            actual = self._camera.camera_configuration()
            self.capture_settings = {
                'output': actual['main'], 'sensor': actual['sensor'],
                'exposure_ev': EXPOSURE_EV, 'capture_fps_requested': CAPTURE_FPS,
                'autofocus': 'continuous', 'rotation_clockwise': 180,
            }
            self._camera.post_callback = self._capture
            self._camera.start(show_preview=False)
        except BaseException:
            self.close()
            raise
        return self

    def _capture(self, request) -> None:
        received, utc = time.monotonic(), utc_at_receipt()
        try:
            image = request.make_array('main').copy()
            validate_frame(image)
            with self._condition:
                if self._closed or self._error is not None:
                    return
                packet = IntegrationFrame(image, self._captured, received, utc)
                self._captured += 1
                self._overwritten += int(self._pending is not None)
                self._pending = packet
                self._condition.notify_all()
        except Exception as exc:
            with self._condition:
                self._error = exc
                self._pending = None
                self._condition.notify_all()

    def read(self) -> IntegrationFrame:
        if not self._entered:
            raise RuntimeError('Open the camera source before reading')
        deadline = time.monotonic() + self.timeout
        with self._condition:
            while self._pending is None and not self._closed and self._error is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('Picamera2 timed out waiting for a frame')
                self._condition.wait(remaining)
            if self._closed:
                raise RuntimeError('Picamera2 source is closed')
            if self._error is not None:
                raise RuntimeError('Picamera2 frame capture failed') from self._error
            packet, self._pending = self._pending, None
            if time.monotonic() - packet.received_at > self.timeout:
                raise RuntimeError('Picamera2 frame is stale')
            self._delivered += 1
            return packet

    def stats(self) -> dict:
        with self._condition:
            return {'captured_frames': self._captured, 'dequeued_frames': self._delivered,
                    'overwritten_frames': self._overwritten,
                    'pending_frames': int(self._pending is not None)}

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending = None
            self._condition.notify_all()
        camera, self._camera = self._camera, None
        if camera is not None:
            try:
                camera.stop()
            finally:
                camera.close()

    def __exit__(self, *args):
        self.close()
