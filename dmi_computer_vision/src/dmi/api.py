"""Application-independent access to the existing detector and live runner."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import math
from threading import Lock
import time
from uuid import uuid4

from dmi_computer_vision.src.dmi.io.camera import CapturedFrame
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor, FrameResult
from dmi_computer_vision.src.dmi.pipeline.live import LiveRunSummary, process_live

__all__ = ["CapturedFrame", "LatestState", "LiveRunSummary", "Observation",
           "VisionSession", "process_live"]


def _source_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source_id must be a nonempty string")
    return value


def _nonnegative(value: float, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite nonnegative seconds")
    return float(value)


@dataclass(frozen=True)
class Observation:
    """One historical detection, never a calibration or action authorization.

    Coordinates in result/evidence use the original input image. These dictionaries
    belong to the caller; changing them cannot mutate the session's latest state.
    Retaining this object does not keep a session active or renew its evidence.
    """
    source_id: str
    session_id: str
    capture_index: int
    received_at: float
    processed_at: float
    upstream_age_seconds: float
    frame_size: tuple[int, int]
    result: FrameResult
    direct_evidence: dict
    temporal_reset: str | None

    def age_seconds(self) -> float:
        """Receipt-to-now plus supplied upstream age; not proof of current state."""
        return time.monotonic() - self.received_at + self.upstream_age_seconds


class VisionSession:
    """One explicit source/session, one serialized processing owner.

    This synchronous interface opens no camera, socket, file, UI or worker. A
    caller owns acquisition and feeds immutable BGR frames until process returns.
    latest() may be read from another thread while the owner analyzes a frame.
    Lifecycle/process calls must be serialized; concurrent calls raise immediately.
    """
    def __init__(self, source_id: str, *, max_gap_seconds: float = 1.0,
                 optimize: bool = True) -> None:
        self._source_id = _source_name(source_id)
        gap = _nonnegative(max_gap_seconds, "max_gap_seconds")
        if gap == 0:
            raise ValueError("max_gap_seconds must be positive")
        self._max_gap = gap
        self._optimize = optimize
        self._operation = Lock()
        self._snapshot = Lock()
        self._state = LatestState()
        self._processor: FrameProcessor | None = None
        self._first_received: float | None = None
        self._last_received: float | None = None
        self._last_capture = -1
        self._session_id: str | None = None
        self._upstream_age = 0.0

    @property
    def source_id(self) -> str:
        return self._source_id

    @contextmanager
    def _exclusive(self):
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("Serialize VisionSession processing and lifecycle calls")
        try:
            yield
        finally:
            self._operation.release()

    def _start(self) -> None:
        processor = FrameProcessor(max_gap_seconds=self._max_gap,
                                   collect_target_evidence=True, optimize=self._optimize)
        with self._snapshot:
            self._state.__enter__()
            self._processor = processor
            self._session_id = uuid4().hex
            self._first_received = self._last_received = None
            self._last_capture = -1
            self._upstream_age = 0.0

    def start(self) -> VisionSession:
        """Start a clean session; starting an already active session is an error."""
        with self._exclusive():
            if self._processor is not None:
                raise RuntimeError("VisionSession is already active")
            self._start()
        return self

    def __enter__(self) -> VisionSession:
        return self.start()

    def _close(self) -> None:
        with self._snapshot:
            processor, self._processor = self._processor, None
            self._state.__exit__(None, None, None)
            self._session_id = None
            self._first_received = self._last_received = None
            self._last_capture = -1
            self._upstream_age = 0.0
        if processor is not None:
            processor.close()

    def close(self) -> None:
        """Invalidate consumers and release native OCR resources; idempotent."""
        with self._exclusive():
            self._close()

    def __exit__(self, *args) -> None:
        self.close()

    def reset(self, *, source_id: str | None = None) -> None:
        """Clear all history/snapshots and change session identity before reuse."""
        with self._exclusive():
            if self._processor is None:
                raise RuntimeError("Start VisionSession before resetting it")
            try:
                name = self._source_id if source_id is None else _source_name(source_id)
            except Exception:
                self._close()
                raise
            self._close()
            self._source_id = name
            self._start()

    def process(self, packet: CapturedFrame) -> Observation:
        """Analyze current pixels using actual monotonic receipt metadata.

        Capture indices and receipt times must increase within the session.
        IntegrationFrame's optional upstream capture/transport ages are retained.
        Invalid input or analysis failure closes the session and clears latest;
        recovery requires an explicit start() or a new session, without retries.
        """
        with self._exclusive():
            processor = self._processor
            if processor is None:
                raise RuntimeError("Start VisionSession before processing frames")
            try:
                received = _nonnegative(packet.received_at, "received_at")
                if (type(packet.capture_index) is not int or packet.capture_index < 0
                        or packet.capture_index <= self._last_capture):
                    raise ValueError("capture_index must be a strictly increasing nonnegative integer")
                if received > time.monotonic():
                    raise ValueError("received_at must not be in the future")
                if self._last_received is not None and received <= self._last_received:
                    raise ValueError("receipt times must strictly increase")
                upstream = _nonnegative(sum(
                    _nonnegative(getattr(packet, name, 0.0), name) for name in
                    ("remote_capture_age_seconds", "transport_round_trip_seconds")),
                    "upstream_age_seconds")
                origin = received if self._first_received is None else self._first_received
                result = processor.process(packet.image, received-origin)
                finished = time.monotonic()
                size = (packet.image.shape[1], packet.image.shape[0])
                with self._snapshot:
                    assert self._session_id is not None
                    self._state.publish(result, capture_index=packet.capture_index,
                        received_at=received, processed_at=finished, frame_size=size,
                        temporal_reset=processor.last_reset_reason)
                    self._upstream_age = upstream
                    self._first_received = origin
                    self._last_received, self._last_capture = received, packet.capture_index
                    return Observation(self._source_id, self._session_id,
                        packet.capture_index, received, finished, upstream, size,
                        deepcopy(result), deepcopy(processor.target_evidence),
                        processor.last_reset_reason)
            except Exception:
                self._close()
                raise

    def latest(self, *, max_age_seconds: float = 1.0) -> dict | None:
        """Return one detached compact snapshot, or None after stop/loss/expiry.

        Age includes supplied upstream capture and transport age. The observation
        can be fresh yet contain unknown/omitted controls; freshness is not enabled
        state, calibration, or permission to move/press. The existing 1.5-s maximum
        evidence lifetime is never extended by this interface.
        """
        limit = _nonnegative(max_age_seconds, "max_age_seconds")
        if not 0 < limit <= 1.5:
            raise ValueError("max_age_seconds must be positive and at most 1.5")
        with self._snapshot:
            snapshot = self._state.get(max_age_seconds=limit)
            if snapshot is None:
                return None
            age = snapshot["age_seconds"] + self._upstream_age
            if age > limit:
                return None
            return {**snapshot, "source_id": self._source_id,
                    "session_id": self._session_id,
                    "upstream_age_seconds": self._upstream_age, "age_seconds": age}
