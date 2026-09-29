"""Border-line fitting for right-display UI regions in rectified frames."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]
Quad = NDArray[np.float32]
Line = tuple[float, float]
LineCandidate = tuple[float, float, float]
BorderLines = tuple[list[LineCandidate], list[LineCandidate]]


def detect_border_lines(frame: Frame) -> BorderLines:
    """Extract reusable horizontal and vertical UI-border evidence."""
    return _line_candidates(frame)


def detect_button_quads(
    frame: Frame,
    state: str,
    border_lines: BorderLines | None = None,
) -> dict[str, Quad]:
    """Fit visible grid borders and return named rectified-space cells."""
    height, width = frame.shape[:2]
    horizontal, vertical = border_lines or _line_candidates(frame)
    if state == "Main":
        names = (
            ("start", "driver_id"),
            ("train_data", "empty_driver_id"),
            ("level", "train_running_number"),
            ("shunting", "non_leading"),
            ("maintain_shunting", "radio_data"),
        )
        grid = _fit_grid(
            horizontal,
            vertical,
            width,
            height,
            x_fractions=(0.0, 0.4525, 0.915),
            y_fractions=(0.189, 0.274, 0.369, 0.454, 0.544, 0.634),
            names=names,
            horizontal_min_length=width * 0.65,
        )
        grid["close"] = _fit_main_close(horizontal, vertical, width, height)
        return grid
    if state == "Driver ID":
        keypad_names = (
            ("digit_1", "digit_2", "digit_3"),
            ("digit_4", "digit_5", "digit_6"),
            ("digit_7", "digit_8", "digit_9"),
            ("delete", "digit_0", "decimal"),
        )
        keypad_x_lines = _fit_axis_topology(
            vertical,
            tuple(value * width for value in (0.001, 0.304, 0.609, 0.905)),
            extent=width,
            cross_center=height / 2,
        )
        keypad_x_expected = tuple(
            value * width for value in (0.001, 0.304, 0.609, 0.905)
        )
        keypad_x_transform = _transform_from_fitted_lines(
            keypad_x_lines, keypad_x_expected, height / 2, width
        )
        action_x_lines = _fit_axis_topology(
            vertical,
            tuple(value * width for value in (0.001, 0.242, 0.423, 0.665, 0.906)),
            extent=width,
            cross_center=height * 0.86,
            fixed_transform=keypad_x_transform,
        )
        y_lines = _fit_axis_topology(
            horizontal,
            tuple(
                value * height
                for value in (0.459, 0.545, 0.634, 0.727, 0.813)
            ),
            extent=height,
            cross_center=width / 2,
            min_length=width * 0.25,
        )
        row_heights = [
            _line_position(y_lines[index + 1], width / 2)
            - _line_position(y_lines[index], width / 2)
            for index in range(4)
        ]
        action_top = _line_position(y_lines[-1], width / 2)
        action_bottom = action_top + float(np.median(row_heights))
        y_lines.append(
            _select_horizontal(
                horizontal,
                action_bottom,
                width,
                height,
                min_length=width * 0.18,
                tolerance_fraction=0.018,
            )
        )
        grid = _cells_from_lines(
            keypad_x_lines,
            y_lines,
            keypad_names,
            x_indices=(0, 1, 2, 3),
            y_indices=(0, 1, 2, 3, 4),
        )
        grid.update(
            _cells_from_lines(
                action_x_lines,
                y_lines,
                (("cancel", "empty_action", "trn", "settings"),),
                x_indices=(0, 1, 2, 3, 4),
                y_indices=(4, 5),
            )
        )
        return grid
    if state == "Level":
        names = (
            ("level_1", "level_2", "level_3"),
            ("level_0", "pzb", "kvb"),
            ("scmt", "lzb", "memor"),
        )
        x_lines = _fit_axis_topology(
            vertical,
            tuple(value * width for value in (0.001, 0.303, 0.613, 0.91)),
            extent=width,
            cross_center=height / 2,
        )
        x_expected = tuple(
            value * width for value in (0.001, 0.303, 0.613, 0.91)
        )
        x_transform = _transform_from_fitted_lines(
            x_lines, x_expected, height / 2, width
        )
        close_x_lines = _fit_axis_topology(
            vertical,
            tuple(value * width for value in (0.001, 0.241)),
            extent=width,
            cross_center=height * 0.86,
            fixed_transform=x_transform,
        )
        y_lines = _fit_axis_topology(
            horizontal,
            tuple(
                value * height
                for value in (0.459, 0.546, 0.634, 0.723, 0.814)
            ),
            extent=height,
            cross_center=width / 2,
            min_length=width * 0.25,
        )
        row_heights = [
            _line_position(y_lines[index + 1], width / 2)
            - _line_position(y_lines[index], width / 2)
            for index in range(3)
        ]
        close_top = _line_position(y_lines[-1], width / 2)
        close_bottom = close_top + float(np.median(row_heights))
        y_lines.append(
            _select_horizontal(
                horizontal,
                close_bottom,
                width,
                height,
                min_length=width * 0.18,
                tolerance_fraction=0.018,
            )
        )
        grid = _cells_from_lines(
            x_lines,
            y_lines,
            names,
            x_indices=(0, 1, 2, 3),
            y_indices=(0, 1, 2, 3),
        )
        grid["more"] = _quad(x_lines[2], x_lines[3], y_lines[3], y_lines[4])
        grid["close"] = _quad(
            close_x_lines[0], close_x_lines[1], y_lines[4], y_lines[5]
        )
        return grid
    return _detect_unknown_buttons(frame, horizontal, vertical)


def detect_title_quad(frame: Frame, text_box: tuple[int, int, int, int]) -> Quad:
    band_quad = _detect_title_band_quad(frame)
    if band_quad is not None:
        return band_quad
    height, width = frame.shape[:2]
    horizontal, vertical = _line_candidates(frame)
    center_y = (text_box[1] + text_box[3]) / 2
    top = _select_horizontal(horizontal, center_y - height * 0.03, width, height)
    bottom = _select_horizontal(horizontal, center_y + height * 0.03, width, height)
    left = (0.0, 0.0)
    right = _select_vertical(vertical, width * 0.93, width, height)
    return _quad(left, right, top, bottom)


def _detect_title_band_quad(frame: Frame) -> Quad | None:
    """Fit the title's own blue/black transitions and visible right endpoint."""
    height, width = frame.shape[:2]
    pixels = frame.astype(np.int16)
    blue, green, red = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    mask = (
        (blue >= 20) & (blue - green >= 9) & (blue - red >= 16)
    ).astype(np.uint8)
    search_top = round(height * 0.025)
    search_bottom = round(height * 0.23)
    title_mask = cv2.morphologyEx(
        mask[search_top:search_bottom],
        cv2.MORPH_CLOSE,
        np.ones((5, 1), dtype=np.uint8),
    )

    column_support = title_mask.sum(axis=0).astype(np.float32)
    column_support = np.convolve(column_support, np.ones(9) / 9, mode="same")
    supported = column_support >= height * 0.04
    right = None
    for x in range(round(width * 0.70), width - 8):
        if not np.any(supported[x : x + 8]):
            right = float(x - 1)
            break
    if right is None or right < width * 0.75:
        return None

    samples: list[tuple[float, float, float]] = []
    minimum_run = max(7, round(height * 0.009))
    for x in range(0, max(1, int(right) - 2), 3):
        indices = np.flatnonzero(title_mask[:, x])
        if indices.size == 0:
            continue
        starts = np.r_[0, np.flatnonzero(np.diff(indices) > 1) + 1]
        ends = np.r_[starts[1:], len(indices)]
        runs = [
            (int(indices[start]) + search_top, int(indices[end - 1]) + search_top)
            for start, end in zip(starts, ends)
            if indices[end - 1] - indices[start] + 1 >= minimum_run
        ]
        if len(runs) >= 2:
            samples.append((float(x), float(runs[0][1]), float(runs[1][0])))
    if len(samples) < width // 15:
        return None
    values = np.asarray(samples, dtype=np.float64)
    if float(np.ptp(values[:, 0])) < width * 0.60:
        return None
    top = _robust_boundary_line(values[:, 0], values[:, 1])
    bottom = _robust_boundary_line(values[:, 0], values[:, 2])
    if not height * 0.025 <= _line_position(top, width / 2) < _line_position(
        bottom, width / 2
    ) <= height * 0.20:
        return None
    return _quad((0.0, 0.0), (0.0, right), top, bottom)


