"""Temporal stabilization for sequential display geometry detections."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import cv2
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


class RightDisplayStabilizer:
    """Debounce recognized field values without freezing their geometry."""

    def __init__(
        self,
        confirmation_frames: int = 15,
        state_confirmation_frames: int = 5,
    ) -> None:
        if confirmation_frames <= 0:
            raise ValueError("confirmation_frames must be positive")
        if state_confirmation_frames <= 0:
            raise ValueError("state_confirmation_frames must be positive")
        self._confirmation_frames = confirmation_frames
        self._state_confirmation_frames = state_confirmation_frames
        self._value: str | None = None
        self._candidate: str | None = None
        self._candidate_count = 0
        self._state: str | None = None
        self._state_candidate: str | None = None
        self._state_candidate_count = 0
        self._last_content: dict[str, Any] | None = None
        self._regions: dict[str, np.ndarray] = {}
        self._relative_region_anchors: dict[str, np.ndarray] = {}
        self._layout_control = np.array(
            [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32
        )
        self._header_control = self._layout_control.copy()

    def update(
        self,
        content: dict[str, Any],
        geometry: DisplayGeometry | None = None,
    ) -> dict[str, Any]:
        current_state = content["state"]
        if self._state is None:
            self._state = current_state
        elif current_state == self._state:
            self._state_candidate = None
            self._state_candidate_count = 0
        else:
            if current_state == self._state_candidate:
                self._state_candidate_count += 1
            else:
                self._state_candidate = current_state
                self._state_candidate_count = 1
            if self._state_candidate_count < self._state_confirmation_frames:
                if self._last_content is not None:
                    return deepcopy(self._last_content)
            else:
                self._state = current_state
                self._state_candidate = None
                self._state_candidate_count = 0
                self._regions.clear()
                self._relative_region_anchors.clear()
                self._layout_control = np.array(
                    [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32
                )
                self._header_control = self._layout_control.copy()
                self._value = None
                self._candidate = None
                self._candidate_count = 0
        field = content["data_field"]
        if field is None:
            self._value = None
            self._candidate = None
            self._candidate_count = 0
            result = self._stabilize_regions(content, geometry)
            self._last_content = deepcopy(result)
            return result

        current = field["value"]
        if self._value is None and current is not None:
            self._value = current
        elif current == self._value:
            self._candidate = None
            self._candidate_count = 0
        elif current is not None:
            if current == self._candidate:
                self._candidate_count += 1
            else:
                self._candidate = current
                self._candidate_count = 1
            if self._candidate_count >= self._confirmation_frames:
                self._value = current
                self._candidate = None
                self._candidate_count = 0

        stabilized = dict(content)
        stabilized["data_field"] = {**field, "value": self._value}
        result = self._stabilize_regions(stabilized, geometry)
        self._last_content = deepcopy(result)
        return result

    def _stabilize_regions(
        self,
        content: dict[str, Any],
        geometry: DisplayGeometry | None,
    ) -> dict[str, Any]:
        layout_transform = None
        header_transform = None
        if geometry is not None and self._state in {"Driver ID", "Level"}:
            layout_transform = self._update_layout_transform(content, geometry)
            header_transform = self._update_header_transform(content, geometry)
        stabilized = dict(content)
        stabilized["title"] = self._stabilize_region(
            "title", content["title"], geometry, None
        )
        stabilized["data_field"] = self._stabilize_region(
            "data_field", content["data_field"], geometry, header_transform
        )
        stabilized["buttons"] = {
            name: self._stabilize_region(
                f"button:{name}", region, geometry, layout_transform
            )
            for name, region in content["buttons"].items()
        }
        active = {
            "title",
            "data_field",
            *(f"button:{name}" for name in content["buttons"]),
        }
        self._regions = {
            key: corners for key, corners in self._regions.items() if key in active
        }
        self._relative_region_anchors = {
            key: corners
            for key, corners in self._relative_region_anchors.items()
            if key in active
        }
        return stabilized

    def _update_layout_transform(
        self,
        content: dict[str, Any],
        geometry: DisplayGeometry,
    ) -> np.ndarray:
        """Track one robust screen-relative transform for the whole UI lattice.

        Driver ID and Level borders move together when the display grows in the
        rectified image.  Estimating that common motion from many button corners
        lets the layout re-lock to the visible borders without allowing one
        noisy line (or a hand edge) to make individual boxes jump.
        """
        source: list[np.ndarray] = []
        destination: list[np.ndarray] = []
        for name, region in content["buttons"].items():
            key = f"button:{name}"
            current = _map_corners_to_display(
                np.asarray(region["corners"], dtype=np.float32), geometry
            )
            anchor = self._relative_region_anchors.get(key)
            if anchor is None:
                self._relative_region_anchors[key] = current.copy()
                continue
            source.append(anchor)
            destination.append(current)

        if len(source) >= 3:
            source_points = np.concatenate(source)
            destination_points = np.concatenate(destination)
            transform, inliers = cv2.findHomography(
                source_points,
                destination_points,
                cv2.RANSAC,
                0.008,
            )
            if transform is not None and inliers is not None:
                inlier_ratio = float(np.mean(inliers))
                target_control = cv2.perspectiveTransform(
                    _UNIT_SQUARE.reshape(1, -1, 2), transform
                )[0]
                if inlier_ratio >= 0.65 and _reasonable_layout_control(
                    target_control
                ):
                    movement = float(
                        np.max(np.linalg.norm(target_control - self._layout_control, axis=1))
                    )
                    # Optical zoom in the recordings changes over consecutive
                    # frames.  A much larger one-frame change is instead the
                    # characteristic failure produced by a hand covering the
                    # grid and several false edges agreeing with each other.
                    if movement <= 0.045:
                        alpha = 0.38 if movement >= 0.008 else 0.12
                        self._layout_control += alpha * (
                            target_control - self._layout_control
                        )
        return cv2.getPerspectiveTransform(_UNIT_SQUARE, self._layout_control)

    def _update_header_transform(
        self,
        content: dict[str, Any],
        geometry: DisplayGeometry,
    ) -> np.ndarray:
        """Track title and field from their nearby field border, not the grid."""
        field = content.get("data_field")
        if field is None:
            return cv2.getPerspectiveTransform(_UNIT_SQUARE, self._header_control)
        current = _map_corners_to_display(
            np.asarray(field["corners"], dtype=np.float32), geometry
        )
        anchor = self._relative_region_anchors.get("data_field")
        if anchor is None:
            self._relative_region_anchors["data_field"] = current.copy()
            return cv2.getPerspectiveTransform(_UNIT_SQUARE, self._header_control)

        affine, _ = cv2.estimateAffine2D(anchor, current, method=cv2.LMEDS)
        if affine is None:
            return cv2.getPerspectiveTransform(_UNIT_SQUARE, self._header_control)
        target_control = cv2.transform(
            _UNIT_SQUARE.reshape(1, -1, 2), affine
        )[0]
        movement = float(
            np.max(np.linalg.norm(target_control - self._header_control, axis=1))
        )
        if _reasonable_layout_control(target_control) and movement <= 0.05:
            alpha = 0.32 if movement >= 0.008 else 0.10
            self._header_control += alpha * (
                target_control - self._header_control
            )
        return cv2.getPerspectiveTransform(_UNIT_SQUARE, self._header_control)

    def _stabilize_region(
        self,
        key: str,
        region: dict[str, Any] | None,
        geometry: DisplayGeometry | None,
        layout_transform: np.ndarray | None,
    ) -> dict[str, Any] | None:
        if region is None:
            self._regions.pop(key, None)
            self._relative_region_anchors.pop(key, None)
            return None
        current = np.asarray(region["corners"], dtype=np.float32)
        if geometry is not None and layout_transform is not None:
            anchor = self._relative_region_anchors.get(key)
            if anchor is None:
                current_relative = _map_corners_to_display(current, geometry)
                inverse = np.linalg.inv(layout_transform)
                anchor = cv2.perspectiveTransform(
                    current_relative.reshape(1, -1, 2), inverse
                )[0]
                self._relative_region_anchors[key] = anchor
            smoothed_relative = cv2.perspectiveTransform(
                anchor.reshape(1, -1, 2), layout_transform
            )[0]
            self._regions[key] = smoothed_relative
            smoothed = _map_corners_from_display(
                smoothed_relative, geometry
            )
            return _region_with_corners(region, smoothed)
        relative = (
            _map_corners_to_display(current, geometry)
            if geometry is not None
            else current
        )
        previous = self._regions.get(key)
        if previous is None:
            smoothed_relative = relative
        else:
            alpha = self._region_smoothing(key)
            displacement = float(
                np.max(np.linalg.norm(relative - previous, axis=1))
            )
            smoothed_relative = (
                previous
                if key == "title" and displacement > 0.045
                else previous + alpha * (relative - previous)
            )
        self._regions[key] = smoothed_relative
        smoothed = (
            _map_corners_from_display(smoothed_relative, geometry)
            if geometry is not None
            else smoothed_relative
        )
        return _region_with_corners(region, smoothed)

    def _region_smoothing(self, key: str) -> float:
        if self._state == "Main":
            return 0.42
        if self._state in {"Driver ID", "Level"}:
            if key == "title":
                return 0.18
            return 0.08
        return 0.18


def _region_with_corners(
    region: dict[str, Any], corners: np.ndarray
) -> dict[str, Any]:
    rounded = np.rint(corners).astype(int)
    result = dict(region)
    result["corners"] = rounded.tolist()
    result["bbox"] = [
        int(np.floor(corners[:, 0].min())),
        int(np.floor(corners[:, 1].min())),
        int(np.ceil(corners[:, 0].max())),
        int(np.ceil(corners[:, 1].max())),
    ]
    result["center"] = np.rint(corners.mean(axis=0)).astype(int).tolist()
    return result


_UNIT_SQUARE = np.array(
    [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32
)


def _reasonable_layout_control(control: np.ndarray) -> bool:
    """Reject implausible projective fits caused by occlusion or false lines."""
    if not np.isfinite(control).all():
        return False
    widths = (
        float(np.linalg.norm(control[1] - control[0])),
        float(np.linalg.norm(control[2] - control[3])),
    )
    heights = (
        float(np.linalg.norm(control[3] - control[0])),
        float(np.linalg.norm(control[2] - control[1])),
    )
    return bool(
        min(*widths, *heights) > 0.72
        and max(*widths, *heights) < 1.28
        and np.max(np.abs(control - _UNIT_SQUARE)) < 0.18
    )


def _display_mapping_corners(geometry: DisplayGeometry) -> np.ndarray:
    """Use the perspective quad only while its opposite edges remain credible."""
    corners = geometry.corners
    lengths = (
        float(np.linalg.norm(corners[1] - corners[0])),
        float(np.linalg.norm(corners[2] - corners[3])),
        float(np.linalg.norm(corners[3] - corners[0])),
        float(np.linalg.norm(corners[2] - corners[1])),
    )
    top, bottom, left, right = lengths
    reliable = bool(
        min(lengths) > 0
        and max(top, bottom) / min(top, bottom) <= 1.12
        and max(left, right) / min(left, right) <= 1.12
    )
    return corners if reliable else geometry.oriented_box


def _map_corners_to_display(
    corners: np.ndarray, geometry: DisplayGeometry
) -> np.ndarray:
    unit_square = np.array(
        [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(
        _display_mapping_corners(geometry).astype(np.float32), unit_square
    )
    return cv2.perspectiveTransform(corners.reshape(1, -1, 2), transform)[0]


def _map_corners_from_display(
    corners: np.ndarray, geometry: DisplayGeometry
) -> np.ndarray:
    unit_square = np.array(
        [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(
        unit_square, _display_mapping_corners(geometry).astype(np.float32)
    )
    return cv2.perspectiveTransform(corners.reshape(1, -1, 2), transform)[0]


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
