"""Keep UI callbacks on the calling thread while one detector worker runs."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import cv2
import numpy as np

from dmi_computer_vision.src.dmi.output.preview_state import PreviewState


class PreviewClosed(Exception):
    pass


class PreviewWorker:
    def __init__(self, processor, source, show, stop_event: Event | None, *, max_hold_seconds: float = 1.5):
        self.processor, self.source, self.show = processor, source, show
        self.stop_event = stop_event
        self.state = PreviewState(max_hold_seconds=max_hold_seconds)
        self.frames = 0
        self.render_seconds = 0.
        self._last_index = -1
        self._last_image = None
        self._last_show = 0.

    def __enter__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dmi-analysis")
        return self

    def _show_latest(self, *, force=False):
        try:
            packet = self.source.latest()
        except RuntimeError:
            self.state.clear()
            if self._last_image is not None:
                image = np.zeros_like(self._last_image)
                cv2.putText(image, "SOURCE LOST", (20, 60), 0, 1, (0, 190, 255), 2)
                self.show(image)
            raise
        if packet is None:
            return
        now = time.monotonic()
        if packet.capture_index != self._last_index or force or now - self._last_show >= .03:
            started = time.perf_counter()
            self._last_image = self.state.render(packet, now)
            self.render_seconds += time.perf_counter() - started
            self.frames += int(packet.capture_index != self._last_index)
            self._last_index = packet.capture_index
        if self._last_image is not None and (force or now - self._last_show >= .03):
            self._last_show = now
            if not self.show(self._last_image):
                raise PreviewClosed()

    def process(self, packet, timestamp):
        future = self.executor.submit(self.processor.process, packet.image, timestamp)
        while not future.done():
            if self.stop_event is not None and self.stop_event.is_set():
                raise PreviewClosed()
            self._show_latest()
            time.sleep(.01)
        result = future.result()
        self.state.update(result, packet)
        self._show_latest(force=True)
        return result

    def idle(self):
        if self.stop_event is not None and self.stop_event.is_set():
            raise PreviewClosed()
        self._show_latest()

    def __exit__(self, *args):
        self.state.clear()
        self.executor.shutdown(wait=True, cancel_futures=True)