def _robust_boundary_line(x_values: np.ndarray, y_values: np.ndarray) -> Line:
    keep = np.ones(len(x_values), dtype=bool)
    coefficients = np.polyfit(x_values, y_values, 1)
    for _ in range(3):
        residuals = np.abs(y_values - np.polyval(coefficients, x_values))
        threshold = max(2.0, float(np.median(residuals[keep])) * 3.0)
        keep = residuals <= threshold
        if np.count_nonzero(keep) < 3:
            break
        coefficients = np.polyfit(x_values[keep], y_values[keep], 1)
    return float(coefficients[0]), float(coefficients[1])


def field_quad_from_contour(contour: NDArray[np.int32]) -> Quad:
    box = cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.float32)
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


def _fit_grid(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    width: int,
    height: int,
    *,
    x_fractions: tuple[float, ...],
    y_fractions: tuple[float, ...],
    names: tuple[tuple[str, ...], ...],
    horizontal_min_length: float = 0.0,
) -> dict[str, Quad]:
    x_lines = [
        _select_vertical(vertical, fraction * width, width, height)
        for fraction in x_fractions
    ]
    y_lines = [
        _select_horizontal(
            horizontal,
            fraction * height,
            width,
            height,
            min_length=horizontal_min_length,
        )
        for fraction in y_fractions
    ]
    return {
        name: _quad(x_lines[column], x_lines[column + 1], y_lines[row], y_lines[row + 1])
        for row, row_names in enumerate(names)
        for column, name in enumerate(row_names)
    }


