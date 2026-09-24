"""Frame-level orchestration for DMI screen understanding.

The public frame contract is established here so later stages can add
evidence-backed detections without changing video acquisition or output code.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from dmi.geometry import Frame, detect_displays
from dmi.right_display import analyze_right_display
from dmi.left_display import analyze_left_display
from dmi.left_tracking import LeftDisplayStabilizer
from dmi.temporal import GeometryStabilizer, RightDisplayStabilizer

FrameResult = dict[str, Any]


def process_frame(
    frame: Frame,
    frame_index: int,
    timestamp: float,
    geometry_stabilizer: GeometryStabilizer | None = None,
    right_display_stabilizer: RightDisplayStabilizer | None = None,
    left_display_stabilizer: LeftDisplayStabilizer | None = None,
) -> FrameResult:
    """Process one source-independent BGR frame.

    Unimplemented recognition stages return explicit unknown values rather
    than fabricated detections.
    """
    _validate_frame(frame)
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    if timestamp < 0:
        raise ValueError("timestamp must be non-negative")

    displays = detect_displays(frame)
    if geometry_stabilizer is not None:
        displays = geometry_stabilizer.update(displays, frame.shape[:2])
    left_geometry = displays["left"]
    right_geometry = displays["right"]
    right_content = (
        analyze_right_display(frame, right_geometry)
        if right_geometry is not None
        else {
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
    left_content = (
        analyze_left_display(frame, left_geometry, left_display_stabilizer)
        if left_geometry is not None
        else {"boxes": {}, "speed_indicator": None}
    )
    if left_geometry is None and left_display_stabilizer is not None:
        left_display_stabilizer.reset()
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


def annotate_frame(frame: Frame, result: FrameResult) -> Frame:
    """Return a readable copy annotated with the matching structured result."""
    _validate_frame(frame)
    annotated = frame.copy()

    frame_index = result["frame_index"]
    timestamp = result["timestamp"]
    state = result["right_display"]["state"]
    left_geometry = result["left_display"]["geometry"]
    right_geometry = result["right_display"]["geometry"]
    lines = (
        f"frame {frame_index} | {timestamp:.3f}s",
        f"right state: {state}",
        "display geometry: "
        f"left={'found' if left_geometry else 'unknown'}, "
        f"right={'found' if right_geometry else 'unknown'}",
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
    _draw_geometry(
        annotated, left_geometry, "left display", (255, 255, 0), draw_center=False
    )
    _draw_geometry(
        annotated, right_geometry, "right display", (0, 255, 0), draw_center=False
    )
    _draw_right_content(annotated, result["right_display"])
    _draw_left_content(annotated, result["left_display"])
    return annotated


def _draw_geometry(
    frame: Frame,
    geometry: dict[str, Any] | None,
    label: str,
    color: tuple[int, int, int],
    *,
    draw_center: bool,
) -> None:
    if geometry is None:
        return
    oriented_box = np.asarray(geometry["oriented_box"], dtype=np.int32)
    cv2.polylines(
        frame, [oriented_box], isClosed=True, color=color, thickness=5,
        lineType=cv2.LINE_AA,
    )
    if draw_center:
        center = tuple(geometry["center"])
        cv2.circle(frame, center, 7, color, thickness=-1, lineType=cv2.LINE_AA)
    origin = tuple(oriented_box[0] + (12, 32))
    cv2.putText(
        frame,
        label,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        color,
        2,
        cv2.LINE_AA,
    )


def _draw_right_content(frame: Frame, display: dict[str, Any]) -> None:
    title = display["title"]
    if title is not None:
        title_text = title["text"] if title["text"] is not None else "title: unknown"
        _draw_region(frame, title, title_text, (255, 0, 255), draw_center=False)
    field = display["data_field"]
    if field is not None:
        value = field["value"] if field["value"] is not None else "unknown"
        _draw_region(
            frame, field, f"field: {value}", (0, 165, 255), draw_center=True
        )
    for name, button in display["buttons"].items():
        _draw_region(
            frame,
            button,
            name,
            (255, 128, 0),
            thickness=2,
            draw_center=True,
        )


def _draw_region(
    frame: Frame,
    region: dict[str, Any],
    label: str,
    color: tuple[int, int, int],
    *,
    thickness: int = 3,
    draw_center: bool,
) -> None:
    corners = np.asarray(region["corners"], dtype=np.int32)
    cv2.polylines(
        frame,
        [corners],
        isClosed=True,
        color=color,
        thickness=thickness,
        lineType=cv2.LINE_AA,
    )
    if draw_center:
        center = tuple(np.rint(corners.mean(axis=0)).astype(int))
        cv2.circle(frame, center, 5, color, thickness=-1, lineType=cv2.LINE_AA)
    x1, y1 = corners[0]
    cv2.putText(
        frame,
        label,
        (x1 + 4, max(18, y1 - 7)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
        cv2.LINE_AA,
    )


def _validate_frame(frame: Frame) -> None:
    if not isinstance(frame, np.ndarray):
        raise TypeError("frame must be a NumPy array")
    if frame.dtype != np.uint8:
        raise ValueError("frame must use uint8 pixels")
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame must be a three-channel BGR image")
    if frame.size == 0:
        raise ValueError("frame must not be empty")


def _draw_left_content(frame: Frame, display: dict[str, Any]) -> None:
    for name, region in display["boxes"].items():
        corners = np.rint(region["corners"]).astype(np.int32)
        cv2.polylines(frame, [corners], True, (80, 255, 80), 2, cv2.LINE_AA)
        center = tuple(np.rint(region["center"]).astype(int))
        cv2.circle(frame, center, 4, (0, 80, 255), -1, cv2.LINE_AA)
        label = name if region["icon"] is None else f'{name}: {region["icon"]}'
        origin = tuple(corners[0] + (5, 19))
        cv2.putText(
            frame, label, origin, cv2.FONT_HERSHEY_SIMPLEX,
            0.45, (0, 0, 0), 3, cv2.LINE_AA,
        )
        cv2.putText(
            frame, label, origin, cv2.FONT_HERSHEY_SIMPLEX,
            0.45, (80, 255, 80), 1, cv2.LINE_AA,
        )
    speed = display["speed_indicator"]
    if speed is not None:
        _draw_region(
            frame, speed, "speed indicator", (0, 220, 255),
            thickness=2, draw_center=False,
        )
        center = tuple(np.rint(speed["center"]).astype(int))
        cv2.circle(frame, center, 4, (0, 220, 255), -1, cv2.LINE_AA)
