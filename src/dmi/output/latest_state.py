"""One fresh, temporally processed observation for future live consumers."""
from copy import deepcopy
import math
from threading import Lock
import time

from dmi.output.json_writer import compact_state


class LatestState:
    """A bounded shared snapshot, active only while process_live is running.

    This exposes existing detector confirmations, not a guarantee of accuracy.
    Unknown/null observations replace old content. Freshness is measured from
    frame receipt, so a stalled camera or processor cannot keep data current.
    Consumers receive independent copies and no image buffers are retained.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._active = False
        self._snapshot = None

    def __enter__(self):
        with self._lock:
            if self._active:
                raise RuntimeError("LatestState already belongs to a live session")
            self._snapshot = None
            self._active = True
        return self

    def __exit__(self, *args):
        with self._lock:
            self._active = False
            self._snapshot = None

    def publish(self, result, *, capture_index, received_at, processed_at,
                frame_size, temporal_reset=None):
        snapshot = {"frame_index": result["frame_index"],
                    "timestamp": result["timestamp"],
                    "capture_index": capture_index, "received_at": received_at,
                    "processed_at": processed_at, "frame_size": list(frame_size),
                    "temporal_reset": temporal_reset, "state": compact_state(result)}
        with self._lock:
            if not self._active:
                raise RuntimeError("LatestState requires an active live session")
            self._snapshot = snapshot

    def get(self, *, max_age_seconds=1.0):
        """Return a fresh snapshot or None before first result/after stop/stall."""
        if (type(max_age_seconds) not in (int, float)
                or not math.isfinite(max_age_seconds) or max_age_seconds <= 0):
            raise ValueError("max_age_seconds must be finite and positive")
        with self._lock:
            if not self._active or self._snapshot is None:
                return None
            age = time.monotonic() - self._snapshot["received_at"]
            if age < 0 or age > max_age_seconds:
                return None
            return {**deepcopy(self._snapshot), "age_seconds": age}