def _cells_from_lines(
    x_lines: list[Line],
    y_lines: list[Line],
    names: tuple[tuple[str, ...], ...],
    *,
    x_indices: tuple[int, ...],
    y_indices: tuple[int, ...],
) -> dict[str, Quad]:
    return {
        name: _quad(
            x_lines[x_indices[column]],
            x_lines[x_indices[column + 1]],
            y_lines[y_indices[row]],
            y_lines[y_indices[row + 1]],
        )
        for row, row_names in enumerate(names)
        for column, name in enumerate(row_names)
    }


def _fit_axis_topology(
    candidates: list[tuple[float, float, float]],
    expected_positions: tuple[float, ...],
    *,
    extent: int,
    cross_center: float,
    min_length: float = 0.0,
    fixed_transform: tuple[float, float] | None = None,
) -> list[Line]:
    """Fit a coherent line lattice and infer borders hidden by occlusion.

    Individual nearest-line searches leave undetected borders at stale nominal
    coordinates and can pull other borders toward unrelated short edges.  The
    visible borders instead establish one affine layout for the whole grid;
    missing members inherit that detected translation, scale, and orientation.
    """
    scale, offset = fixed_transform or _fit_topology_transform(
        candidates, expected_positions, cross_center, extent, min_length
    )
    transformed = [scale * expected + offset for expected in expected_positions]
    anchor_tolerance = extent * 0.035
    anchors: list[tuple[float, tuple[float, float, float]]] = []
    for expected, target in zip(expected_positions, transformed):
        nearby = [
            candidate
            for candidate in candidates
            if abs(_line_position(candidate, cross_center) - target)
            <= anchor_tolerance
        ]
        if not nearby:
            continue
        sufficiently_long = [item for item in nearby if item[2] >= min_length]
        if sufficiently_long:
            nearby = sufficiently_long
        selected = min(
            nearby,
            key=lambda item: abs(_line_position(item, cross_center) - target)
            - min(item[2], extent) * 0.015,
        )
        anchors.append((expected, selected))

    if fixed_transform is None:
        refined_scale, refined_offset = _fit_axis_transform(
            anchors, cross_center, extent
        )
        if len(anchors) >= 2:
            scale, offset = refined_scale, refined_offset
    transformed = [scale * expected + offset for expected in expected_positions]
    shared_slope = _shared_slope([line for _, line in anchors])
    fitted: list[Line] = []
    for target in transformed:
        nearby = [
            candidate
            for candidate in candidates
            if abs(_line_position(candidate, cross_center) - target)
            <= extent * 0.035
        ]
        sufficiently_long = [item for item in nearby if item[2] >= min_length]
        if sufficiently_long:
            nearby = sufficiently_long
        if nearby:
            selected = min(
                nearby,
                key=lambda item: abs(_line_position(item, cross_center) - target)
                - min(item[2], extent) * 0.015,
            )
            position = _line_position(selected, cross_center)
            fitted.append(
                (shared_slope, position - shared_slope * cross_center)
            )
        else:
            fitted.append((shared_slope, target - shared_slope * cross_center))
    return fitted


