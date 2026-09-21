"""Frame-level orchestration for DMI screen understanding.

Detection stages are deliberately absent in Phase 2. The public frame contract
is established here so later stages can add evidence-backed detections without
changing video acquisition or output code.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]
FrameResult = dict[str, Any]


def process_frame(frame: Frame, frame_index: int, timestamp: float) -> FrameResult:
    """Process one source-independent BGR frame.

    Phase 2 returns explicit unknown values rather than fabricated detections.
    Geometry and recognition phases will populate the same result structure.
    """
    _validate_frame(frame)
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    if timestamp < 0:
        raise ValueError("timestamp must be non-negative")

    return {
        "frame_index": int(frame_index),
        "timestamp": round(float(timestamp), 6),
        "right_display": {
            "state": "unknown",
            "title": None,
            "buttons": {},
            "data_field": None,
        },
        "left_display": {
            "boxes": {},
            "speed_indicator": None,
        },
    }


def annotate_frame(frame: Frame, result: FrameResult) -> Frame:
    """Return a readable copy annotated with the matching structured result."""
    _validate_frame(frame)
    annotated = frame.copy()

    frame_index = result["frame_index"]
    timestamp = result["timestamp"]
    state = result["right_display"]["state"]
    lines = (
        f"frame {frame_index} | {timestamp:.3f}s",
        f"right state: {state}",
        "Phase 2: detections not implemented",
    )

    overlay = annotated.copy()
    cv2.rectangle(overlay, (12, 12), (510, 116), (0, 0, 0), thickness=-1)
    cv2.addWeighted(overlay, 0.65, annotated, 0.35, 0, annotated)
    for row, line in enumerate(lines):
        cv2.putText(
            annotated,
            line,
            (28, 43 + row * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return annotated


def _validate_frame(frame: Frame) -> None:
    if not isinstance(frame, np.ndarray):
        raise TypeError("frame must be a NumPy array")
    if frame.dtype != np.uint8:
        raise ValueError("frame must use uint8 pixels")
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame must be a three-channel BGR image")
    if frame.size == 0:
        raise ValueError("frame must not be empty")
