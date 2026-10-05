"""Render detections in original-frame coordinates."""

from typing import Any

import cv2
import numpy as np

from dmi.detection.display_geometry import Frame
from dmi.pipeline.frame_processor import FrameResult
from dmi.utils.image_ops import validate_frame


def annotate_frame(frame: Frame, result: FrameResult) -> Frame:
    """Return a readable copy annotated with the matching structured result."""
    validate_frame(frame)
    annotated = frame.copy()

    frame_index = result["frame_index"]
    timestamp = result["timestamp"]
    state = result["right_display"]["state"]
    left_geometry = result["left_display"]["geometry"]
    right_geometry = result["right_display"]["geometry"]
    lines = (
        f"frame {frame_index} | {timestamp:.3f}s",
        f"right state: {state}" + (" | paused: obstruction"
            if result["right_display"].get("visibility") == "occluded" else ""),
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


def _draw_left_content(frame: Frame, display: dict[str, Any]) -> None:
    title = display.get("title")
    if title is not None:
        _draw_region(frame, title, title["text"], (255, 0, 255), draw_center=False)
    for name, button in display.get("buttons", {}).items():
        _draw_region(frame, button, name, (255, 128, 0), draw_center=True)
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