def _transform_from_fitted_lines(
    lines: list[Line],
    expected_positions: tuple[float, ...],
    cross_center: float,
    extent: int,
) -> tuple[float, float]:
    anchors = [
        (expected, (line[0], line[1], float(extent)))
        for expected, line in zip(expected_positions, lines)
    ]
    return _fit_axis_transform(anchors, cross_center, extent)


def _fit_topology_transform(
    candidates: list[LineCandidate],
    expected_positions: tuple[float, ...],
    cross_center: float,
    extent: int,
    min_length: float,
) -> tuple[float, float]:
    """Find the affine placement whose complete line pattern has most support."""
    usable = [item for item in candidates if item[2] >= min_length]
    if len(usable) < 2:
        usable = candidates
    detected = sorted(
        {
            round(_line_position(item, cross_center), 1)
            for item in usable
        }
    )
    if not detected:
        return 1.0, 0.0

    hypotheses: list[tuple[float, float]] = [(1.0, 0.0)]
    for expected in expected_positions:
        hypotheses.extend((1.0, value - expected) for value in detected)
    for first_index, first_expected in enumerate(expected_positions[:-1]):
        for second_expected in expected_positions[first_index + 1 :]:
            expected_distance = second_expected - first_expected
            if expected_distance < extent * 0.07:
                continue
            for detected_index, first_detected in enumerate(detected[:-1]):
                for second_detected in detected[detected_index + 1 :]:
                    scale = (second_detected - first_detected) / expected_distance
                    if 0.78 <= scale <= 1.24:
                        hypotheses.append(
                            (scale, first_detected - scale * first_expected)
                        )

    tolerance = extent * 0.022
    best = (1.0, 0.0)
    best_score = (-1, float("-inf"))
    for scale, offset in hypotheses:
        residuals = [
            min(abs(value - (scale * expected + offset)) for value in detected)
            for expected in expected_positions
        ]
        matched = [value for value in residuals if value <= tolerance]
        score = (
            len(matched),
            -sum(matched)
            - abs(scale - 1.0) * extent * 0.01
            - abs(offset) * 0.05,
        )
        if score > best_score:
            best_score = score
            best = (scale, offset)
    return float(best[0]), float(best[1])


def _fit_axis_transform(
    anchors: list[tuple[float, tuple[float, float, float]]],
    cross_center: float,
    extent: int,
) -> tuple[float, float]:
    if not anchors:
        return 1.0, 0.0
    expected = np.asarray([item[0] for item in anchors], dtype=np.float64)
    detected = np.asarray(
        [_line_position(item[1], cross_center) for item in anchors],
        dtype=np.float64,
    )
    if len(anchors) == 1 or float(np.ptp(expected)) < extent * 0.08:
        return 1.0, float(np.median(detected - expected))
    scale, offset = np.polyfit(expected, detected, 1)
    residuals = np.abs(detected - (scale * expected + offset))
    reliable = residuals <= extent * 0.025
    if np.count_nonzero(reliable) >= 2 and not np.all(reliable):
        scale, offset = np.polyfit(expected[reliable], detected[reliable], 1)
    if not 0.82 <= scale <= 1.18:
        return 1.0, float(np.median(detected - expected))
    return float(scale), float(offset)


def _line_position(line: tuple[float, float, float], cross: float) -> float:
    return line[0] * cross + line[1]


def _shared_slope(candidates: list[tuple[float, float, float]]) -> float:
    if not candidates:
        return 0.0
    total = sum(item[2] for item in candidates)
    return float(sum(item[0] * item[2] for item in candidates) / total)


