"""Temporal stabilization for sequential display geometry detections."""

from __future__ import annotations

import numpy as np

from dmi.geometry import DisplayGeometry, PointArray


class GeometryStabilizer:
    """Causally smooth display geometry while remaining responsive to jumps."""

    def __init__(self, smoothing: float = 0.2) -> None:
        if not 0 < smoothing <= 1:
            raise ValueError("smoothing must be in the interval (0, 1]")
        self._smoothing = smoothing
        self._previous: dict[str, DisplayGeometry] = {}

    def update(
        self,
        displays: dict[str, DisplayGeometry | None],
        frame_shape: tuple[int, int],
    ) -> dict[str, DisplayGeometry | None]:
        """Return stabilized geometry for one sequential video frame."""
        stabilized: dict[str, DisplayGeometry | None] = {}
        for name in ("left", "right"):
            current = displays[name]
            previous = self._previous.get(name)
            if current is None:
                self._previous.pop(name, None)
                stabilized[name] = None
                continue
            if previous is None or _is_geometry_jump(previous, current, frame_shape):
                result = current
            else:
                alpha = _adaptive_smoothing(
                    previous, current, frame_shape, self._smoothing
                )
                result = _blend_geometry(previous, current, alpha)
            self._previous[name] = result
            stabilized[name] = result
        return stabilized


def _blend_geometry(
    previous: DisplayGeometry,
    current: DisplayGeometry,
    alpha: float,
) -> DisplayGeometry:
    corners = previous.corners + alpha * (current.corners - previous.corners)
    previous_parameters = _oriented_box_parameters(previous.oriented_box)
    current_parameters = _oriented_box_parameters(current.oriented_box)
    previous_center, previous_width, previous_height, previous_angle = (
        previous_parameters
    )
    current_center, current_width, current_height, current_angle = (
        current_parameters
    )
    angle_delta = _wrapped_angle_delta(previous_angle, current_angle)
    center = previous_center + alpha * (current_center - previous_center)
    width = previous_width + alpha * (current_width - previous_width)
    height = previous_height + alpha * (current_height - previous_height)
    angle = previous_angle + alpha * angle_delta
    oriented_box = _oriented_box_from_parameters(center, width, height, angle)

    previous_bbox = np.asarray(previous.bbox, dtype=np.float32)
    current_bbox = np.asarray(current.bbox, dtype=np.float32)
    bbox = tuple(
        np.rint(previous_bbox + alpha * (current_bbox - previous_bbox))
        .astype(int)
        .tolist()
    )
    return DisplayGeometry(
        corners=corners.astype(np.float32),
        oriented_box=oriented_box,
        bounding_box=bbox,
    )


def _oriented_box_parameters(
    box: PointArray,
) -> tuple[PointArray, float, float, float]:
    top = box[1] - box[0]
    return (
        np.mean(box, axis=0),
        float(np.linalg.norm(top)),
        float(np.linalg.norm(box[2] - box[1])),
        float(np.arctan2(top[1], top[0])),
    )


def _oriented_box_from_parameters(
    center: PointArray,
    width: float,
    height: float,
    angle: float,
) -> PointArray:
    horizontal = np.array([np.cos(angle), np.sin(angle)], dtype=np.float32)
    vertical = np.array([-np.sin(angle), np.cos(angle)], dtype=np.float32)
    half_width = horizontal * (width / 2)
    half_height = vertical * (height / 2)
    return np.array(
        [
            center - half_width - half_height,
            center + half_width - half_height,
            center + half_width + half_height,
            center - half_width + half_height,
        ],
        dtype=np.float32,
    )


def _wrapped_angle_delta(previous: float, current: float) -> float:
    return float((current - previous + np.pi) % (2 * np.pi) - np.pi)


def _is_geometry_jump(
    previous: DisplayGeometry,
    current: DisplayGeometry,
    frame_shape: tuple[int, int],
) -> bool:
    frame_diagonal = float(np.hypot(*frame_shape))
    previous_center, previous_width, previous_height, previous_angle = (
        _oriented_box_parameters(previous.oriented_box)
    )
    current_center, current_width, current_height, current_angle = (
        _oriented_box_parameters(current.oriented_box)
    )
    center_change = float(np.linalg.norm(current_center - previous_center))
    width_change = abs(current_width / previous_width - 1)
    height_change = abs(current_height / previous_height - 1)
    angle_change = abs(_wrapped_angle_delta(previous_angle, current_angle))
    return bool(
        center_change > frame_diagonal * 0.06
        or width_change > 0.12
        or height_change > 0.12
        or angle_change > np.deg2rad(6)
    )


def _adaptive_smoothing(
    previous: DisplayGeometry,
    current: DisplayGeometry,
    frame_shape: tuple[int, int],
    base_alpha: float,
) -> float:
    """Increase responsiveness when motion exceeds ordinary detection jitter."""
    frame_diagonal = float(np.hypot(*frame_shape))
    center_change = float(
        np.linalg.norm(
            np.mean(current.oriented_box, axis=0)
            - np.mean(previous.oriented_box, axis=0)
        )
    )
    response = np.clip(
        (center_change / frame_diagonal - 0.012) / 0.025, 0.0, 1.0
    )
    return float(base_alpha + response * (0.65 - base_alpha))
