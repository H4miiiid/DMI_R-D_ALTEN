"""Frame-level orchestration for DMI screen understanding.

The public frame contract is established here so later stages can add
evidence-backed detections without changing video acquisition or output code.
"""

from __future__ import annotations

from typing import Any
import math

from dmi.utils.image_ops import validate_frame

from dmi.detection.display_geometry import Frame, detect_displays, rectify_display
from dmi.detection.right_display import analyze_right_display
from dmi.detection.left_display import (RECTIFIED_SIZE as LEFT_SIZE,
                                        analyze_left_display, analyze_train_left_display)
from dmi.temporal.left_tracking import LeftDisplayStabilizer
from dmi.temporal.smoothing import (
    GeometryStabilizer, LeftWorkflowStabilizer, RightDisplayStabilizer,
)

FrameResult = dict[str, Any]


class FrameProcessor:
    """One sequential source's temporal state, independent of frame acquisition.

    Video callers supply index/FPS timestamps. Live callers supply elapsed
    monotonic receipt times and may bound the gap across which history is used.
    """

    def __init__(self, *, max_gap_seconds: float | None = None) -> None:
        if max_gap_seconds is not None and (
            not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0
        ):
            raise ValueError("max_gap_seconds must be finite and positive")
        self.max_gap_seconds = max_gap_seconds
        self.reset()

    def reset(self) -> None:
        """Begin a new source/session with no previous detections."""
        self._index = 0
        self._timestamp: float | None = None
        self._shape: tuple[int, ...] | None = None
        self.last_reset_reason: str | None = None
        self._reset_history()

    def _reset_history(self) -> None:
        self._geometry = GeometryStabilizer()
        self._right = RightDisplayStabilizer()
        self._left = LeftDisplayStabilizer()
        self._left_workflow = LeftWorkflowStabilizer()

    def process(self, frame: Frame, timestamp: float) -> FrameResult:
        validate_frame(frame)
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("timestamp must be finite and non-negative")
        if self._timestamp is not None and timestamp <= self._timestamp:
            raise ValueError("timestamps must increase within a session")
        reason = None
        if self._shape is not None and frame.shape != self._shape:
            reason = "frame_size_changed"
        elif (self._timestamp is not None and self.max_gap_seconds is not None
              and timestamp - self._timestamp > self.max_gap_seconds):
            reason = "capture_gap"
        if reason:
            self._reset_history()
        self.last_reset_reason = reason
        try:
            result = process_frame(frame, self._index, timestamp,
                                   self._geometry, self._right, self._left, self._left_workflow)
        except Exception:
            self._reset_history()
            raise
        self._index += 1
        self._timestamp = timestamp
        self._shape = frame.shape
        return result


def process_frame(
    frame: Frame,
    frame_index: int,
    timestamp: float,
    geometry_stabilizer: GeometryStabilizer | None = None,
    right_display_stabilizer: RightDisplayStabilizer | None = None,
    left_display_stabilizer: LeftDisplayStabilizer | None = None,
    left_workflow_stabilizer: LeftWorkflowStabilizer | None = None,
) -> FrameResult:
    """Process one source-independent BGR frame.

    Unimplemented recognition stages return explicit unknown values rather
    than fabricated detections.
    """
    validate_frame(frame)
    if type(frame_index) is not int or frame_index < 0:
        raise ValueError("frame_index must be a non-negative integer")
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("timestamp must be finite and non-negative")

    displays = detect_displays(frame)
    if geometry_stabilizer is not None:
        displays = geometry_stabilizer.update(displays, frame.shape[:2])
    left_geometry = displays["left"]
    right_geometry = displays["right"]
    left_rectified = (rectify_display(frame, left_geometry, LEFT_SIZE)
                      if left_geometry is not None else None)
    train_left = (analyze_train_left_display(left_rectified, left_geometry)
                  if left_geometry is not None else None)
    train_state = train_left[0] if train_left is not None else None
    right_content = (
        analyze_right_display(frame, right_geometry, train_state)
        if right_geometry is not None
        else {
            "visibility": "unknown",
            "state": "unknown",
            "title": None,
            "buttons": {},
            "data_field": None,
        }
    )
    if right_display_stabilizer is not None:
        if right_geometry is None:
            right_display_stabilizer.reset()
        else:
            right_content = right_display_stabilizer.update(
                right_content, right_geometry
            )
    if train_left is not None:
        left_content = train_left[1]
        if left_workflow_stabilizer is not None:
            left_content = left_workflow_stabilizer.update(
                train_state, left_content, left_geometry
            )
    elif left_geometry is not None:
        left_content = analyze_left_display(
            frame, left_geometry, left_display_stabilizer, left_rectified
        )
    else:
        left_content = {"boxes": {}, "speed_indicator": None}
    if (train_left is not None or left_geometry is None) and left_display_stabilizer is not None:
        left_display_stabilizer.reset()
    if train_left is None and left_workflow_stabilizer is not None:
        left_workflow_stabilizer.reset()
    return {
        "frame_index": int(frame_index),
        "timestamp": round(float(timestamp), 6),
        "right_display": {
            "geometry": right_geometry.as_result() if right_geometry else None,
            **right_content,
        },
        "left_display": {
            "geometry": left_geometry.as_result() if left_geometry else None,
            **left_content,
        },
    }
