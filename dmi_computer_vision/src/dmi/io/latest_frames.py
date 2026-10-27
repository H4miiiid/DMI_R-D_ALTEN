"""One reader and one pending frame for independently refreshed previews."""
from __future__ import annotations

from threading import Condition, Event, Thread
import math
import time
from dmi_computer_vision.src.dmi.utils.image_ops import validate_frame


class LatestFrames:
    """Drain an already owned source, never open a second camera/HTTP client.

    ``last_packet`` identifies the frame delivered to analysis. ``latest()``
    peeks at acquisition without consuming or renewing detection evidence.
    """
    def __init__(self, source) -> None:
        self.source = source
        self.timeout = getattr(source, "timeout", 5.0)
        self._condition, self._stop = Condition(), Event()
        self._pending = self._latest = self.last_packet = None
        self._error = None
        self._ended = False
        self.captured = self.delivered = self.overwritten = 0
        self.discarded_on_stop = 0
        self._thread = None

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError("Create a new frame dispatcher for each session")
        self._thread = Thread(target=self._read_source, name="dmi-preview-source", daemon=True)
        self._thread.start()
        return self

    def _read_source(self):
        try:
            while not self._stop.is_set():
                try:
                    packet = self.source.read()
                except EOFError:
                    break
                validate_frame(packet.image)
                previous = self._latest
                if (type(packet.capture_index) is not int or packet.capture_index < 0
                        or not math.isfinite(packet.received_at) or packet.received_at > time.monotonic()
                        or (previous is not None and (packet.capture_index <= previous.capture_index
                                                      or packet.received_at <= previous.received_at))):
                    raise ValueError("Source capture indices and receipt times must increase")
                with self._condition:
                    if self._stop.is_set():
                        break
                    self.captured += 1
                    self.overwritten += int(self._pending is not None)
                    self._pending = self._latest = packet
                    self._condition.notify_all()
        except Exception as exc:
            with self._condition:
                self._error = exc
        finally:
            with self._condition:
                self._ended = True
                self._condition.notify_all()

    def latest(self):
        with self._condition:
            if self._error is not None:
                raise RuntimeError(str(self._error)) from self._error
            return self._latest

    def read(self, *, timeout: float | None = None):
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        with self._condition:
            while self._pending is None and not self._ended and not self._stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Frame dispatcher timed out")
                self._condition.wait(remaining)
            if self._error is not None:
                raise RuntimeError(str(self._error)) from self._error
            if self._pending is None:
                raise EOFError("Frame dispatcher ended")
            self.last_packet, self._pending = self._pending, None
            self.delivered += 1
            return self.last_packet

    def stats(self):
        with self._condition:
            return {"received_frames": self.captured, "dequeued_frames": self.delivered,
                    "overwritten_frames": self.overwritten, "pending_frames": int(self._pending is not None),
                    "discarded_on_stop": self.discarded_on_stop}

    def __exit__(self, *args):
        self._stop.set()
        with self._condition:
            self.discarded_on_stop += int(self._pending is not None)
            self._pending = self._latest = None
            self._condition.notify_all()
        self._thread.join(timeout=self.timeout + .5)
        if self._thread.is_alive():
            raise RuntimeError("Source reader failed to stop within its acquisition timeout")