def _detect_unknown_buttons(
    frame: Frame,
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
) -> dict[str, Quad]:
    """Return conservatively verified bordered cells on an unknown screen."""
    height, width = frame.shape[:2]
    h_lines = _cluster_lines(
        [line for line in horizontal if line[2] >= width * 0.12], width / 2
    )
    v_lines = _cluster_lines(
        [line for line in vertical if line[2] >= height * 0.06], height / 2
    )
    # Blue background alone is not a border. Require local image edges too,
    # otherwise extrapolated glyph/grid lines create large unsupported cells.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 8, 30)
    # Antialiased white glyph edges can also touch blue pixels. Exclude their
    # immediate neighborhoods so text strokes cannot become cell boundaries.
    glyphs = cv2.dilate((gray >= 90).astype(np.uint8), np.ones((7, 7), np.uint8))
    mask = _border_color_mask(frame) & (edges > 0).astype(np.uint8) & (glyphs == 0)
    cells: list[Quad] = []
    for top, bottom in zip(h_lines, h_lines[1:]):
        center_y = (_line_position((*top, 0.0), width / 2) + _line_position((*bottom, 0.0), width / 2)) / 2
        if center_y < height * 0.30:
            continue
        for left, right in zip(v_lines, v_lines[1:]):
            quad = _quad(left, right, top, bottom)
            cell_width = float(np.linalg.norm(quad[1] - quad[0]))
            cell_height = float(np.linalg.norm(quad[3] - quad[0]))
            if not (
                width * 0.08 <= cell_width <= width * 0.70
                and height * 0.04 <= cell_height <= height * 0.22
            ):
                continue
            supports = [
                _edge_support(mask, quad[index], quad[(index + 1) % 4])
                for index in range(4)
            ]
            if min(supports) >= 0.42:
                cells.append(quad)
    cells.sort(key=lambda quad: (float(quad[:, 1].mean()), float(quad[:, 0].mean())))
    return {f"button_{index}": quad for index, quad in enumerate(cells, start=1)}


def _cluster_lines(
    candidates: list[tuple[float, float, float]], cross_center: float
) -> list[Line]:
    ordered = sorted(candidates, key=lambda line: _line_position(line, cross_center))
    clusters: list[list[tuple[float, float, float]]] = []
    for candidate in ordered:
        if not clusters or abs(
            _line_position(candidate, cross_center)
            - np.mean([_line_position(item, cross_center) for item in clusters[-1]])
        ) > 8:
            clusters.append([candidate])
        else:
            clusters[-1].append(candidate)
    result = []
    for cluster in clusters:
        total = sum(item[2] for item in cluster)
        result.append(
            (
                sum(item[0] * item[2] for item in cluster) / total,
                sum(item[1] * item[2] for item in cluster) / total,
            )
        )
    return result


def _border_color_mask(frame: Frame) -> NDArray[np.uint8]:
    pixels = frame.astype(np.int16)
    blue, green, red = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    return (
        (blue >= 28) & (blue - green >= 12) & (blue - red >= 24)
    ).astype(np.uint8)


def _edge_support(mask: NDArray[np.uint8], start: NDArray, end: NDArray) -> float:
    positions = np.linspace(0.04, 0.96, 40)
    xs = np.rint(start[0] + (end[0] - start[0]) * positions).astype(int)
    ys = np.rint(start[1] + (end[1] - start[1]) * positions).astype(int)
    supported = []
    for x, y in zip(xs, ys):
        x1, x2 = max(0, x - 2), min(mask.shape[1], x + 3)
        y1, y2 = max(0, y - 2), min(mask.shape[0], y + 3)
        supported.append(bool(mask[y1:y2, x1:x2].any()))
    return float(np.mean(supported))


def _fit_main_close(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    width: int,
    height: int,
) -> Quad:
    """Fit the standalone Main close button without treating it as a grid cell."""
    center_x = width / 2
    lower_lines = [
        line
        for line in horizontal
        if height * 0.70 <= line[0] * center_x + line[1] <= height * 0.99
        and line[2] >= width * 0.16
    ]
    # Fit a border pair by its separation, rather than deciding that every
    # line below a fixed y cutoff must be the bottom edge. Zoom can move both
    # real edges down while the button remains fully visible.
    pairs = []
    for upper in lower_lines:
        top_y = _line_position(upper, center_x)
        for lower in lower_lines:
            gap = _line_position(lower, center_x) - top_y
            if height * 0.06 <= gap <= height * 0.18:
                score = abs(gap - height * 0.092) + .15 * abs(top_y - height * .815)
                pairs.append((score, upper, lower))
    bottom_candidates = [
        line for line in lower_lines
        if _line_position(line, center_x) >= height * .84
    ]
    if pairs:
        _, upper, lower = min(pairs, key=lambda item: item[0])
        top, bottom = upper[:2], lower[:2]
    elif bottom_candidates:
        bottom_candidate = min(
            bottom_candidates,
            key=lambda line: abs(line[0] * center_x + line[1] - height * 0.92),
        )
        bottom = bottom_candidate[:2]
        bottom_y = bottom[0] * center_x + bottom[1]
        top = (bottom[0], bottom[1] - height * 0.11)
    else:
        top = (0.0, height * 0.815)
        bottom = (0.0, height * 0.905)
    return _quad(
        _select_vertical(vertical, 0.0, width, height),
        _select_vertical(vertical, width * 0.24, width, height),
        top,
        bottom,
    )


