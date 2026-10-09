"""Cheap acquisition-time scheduling; skips never become detector evidence."""
from __future__ import annotations

from threading import Event
import math

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.io.camera import CapturedFrame
from dmi_computer_vision.src.dmi.utils.image_ops import validate_frame


class DetectionPolicy:
    def __init__(self, *, max_detection_fps: float = 5.0, refresh_seconds: float = 0.4,
                 pixel_delta: float = 12.0, changed_fraction: float = 0.002,
                 burst_seconds: float = 3.0) -> None:
        for name, value in [('rate', max_detection_fps), ('refresh', refresh_seconds),
                            ('pixel delta', pixel_delta), ('change fraction', changed_fraction)]:
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if changed_fraction > 1 or not math.isfinite(burst_seconds) or burst_seconds < 0:
            raise ValueError('Invalid change fraction/burst duration')
        if refresh_seconds < 1 / max_detection_fps:
            raise ValueError('Refresh interval must respect detection rate cap')
        self.interval = 1 / max_detection_fps
        self.refresh_seconds = refresh_seconds
        self.pixel_delta, self.changed_fraction = pixel_delta, changed_fraction
        self.burst_seconds = burst_seconds
        self._force = Event()
        self._refresh_after = None
        self._baseline = None
        self._shape = None
        self._last_started = None
        self._last_receipt = None
        self._burst_until = 0.0
        self.checked_frames = self.skipped_frames = self.detection_calls = 0
        self.check_seconds = 0.0
        self.last_reason = None

    def start_session(self) -> None:
        """Begin with no retained image/evidence or prior session counters."""
        self._baseline = self._shape = self._last_started = self._last_receipt = None
        self._burst_until = 0.0
        self._refresh_after = None
        self._force.clear()
        self.checked_frames = self.skipped_frames = self.detection_calls = 0
        self.check_seconds = 0.0
        self.last_reason = None

    def request_refresh(self, *, after_received_at: float | None = None) -> None:
        """Call after an action completes; next received frame is forced once."""
        import time
        self._refresh_after = time.monotonic() if after_received_at is None else after_received_at
        self._force.set()

    def should_process(self, packet: CapturedFrame, now: float) -> bool:
        import time
        started = time.perf_counter()
        validate_frame(packet.image)
        thumbnail = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(packet.image, (160, 120)), cv2.COLOR_BGR2GRAY), (3, 3), 0)
        self.checked_frames += 1
        changed = (self._baseline is None or
                   float(np.mean(cv2.absdiff(thumbnail, self._baseline) > self.pixel_delta)) >= self.changed_fraction)
        reset = self._shape != packet.image.shape
        gap = self._last_receipt is not None and packet.received_at - self._last_receipt > self.refresh_seconds * 2
        self._last_receipt = packet.received_at
        forced = self._force.is_set()
        if forced and packet.received_at <= self._refresh_after:
            self.check_seconds += time.perf_counter() - started
            self.skipped_frames += 1
            return False
        if forced:
            self._force.clear()
        if changed or reset or gap or forced:
            self._burst_until = now + self.burst_seconds
        elapsed = float('inf') if self._last_started is None else now - self._last_started
        mandatory = self._baseline is None or reset or gap or forced
        due = elapsed >= self.interval and (changed or now < self._burst_until or elapsed >= self.refresh_seconds)
        self.check_seconds += time.perf_counter() - started
        if not mandatory and not due:
            self.skipped_frames += 1
            return False
        self._baseline, self._shape, self._last_started = thumbnail, packet.image.shape, now
        self.detection_calls += 1
        self.last_reason = ('forced' if forced else 'reset' if reset or gap else
                            'change' if changed else 'confirmation_burst' if now < self._burst_until else 'refresh')
        return True

    def stats(self) -> dict:
        return {'settings': {'max_detection_fps': 1/self.interval, 'refresh_seconds': self.refresh_seconds,
                             'burst_seconds': self.burst_seconds, 'pixel_delta': self.pixel_delta,
                             'changed_fraction': self.changed_fraction},
                'checked_frames': self.checked_frames, 'policy_skipped_frames': self.skipped_frames,
                'detection_calls': self.detection_calls, 'cheap_check_seconds': self.check_seconds}
