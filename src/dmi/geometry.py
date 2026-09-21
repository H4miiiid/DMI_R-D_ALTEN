"""Detection and rectification of the two physical DMI displays."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]
PointArray = NDArray[np.float32]


@dataclass(frozen=True)
class DisplayGeometry:
    """Detected display geometry in original-frame coordinates.

    Both corner arrays are ordered top-left, top-right, bottom-right,
    bottom-left. ``corners`` preserves the perspective quadrilateral used for
    rectification, while ``oriented_box`` is the detected rotated rectangle
    used for visualization.
    """

    corners: PointArray
    oriented_box: PointArray
    bounding_box: tuple[int, int, int, int]

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return self.bounding_box

    @property
    def center(self) -> tuple[int, int]:
        center = np.mean(self.oriented_box, axis=0)
        return round(float(center[0])), round(float(center[1]))

    def as_result(self) -> dict[str, list[int] | list[list[int]]]:
        corners = np.rint(self.corners).astype(int)
        return {
            "corners": corners.tolist(),
            "oriented_box": np.rint(self.oriented_box).astype(int).tolist(),
            "bbox": list(self.bbox),
            "center": list(self.center),
        }


def detect_displays(frame: Frame) -> dict[str, DisplayGeometry | None]:
    """Locate the left and right display surfaces in one BGR frame.

    The illuminated DMI surfaces have a consistent blue hue even as their
    brightness changes. Large blue components are grouped horizontally, then
    four boundary lines are fit to each group. No absolute screen coordinates
    are used.
    """
    height, width = frame.shape[:2]
    mask, strong_mask = _display_color_masks(frame)
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    component_area = height * width * 0.005
    components = [
        contour for contour in contours if cv2.contourArea(contour) >= component_area
    ]
    groups = _split_display_components(components, width)
    if groups is None:
        return {"left": None, "right": None}

    geometries: list[DisplayGeometry] = []
    for group in groups:
        geometry = _fit_display(group, strong_mask, (height, width))
        if geometry is None:
            return {"left": None, "right": None}
        geometries.append(geometry)

    if geometries[0].center[0] >= geometries[1].center[0]:
        return {"left": None, "right": None}
    geometries = _align_display_box_aspect(geometries, height)
    return {"left": geometries[0], "right": geometries[1]}


def _align_display_box_aspect(
    geometries: list[DisplayGeometry], frame_height: int
) -> list[DisplayGeometry]:
    """Use the shared physical-display aspect to resist partial occlusion."""
    ratios = []
    for geometry in geometries:
        x1, y1, x2, y2 = geometry.bbox
        ratios.append((y2 - y1) / (x2 - x1))
    common_ratio = max(ratios)

    aligned = []
    for geometry in geometries:
        x1, y1, x2, _ = geometry.bbox
        y2 = min(frame_height - 1, round(y1 + (x2 - x1) * common_ratio))
        aligned.append(
            DisplayGeometry(
                corners=geometry.corners,
                oriented_box=geometry.oriented_box,
                bounding_box=(x1, y1, x2, y2),
            )
        )
    return aligned


def rectify_display(
    frame: Frame,
    geometry: DisplayGeometry,
    output_size: tuple[int, int] = (800, 1280),
) -> Frame:
    """Perspective-rectify a detected display to ``(width, height)``."""
    width, height = output_size
    if width <= 0 or height <= 0:
        raise ValueError("output_size dimensions must be positive")
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(geometry.corners, destination)
    return cv2.warpPerspective(frame, transform, (width, height))


def _display_color_masks(
    frame: Frame,
) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (92, 80, 8), (118, 255, 255))
    strong_mask = cv2.inRange(hsv, (92, 80, 20), (118, 255, 255))

    close_width = _odd_kernel_size(width * 0.012, minimum=5)
    close_height = _odd_kernel_size(height * 0.012, minimum=5)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT, (close_width, close_height)
        ),
        iterations=2,
    )
    open_size = _odd_kernel_size(min(height, width) * 0.004, minimum=3)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (open_size, open_size)),
    )
    strong_mask = cv2.morphologyEx(
        strong_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT, (close_width, close_height)
        ),
        iterations=2,
    )
    strong_mask = cv2.morphologyEx(
        strong_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (open_size, open_size)),
    )
    return mask, strong_mask


def _split_display_components(
    contours: list[NDArray[np.int32]], frame_width: int
) -> tuple[list[NDArray[np.int32]], list[NDArray[np.int32]]] | None:
    if len(contours) < 2:
        return None

    centers = np.array(
        [
            x + width / 2
            for contour in contours
            for x, _, width, _ in [cv2.boundingRect(contour)]
        ]
    )
    order = np.argsort(centers)
    gaps = np.diff(centers[order])
    split = int(np.argmax(gaps)) + 1
    if gaps[split - 1] < frame_width * 0.05:
        return None

    left = [contours[index] for index in order[:split]]
    right = [contours[index] for index in order[split:]]
    if not left or not right:
        return None
    return left, right


def _fit_display(
    contours: list[NDArray[np.int32]],
    strong_mask: NDArray[np.uint8],
    frame_shape: tuple[int, int],
) -> DisplayGeometry | None:
    height, width = frame_shape
    points = np.concatenate(contours)
    hull = cv2.convexHull(points)
    if cv2.contourArea(hull) < height * width * 0.1:
        return None

    x, y, box_width, box_height = cv2.boundingRect(points)
    local = np.zeros((box_height, box_width), dtype=np.uint8)
    shifted_contours = []
    for contour in contours:
        shifted = contour.copy()
        shifted[:, :, 0] -= x
        shifted[:, :, 1] -= y
        shifted_contours.append(shifted)
    cv2.drawContours(local, shifted_contours, -1, 1, thickness=-1)
    hull_mask = np.zeros_like(local)
    shifted_hull = hull.copy()
    shifted_hull[:, :, 0] -= x
    shifted_hull[:, :, 1] -= y
    cv2.drawContours(hull_mask, [shifted_hull], -1, 1, thickness=-1)
    strong_local = (strong_mask[y : y + box_height, x : x + box_width] > 0) & (
        hull_mask > 0
    )

    row_start, row_end = round(box_height * 0.1), round(box_height * 0.9)
    rows = np.arange(row_start, row_end)
    row_pixels = local[rows] > 0
    valid_rows = row_pixels.any(axis=1)
    rows = rows[valid_rows]
    row_pixels = row_pixels[valid_rows]
    left_x = np.argmax(row_pixels, axis=1) + x
    right_x = box_width - 1 - np.argmax(row_pixels[:, ::-1], axis=1) + x
    rows = rows + y

    column_start, column_end = round(box_width * 0.1), round(box_width * 0.9)
    columns = np.arange(column_start, column_end)
    column_pixels = local[:, columns] > 0
    valid_columns = column_pixels.any(axis=0)
    columns = columns[valid_columns]
    column_pixels = column_pixels[:, valid_columns]
    top_y = np.argmax(column_pixels, axis=0) + y
    bottom_range = (columns >= box_width * 0.2) & (columns <= box_width * 0.8)
    columns_for_bottom = columns[bottom_range]
    bottom_pixels = strong_local[:, columns_for_bottom]
    strong_columns = bottom_pixels.any(axis=0)
    if np.count_nonzero(strong_columns) >= len(columns_for_bottom) * 0.5:
        columns_for_bottom = columns_for_bottom[strong_columns]
        bottom_pixels = bottom_pixels[:, strong_columns]
        bottom_y = (
            box_height - 1 - np.argmax(bottom_pixels[::-1], axis=0) + y
        )
    else:
        fallback_pixels = local[:, columns_for_bottom] > 0
        bottom_y = (
            box_height - 1 - np.argmax(fallback_pixels[::-1], axis=0) + y
        )
    columns = columns + x
    columns_for_bottom = columns_for_bottom + x

    left_line = _robust_linear_fit(rows, left_x)
    right_line = _robust_linear_fit(rows, right_x)
    top_line = _robust_linear_fit(columns, top_y)
    bottom_line = _robust_linear_fit(columns_for_bottom, bottom_y)
    corners = np.array(
        [
            _intersect_lines(left_line, top_line),
            _intersect_lines(right_line, top_line),
            _intersect_lines(right_line, bottom_line),
            _intersect_lines(left_line, bottom_line),
        ],
        dtype=np.float32,
    )
    if not _valid_geometry(corners, frame_shape):
        return None
    bounding_box = _fit_axis_aligned_box(
        left_x, right_x, top_y, bottom_y, frame_shape
    )
    if bounding_box is None:
        return None
    oriented_box = _fit_oriented_box(points)
    if not _valid_geometry(oriented_box, frame_shape):
        return None
    return DisplayGeometry(
        corners=corners,
        oriented_box=oriented_box,
        bounding_box=bounding_box,
    )


def _fit_oriented_box(points: NDArray[np.int32]) -> PointArray:
    """Return the minimum-area display rectangle in canonical corner order."""
    box = cv2.boxPoints(cv2.minAreaRect(points)).astype(np.float32)
    coordinate_sum = box.sum(axis=1)
    coordinate_difference = np.diff(box, axis=1).ravel()
    return np.array(
        [
            box[np.argmin(coordinate_sum)],
            box[np.argmin(coordinate_difference)],
            box[np.argmax(coordinate_sum)],
            box[np.argmax(coordinate_difference)],
        ],
        dtype=np.float32,
    )


def _fit_axis_aligned_box(
    left_x: NDArray,
    right_x: NDArray,
    top_y: NDArray,
    bottom_y: NDArray,
    frame_shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    height, width = frame_shape
    x1 = int(np.floor(np.percentile(left_x, 1)))
    x2 = int(np.ceil(np.percentile(right_x, 99)))
    y1 = int(np.floor(np.percentile(top_y, 1)))
    y2 = int(np.ceil(np.percentile(bottom_y, 5)))
    x1, x2 = max(0, x1), min(width - 1, x2)
    y1, y2 = max(0, y1), min(height - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    if (x2 - x1) * (y2 - y1) < height * width * 0.1:
        return None
    return x1, y1, x2, y2


def _robust_linear_fit(independent: NDArray, dependent: NDArray) -> NDArray:
    first_fit = np.polyfit(independent, dependent, 1)
    residual = np.abs(dependent - np.polyval(first_fit, independent))
    limit = max(3.0, float(np.percentile(residual, 80)))
    keep = residual <= limit
    return np.polyfit(independent[keep], dependent[keep], 1)


def _intersect_lines(
    x_from_y: NDArray, y_from_x: NDArray
) -> tuple[float, float]:
    x_slope, x_offset = x_from_y
    y_slope, y_offset = y_from_x
    denominator = 1 - y_slope * x_slope
    if abs(denominator) < 1e-6:
        return float("nan"), float("nan")
    y = (y_slope * x_offset + y_offset) / denominator
    return float(x_slope * y + x_offset), float(y)


def _valid_geometry(corners: PointArray, frame_shape: tuple[int, int]) -> bool:
    if not np.isfinite(corners).all():
        return False
    height, width = frame_shape
    margin = max(height, width) * 0.03
    if (
        (corners[:, 0] < -margin).any()
        or (corners[:, 0] > width + margin).any()
        or (corners[:, 1] < -margin).any()
        or (corners[:, 1] > height + margin).any()
    ):
        return False

    area = abs(cv2.contourArea(corners))
    top_width = np.linalg.norm(corners[1] - corners[0])
    bottom_width = np.linalg.norm(corners[2] - corners[3])
    left_height = np.linalg.norm(corners[3] - corners[0])
    right_height = np.linalg.norm(corners[2] - corners[1])
    mean_width = (top_width + bottom_width) / 2
    mean_height = (left_height + right_height) / 2
    return bool(area >= height * width * 0.1 and mean_height > mean_width * 1.2)


def _odd_kernel_size(value: float, minimum: int) -> int:
    size = max(minimum, int(round(value)))
    return size if size % 2 else size + 1