def _line_candidates(
    frame: Frame,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 8, 30)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 720,
        threshold=35,
        minLineLength=70,
        maxLineGap=35,
    )
    horizontal: list[tuple[float, float, float]] = []
    vertical: list[tuple[float, float, float]] = []
    if lines is None:
        return horizontal, vertical
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        if not _has_border_color(frame, x1, y1, x2, y2):
            continue
        dx, dy = float(x2 - x1), float(y2 - y1)
        if abs(dx) >= 70 and abs(dy / dx) < 0.4:
            slope = dy / dx
            horizontal.append((slope, float(y1 - slope * x1), abs(dx)))
        elif abs(dy) >= 70 and abs(dx / dy) < 0.4:
            slope = dx / dy
            vertical.append((slope, float(x1 - slope * y1), abs(dy)))
    # Camera/display movement can leave a coherent residual shear after the
    # outer screen is rectified.  Keep the repeated, dominant UI orientation
    # rather than imposing an axis-aligned box or following an isolated hand
    # edge.
    return _dominant_orientation(horizontal), _dominant_orientation(vertical)


def _has_border_color(
    frame: Frame, x1: int, y1: int, x2: int, y2: int
) -> bool:
    positions = np.linspace(0.0, 1.0, 32)
    xs = np.clip(np.rint(x1 + (x2 - x1) * positions).astype(int), 0, frame.shape[1] - 1)
    ys = np.clip(np.rint(y1 + (y2 - y1) * positions).astype(int), 0, frame.shape[0] - 1)
    pixels = frame[ys, xs].astype(np.int16)
    blue, green, red = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    border_pixels = (blue >= 28) & (blue - green >= 12) & (blue - red >= 24)
    return float(np.mean(border_pixels)) >= 0.35


def _dominant_orientation(
    candidates: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    if not candidates:
        return []
    bin_width = 0.025
    weights: dict[int, float] = {}
    for slope, _, length in candidates:
        key = round(slope / bin_width)
        weights[key] = weights.get(key, 0.0) + length
    dominant = max(weights, key=weights.get) * bin_width
    nearby = [item for item in candidates if abs(item[0] - dominant) <= 0.04]
    total_length = sum(item[2] for item in nearby)
    center = sum(item[0] * item[2] for item in nearby) / total_length
    return [item for item in candidates if abs(item[0] - center) <= 0.14]


def _select_horizontal(
    candidates: list[tuple[float, float, float]],
    expected_y: float,
    width: int,
    height: int,
    *,
    min_length: float = 0.0,
    tolerance_fraction: float = 0.035,
) -> Line:
    center_x = width / 2
    nearby = [
        candidate
        for candidate in candidates
        if abs(candidate[0] * center_x + candidate[1] - expected_y)
        <= height * tolerance_fraction
    ]
    if not nearby:
        return 0.0, expected_y
    sufficiently_long = [candidate for candidate in nearby if candidate[2] >= min_length]
    if sufficiently_long:
        nearby = sufficiently_long
    slope, offset, _ = min(
        nearby,
        key=lambda line: abs(line[0] * center_x + line[1] - expected_y)
        - min(line[2], width) * 0.015,
    )
    return slope, offset


def _select_vertical(
    candidates: list[tuple[float, float, float]],
    expected_x: float,
    width: int,
    height: int,
) -> Line:
    center_y = height / 2
    nearby = [
        candidate
        for candidate in candidates
        if abs(candidate[0] * center_y + candidate[1] - expected_x) <= width * 0.04
    ]
    if not nearby:
        return 0.0, expected_x
    slope, offset, _ = min(
        nearby,
        key=lambda line: abs(line[0] * center_y + line[1] - expected_x)
        - min(line[2], height) * 0.01,
    )
    return slope, offset


def _quad(left: Line, right: Line, top: Line, bottom: Line) -> Quad:
    return np.array(
        [
            _intersection(left, top),
            _intersection(right, top),
            _intersection(right, bottom),
            _intersection(left, bottom),
        ],
        dtype=np.float32,
    )


def _intersection(vertical: Line, horizontal: Line) -> tuple[float, float]:
    x_slope, x_offset = vertical
    y_slope, y_offset = horizontal
    denominator = 1 - x_slope * y_slope
    y = (y_slope * x_offset + y_offset) / denominator
    return x_slope * y + x_offset, y
