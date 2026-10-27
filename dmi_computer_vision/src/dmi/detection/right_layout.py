"""Border-line fitting for right-display UI regions in rectified frames."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi_computer_vision.src.dmi.detection.left_layout import BorderEvidence, valid_quad

Frame = NDArray[np.uint8]
Quad = NDArray[np.float32]
Line = tuple[float, float]
LineCandidate = tuple[float, float, float]
BorderLines = tuple[list[LineCandidate], list[LineCandidate]]


def detect_border_lines(frame: Frame) -> BorderLines:
    """Extract reusable horizontal and vertical UI-border evidence."""
    return _line_candidates(frame)


def has_button_grid(frame: Frame) -> bool:
    """Validate an orphan region's role from repeated measured control borders.

    Layouts are hypotheses only. Even legacy nominal cells must have all four
    borders fitted locally before they support a region. No screen identity or
    named controls are returned from this geometry check.
    """
    evidence = BorderEvidence(frame)
    borders = detect_border_lines(frame)
    height, width = frame.shape[:2]
    for state in ("Main", "Driver ID", "Level"):
        centers = []
        for points in detect_button_quads(frame, state, borders).values():
            if not valid_quad(points):
                continue
            supported = True
            for a, b in zip(points, np.roll(points, -1, axis=0)):
                horizontal = abs(b[0] - a[0]) >= abs(b[1] - a[1])
                axis = "h" if horizontal else "v"
                start, end = sorted((a[0], b[0]) if horizontal else (a[1], b[1]))
                cross = (start + end) / 2
                position = float((a[1] + b[1]) / 2 if horizontal else (a[0] + b[0]) / 2)
                slope = float((b[1] - a[1]) / (b[0] - a[0]) if horizontal
                              else (b[0] - a[0]) / (b[1] - a[1]))
                inset = (end - start) * .15
                if evidence.fit(axis, position, cross, start + inset, end - inset,
                                radius=6, slope=slope, slope_radius=.025) is None:
                    supported = False
                    break
            if supported:
                centers.append(points.mean(axis=0))
        if len(centers) >= 6:
            centers = np.asarray(centers)
            if np.ptp(centers[:, 0]) > width * .3 and np.ptp(centers[:, 1]) > height * .15:
                return True
    return False


def detect_button_quads(
    frame: Frame,
    state: str,
    border_lines: BorderLines | None = None,
    *, level_read_cells: dict[str, Quad] | None = None,
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
        observed = _fit_active_area_grid(frame, names, action="close")
        if observed is not None:
            # A standalone close button can remain visible without a menu.
            # Retain its measured borders without inventing the missing grid.
            lower = [line for line in horizontal
                     if height * .7 <= _line_position(line, width / 2) <= height * .99]
            pair = any(height * .06 <= _line_position(b, width / 2) - _line_position(a, width / 2) <= height * .18
                       for a in lower for b in lower)
            sides = all(any(abs(_line_position(line, height * .9) - x) < width * .04
                            and line[2] >= height * .06 for line in vertical)
                        for x in (0., width * .25))
            upper_grid = any(_line_position(line, width / 2) < height * .7
                             and line[2] >= width * .6 for line in horizontal)
            if not observed and pair and sides and not upper_grid:
                return {"close": _fit_main_close(horizontal, vertical, width, height)}
            return observed
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
    if state in {"Driver ID", "Train Running Number"}:
        keypad_names = (
            ("digit_1", "digit_2", "digit_3"),
            ("digit_4", "digit_5", "digit_6"),
            ("digit_7", "digit_8", "digit_9"),
            ("delete", "digit_0", "decimal"),
        )
        observed = _fit_active_area_grid(
            frame, keypad_names, action="cancel" if state == "Driver ID" else "close",
        )
        if observed is not None:
            return observed
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
        if state == "Train Running Number":
            grid["close"] = _quad(
                action_x_lines[0], action_x_lines[1], y_lines[4], y_lines[5]
            )
            return grid
        grid.update(
            _cells_from_lines(
                action_x_lines,
                y_lines,
                (("cancel", "empty_action"),),
                x_indices=(0, 1, 2),
                y_indices=(4, 5),
            )
        )
        grid.update(_visible_driver_actions(
            frame, BorderEvidence(frame), action_x_lines, y_lines[4], y_lines[5],
        ))
        return grid
    if state in {"Train Data", "Validate Train Data"}:
        middle_top = .50 if state == "Train Data" else .685
        names = (("gamma", "lambda"),) if state == "Train Data" else (("no", "yes"),)
        grid = _fit_grid(
            horizontal, vertical, width, height,
            x_fractions=(0.0, .304, .609),
            y_fractions=(middle_top, middle_top + .095), names=names,
        )
        row_transform = None
        if state == "Validate Train Data":
            row_positions = (middle_top * height, (middle_top + .095) * height)
            row_candidates = [line for line in horizontal
                              if height * .5 < _line_position(line, width * .3) < height * .85
                              and line[2] >= width * .4]
            row_lines = _fit_axis_topology(
                row_candidates, row_positions, extent=height, cross_center=width * .3,
            )
            row_transform = _transform_from_fitted_lines(
                row_lines, row_positions, width * .125, height,
            )
            x_lines = [_select_vertical(vertical, value * width, width, height)
                       for value in (0.0, .304, .609)]
            grid = _cells_from_lines(x_lines, row_lines, names,
                                     x_indices=(0, 1, 2), y_indices=(0, 1))
        action_positions = ((0.0, .255, .745, .92) if state == "Train Data"
                            else (0.0, .255))
        action_x = _fit_axis_topology(
            vertical, tuple(value * width for value in action_positions),
            extent=width, cross_center=height * .92,
        )
        action_horizontal = (horizontal if state == "Train Data" else
                             [line for line in horizontal if line[2] <= width * .4])
        action_y = _fit_axis_topology(
            action_horizontal, (.875 * height, .97 * height),
            extent=height, cross_center=width * (.5 if state == "Train Data" else .125),
            fixed_transform=row_transform,
        )
        grid["close"] = _quad(action_x[0], action_x[1], *action_y)
        if state == "Train Data":
            grid["enter_data"] = _quad(action_x[2], action_x[3], *action_y)
        return grid
    if state == "Train Data (1/2)":
        grid = _fit_grid(
            horizontal, vertical, width, height,
            x_fractions=(0.0, .305, .61, .92),
            y_fractions=(.485, .578, .671, .765, .859),
            names=(("digit_1", "digit_2", "digit_3"),
                   ("digit_4", "digit_5", "digit_6"),
                   ("digit_7", "digit_8", "digit_9"),
                   ("delete", "digit_0", "decimal")),
            coherent=True,
        )
        grid.update(_train_navigation(horizontal, vertical, width, height,
                                      preceding_row=grid["delete"]))
        return grid
    if state == "Train Data (2/2)":
        grid = _fit_grid(
            horizontal, vertical, width, height,
            x_fractions=(0.0, .305, .61, .92),
            y_fractions=(.459, .548, .637),
            names=(("g1", "ga", "gb"),
                   ("gc", "out_of_gc", "unused_selection")),
            coherent=True,
        )
        grid.pop("unused_selection")
        grid.update(_train_navigation(horizontal, vertical, width, height))
        return grid
    if state == "Level":
        return _level_button_cells(frame, read_cells=level_read_cells)
    return _detect_unknown_buttons(frame, horizontal, vertical)


def _level_button_cells(
    frame: Frame, *, read_cells: dict[str, Quad] | None = None,
) -> dict[str, Quad]:
    """Propose cells from current gradients and validate every side locally.

    No nominal row/column placement, missing-edge extrapolation or semantic
    labels: Level identities are recognized from each supported cell's content.
    Optional read_cells receives current narrow-fit cells for unchanged OCR;
    returned cells include the extra supported-face refinement.
    """
    if read_cells is not None:
        read_cells.clear()
    height, width = frame.shape[:2]
    evidence = BorderEvidence(frame)
    pixels = frame.astype(np.float32)
    glyphs = ((pixels[:, :, 2] > pixels[:, :, 0] * .25)
              & (pixels[:, :, 1] > pixels[:, :, 0] * .45)
              & (pixels.max(axis=2) > 40)).astype(np.uint8)
    glyphs = cv2.dilate(glyphs, np.ones((11, 11), np.uint8))
    evidence.horizontal[glyphs > 0] = 0
    evidence.vertical[glyphs.T > 0] = 0
    horizontal = np.quantile(evidence.horizontal[:, 5:-5], .8, axis=1)
    horizontal[:round(height * .3)] = 0
    rows = _border_peaks(horizontal, separation=round(height * .025))
    if not rows:
        return {}
    row_floor = max(1.5, float(np.median(sorted(horizontal[rows], reverse=True)[:3])) * .25)
    cells = []
    for top in rows:
        for bottom in rows:
            step = bottom - top
            if not height * .055 < step < height * .16:
                continue
            start, end = top + step * .15, bottom - step * .15
            profile = evidence.profile('v', round(start), round(end))
            peaks = _border_peaks(profile, separation=round(width * .025))
            if len(peaks) < 2:
                continue
            # Bezel edges can dwarf thin UI borders. Establish contrast from
            # the strongest observed interior dividers when both are available.
            interior = sorted((profile[x] for x in peaks if width*.08 < x < width*.92), reverse=True)
            reference = (float(np.median(interior[:2])) if len(interior) >= 2
                         else float(np.median(sorted(profile[peaks], reverse=True)[:3])))
            column_floor = max(1.5, reference * (.35 if len(interior) >= 2 else .12))
            columns = []
            for x in peaks:
                line = evidence.fit("v", x, (top + bottom)/2, start, end,
                                    radius=4, slope_radius=.06)
                if line is not None and _level_edge_supported(
                        evidence, "v", line, top, bottom, minimum=column_floor):
                    columns.append((x, line))
            # Reject texture/glyph peaks before adjacency is established. A
            # spurious peak must not split a real bordered cell into false slots.
            for (left, left_line), (right, right_line) in zip(columns, columns[1:]):
                span = right - left
                if not width * .12 < span < width * .43:
                    continue
                cx, cy = (left + right) / 2, (top + bottom) / 2
                sides = (
                    left_line,
                    right_line,
                    evidence.fit("h", top, cx, left + span * .12, right - span * .12,
                                 radius=4, slope_radius=.06),
                    evidence.fit("h", bottom, cx, left + span * .12, right - span * .12,
                                 radius=4, slope_radius=.06),
                )
                if any(side is None for side in sides):
                    continue
                if not all(_level_edge_supported(evidence, axis, line, lo, hi,
                                                 minimum=column_floor if axis == "v" else row_floor)
                           for axis, line, lo, hi in (
                               ("v", sides[0], top, bottom), ("v", sides[1], top, bottom),
                               ("h", sides[2], left, right), ("h", sides[3], left, right))):
                    continue
                # A nearer measured divider rules out a larger box spanning
                # that divider (for example Close plus the monitor boundary).
                inner = evidence.profile('h', round(left + span*.12), round(right - span*.12))
                intervening = _border_peaks(inner, separation=round(height * .015))
                divider = False
                for y in intervening:
                    if not top + step*.18 < y < bottom - step*.18:
                        continue
                    line = evidence.fit("h", y, cx, left + span*.12, right - span*.12,
                                        radius=3, slope_radius=.06)
                    if line is not None and _level_edge_supported(
                            evidence, "h", line, left, right, minimum=row_floor):
                        divider = True
                        break
                if divider:
                    continue
                # Neighboring buttons can have separate outlines and a narrow
                # gap. Fit the face towards this cell instead of sharing an
                # arbitrary member of the measured divider cluster.
                reading_edges = [] if read_cells is not None else None
                sides = (
                    _level_inner_edge(evidence, "v", sides[0], top, bottom,
                                      radius=span*.06, positive=True, minimum=column_floor,
                                      reading_edges=reading_edges),
                    _level_inner_edge(evidence, "v", sides[1], top, bottom,
                                      radius=span*.06, positive=False, minimum=column_floor,
                                      reading_edges=reading_edges),
                    _level_inner_edge(evidence, "h", sides[2], left, right,
                                      radius=step*.12, positive=True, minimum=row_floor,
                                      reading_edges=reading_edges),
                    _level_inner_edge(evidence, "h", sides[3], left, right,
                                      radius=step*.12, positive=False, minimum=row_floor,
                                      reading_edges=reading_edges),
                )
                points = _quad(*sides)
                reading = _quad(*reading_edges) if reading_edges is not None else points
                if all(valid_quad(q) and np.all(q >= 0)
                       and np.all(q[:, 0] < width) and np.all(q[:, 1] < height)
                       for q in (points, reading)):
                    cells.append((points, reading))
    cells.sort(key=lambda pair: (float(pair[0][:, 1].mean()), float(pair[0][:, 0].mean())))
    if read_cells is not None:
        read_cells.update({f"button_{i}": reading for i, (_, reading) in enumerate(cells, 1)})
    return {f"button_{i}": q for i, (q, _) in enumerate(cells, 1)}


def _level_inner_edge(evidence: BorderEvidence, axis: str, line: Line,
                      start: float, end: float, *, radius: float,
                      positive: bool, minimum: float,
                      reading_edges: list[Line] | None = None) -> Line:
    """Choose a supported face; optionally retain the narrow fit for current OCR."""
    response = evidence.horizontal if axis == "h" else evidence.vertical
    samples = np.linspace(start+(end-start)*.12, end-(end-start)*.12, 64, dtype=np.float32)
    offsets = np.arange(-round(radius), round(radius)+1, dtype=np.float32)
    dependent = line[0]*samples + line[1]
    sampled = cv2.remap(response, np.broadcast_to(samples, (len(offsets), 64)),
                        dependent[None, :] + offsets[:, None], cv2.INTER_LINEAR)
    scores = np.median(sampled, axis=1)
    maxima = cv2.dilate(scores[None, :], np.ones((1, 3), np.uint8))[0]
    peaks = np.flatnonzero((scores >= maxima) & (scores >= max(minimum, float(scores.max())*.3)))
    cross = (start+end)/2
    # Preserve every successful narrow fit before trying a wider search. A broad
    # gradient peak can fill the narrow search and fail fit's contrast test;
    # only then retry with background, keeping the same edge support checks.
    for radius_px in (1, 3):
        for index in (peaks[::-1] if positive else peaks):
            fitted = evidence.fit(axis, line[0]*cross+line[1]+offsets[index], cross,
                                  start+(end-start)*.12, end-(end-start)*.12,
                                  radius=radius_px, slope=line[0], slope_radius=.015)
            if fitted is not None and _level_edge_supported(
                    evidence, axis, fitted, start, end, minimum=minimum):
                if radius_px == 1 and reading_edges is not None:
                    reading_edges.append(fitted)
                return fitted
        if radius_px == 1 and reading_edges is not None:
            # These borders were already validated before refinement. Keeping
            # this same-pass crop avoids changing OCR resampling/retry cost
            # when only a broad outline's exported face needs correction.
            reading_edges.append(line)
    return line  # The original edge already passed the same current-evidence check.


def _level_edge_supported(evidence: BorderEvidence, axis: str, line: Line,
                          start: float, end: float, *, minimum: float = 1.5) -> bool:
    """A glyph stroke cannot stand in for a nearly complete control edge."""
    cache = getattr(evidence, '_supports', None)
    key = (axis, line, start, end, minimum)
    if cache is not None and key in cache:
        return cache[key]
    response = evidence.horizontal if axis == "h" else evidence.vertical
    samples = np.linspace(start + (end-start)*.04, end - (end-start)*.04, 64, dtype=np.float32)
    dependent = line[0]*samples + line[1]
    offsets = np.r_[np.arange(-12, -6), np.arange(-2, 3), np.arange(7, 13)]
    sampled = cv2.remap(response, np.broadcast_to(samples, (len(offsets), 64)),
                        (dependent[None, :] + offsets[:, None]).astype(np.float32),
                        cv2.INTER_LINEAR)
    values = sampled[6:11].max(axis=0)
    background = np.median(np.r_[sampled[:6], sampled[11:]], axis=0)
    # Camera texture can have nonzero gradients along an arbitrary line. Each
    # edge must stand out from its parallel local background, not just be nonzero.
    supported = bool(np.mean(values > np.maximum(minimum, background * 1.8)) >= .8)
    if cache is not None:
        cache[key] = supported
    return supported


def _border_peaks(profile: NDArray, *, separation: int) -> list[int]:
    """Return measured response peaks, never predicted missing lines."""
    work = cv2.GaussianBlur(np.asarray(profile, np.float32)[:, None], (1, 3), 0).ravel()
    threshold = max(1.5, float(np.median(work)) * 4, float(work.max()) * .04)
    peaks = []
    for _ in range(24):
        index = int(work.argmax())
        if work[index] < threshold:
            break
        peaks.append(index)
        work[max(0, index - separation):index + separation + 1] = 0
    return sorted(peaks)


def _train_navigation(
    horizontal: list[LineCandidate], vertical: list[LineCandidate],
    width: int, height: int,
    preceding_row: Quad | None = None,
) -> dict[str, Quad]:
    x_lines = [_select_vertical(vertical, value * width, width, height)
               for value in (0.0, .255, .5, .745, .92)]
    y_lines = [_select_horizontal(horizontal, value * height, width, height)
               for value in (.86, .96)]
    if preceding_row is not None:
        # The keypad's last row and the navigation row share one visible edge.
        left, right = preceding_row[3], preceding_row[2]
        slope = float((right[1] - left[1]) / (right[0] - left[0]))
        top = (slope, float(left[1] - slope * left[0]))
        row_height = float(np.mean(preceding_row[2:, 1]) - np.mean(preceding_row[:2, 1]))
        y_lines = [top, _select_horizontal(
            horizontal, _line_position(top, width / 2) + row_height, width, height,
        )]
    return _cells_from_lines(
        x_lines, y_lines,
        (("close", "left_arrow", "right_arrow", "select_type"),),
        x_indices=(0, 1, 2, 3, 4), y_indices=(0, 1),
    )


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


def _fit_active_area_grid(
    frame: Frame, names: tuple[tuple[str, ...], ...], *, action: str,
) -> dict[str, Quad] | None:
    """Fit a border-supported grid when UI columns fill the logical crop.

    Distinguish legacy margins/action columns from full-width UI evidence.
    Missing full-width borders must cause omissions rather than falling back
    to nominal legacy controls.
    """
    height, width = frame.shape[:2]
    rows, columns = len(names), len(names[0])
    menu = columns == 2
    evidence = BorderEvidence(frame)
    start, end = ((.16, .65) if menu else (.46, .85))
    # A gradient at the crop edge can be a black bezel, not a UI column.
    # Measure the active blue extent as well as the internal grid lines.
    edge = frame[round(height * start):round(height * end),
                 round(width * .97):round(width * .995)].astype(np.int16)
    blue_extent = np.mean((edge[:, :, 0] >= 18)
                          & (edge[:, :, 0] - edge[:, :, 1] >= 6)
                          & (edge[:, :, 0] - edge[:, :, 2] >= 12)) >= .65
    if not blue_extent:
        return None
    verticals = []
    for index in range(columns + 1):
        expected = (width - 1) * index / columns
        line = evidence.fit("v", expected, height / 2, height * start, height * end,
                            radius=width * .025, slope_radius=.015)
        if line is not None and abs(_line_position((*line, 0), height / 2) - expected) > width * .025:
            line = None
        verticals.append(line)
    if verticals[-1] is None:
        margin_edge = evidence.fit("v", width * .915, height / 2,
                                   height * start, height * end,
                                   radius=width * .025, slope_radius=.04)
        if margin_edge is not None:
            return None
    if columns == 3 and any(line is None for line in verticals):
        # Extra observed action-row columns identify the accepted multi-slot
        # layout even when an upper keypad border is occluded.
        lower = np.median(evidence.vertical[:, round(height * .89):round(height * .94)], axis=1)
        lo, hi = round(width * .3), round(width * .9)
        peak = lo + int(np.argmax(lower[lo:hi]))
        if lower[peak] > max(4., float(np.median(lower)) * 5):
            action_column = evidence.fit("v", peak, height * .915,
                                         height * .89, height * .94,
                                         radius=5, slope_radius=.025)
            if action_column is not None:
                return None

    profile = np.median(evidence.horizontal[:, round(width * .07):round(width * .93)], axis=1)
    profile = cv2.GaussianBlur(profile[:, None], (1, 5), 0).ravel()
    low, high = ((.08, .70) if menu else (.35, .89))
    work = profile.copy()
    work[:round(height * low)] = 0
    work[round(height * high):] = 0
    horizontal = []
    for _ in range(24):
        peak = int(work.argmax())
        if work[peak] < max(2.0, float(np.median(profile)) * 4):
            break
        work[max(0, peak - 12):peak + 13] = 0
        line = evidence.fit("h", peak, width / 2, width * .05, width * .95,
                            radius=6, slope_radius=.02)
        if line is not None:
            horizontal.append(line)
    if not any(verticals[1:-1]) and len(horizontal) < 3:
        return {}
    if any(line is None for line in verticals):
        return {}
    horizontal.sort(key=lambda line: _line_position((*line, 0), width / 2))
    positions = np.array([_line_position((*line, 0), width / 2) for line in horizontal])
    best = None
    for first in positions:
        if not (height * (.08 if menu else .35) < first < height * (.23 if menu else .53)):
            continue
        for last in positions:
            step = (last - first) / rows
            if not height * .07 < step < height * .13:
                continue
            expected = first + np.arange(rows + 1) * step
            distance = np.abs(expected[:, None] - positions)
            indices = distance.argmin(axis=1)
            errors = distance[np.arange(rows + 1), indices]
            if len(set(indices)) != rows + 1 or errors.max() > step * .17:
                continue
            score = float(errors.sum() + .05 * abs(step - height * .1))
            if best is None or score < best[0]:
                best = score, indices, step
    if best is None:
        return {}
    _, indices, step = best
    fitted = [horizontal[index] for index in indices]
    result = _cells_from_lines(verticals, fitted, names,
                               x_indices=tuple(range(columns + 1)),
                               y_indices=tuple(range(rows + 1)))
    # Fit the cross independently; optional Driver ID controls cannot be a gate
    # for the keypad or inferred from an earlier observation.
    bottom_y = height * .965 if menu else _line_position((*fitted[-1], 0), width / 2) + step
    top_y = bottom_y - step
    right = evidence.fit("v", width * .25, (top_y + bottom_y) / 2,
                         top_y + step * .15, bottom_y - step * .15,
                         radius=width * .04, slope_radius=.025)
    if right is not None:
        right_x = _line_position((*right, 0), (top_y + bottom_y) / 2)
        left = evidence.fit("v", 2, (top_y + bottom_y) / 2,
                            top_y + step * .15, bottom_y - step * .15,
                            radius=6, slope_radius=.025)
        top = evidence.fit("h", top_y, right_x / 2, 8, right_x - 8,
                           radius=height * .025, slope_radius=.025)
        bottom = evidence.fit("h", bottom_y, right_x / 2, 8, right_x - 8,
                              radius=height * .025, slope_radius=.025)
        if left is not None and top is not None and bottom is not None:
            result[action] = _quad(left, right, top, bottom)
    if action == "cancel":
        # These proportions propose searches in the measured full-width crop.
        # Each optional cell still needs its own four edges and visible content.
        action_columns = [tuple((1 - fraction) * np.array(verticals[0])
                                + fraction * np.array(verticals[-1]))
                          for fraction in (0., .25, .46, .73, 1.)]
        result.update(_visible_driver_actions(
            frame, evidence, action_columns, fitted[-1],
            (fitted[-1][0], fitted[-1][1] + step),
        ))
    return {name: points for name, points in result.items() if valid_quad(points)}


def _visible_driver_actions(
    frame: Frame, evidence: BorderEvidence, columns: list[Line], top: Line, bottom: Line,
) -> dict[str, Quad]:
    """Return independently visible TRN/wrench cells; keep existing identities."""
    height, width = frame.shape[:2]
    result = {}
    for name, index in (("trn", 2), ("settings", 3)):
        guess = _quad(columns[index], columns[index + 1], top, bottom)
        center_x, center_y = guess.mean(axis=0)
        x1, x2 = float(guess[:, 0].min()), float(guess[:, 0].max())
        y1, y2 = float(guess[:, 1].min()), float(guess[:, 1].max())
        if x2 - x1 < 16 or y2 - y1 < 16:
            continue
        left = evidence.fit("v", float(guess[[0, 3], 0].mean()), center_y,
                            y1 + (y2 - y1) * .15, y2 - (y2 - y1) * .15,
                            radius=width * .025, slope=columns[index][0])
        right = evidence.fit("v", float(guess[[1, 2], 0].mean()), center_y,
                             y1 + (y2 - y1) * .15, y2 - (y2 - y1) * .15,
                             radius=width * .025, slope=columns[index + 1][0])
        upper = evidence.fit("h", float(guess[:2, 1].mean()), center_x,
                             x1 + (x2 - x1) * .15, x2 - (x2 - x1) * .15,
                             radius=height * .025, slope=top[0])
        lower = evidence.fit("h", float(guess[2:, 1].mean()), center_x,
                             x1 + (x2 - x1) * .15, x2 - (x2 - x1) * .15,
                             radius=height * .025, slope=bottom[0])
        if any(line is None for line in (left, right, upper, lower)):
            continue
        points = _quad(left, right, upper, lower)
        if not valid_quad(points):
            continue
        destination = np.float32([[0, 0], [119, 0], [119, 79], [0, 79]])
        cell = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(points, destination), (120, 80))
        # A bordered empty slot is not a visible TRN or wrench. Test interior
        # glyph/icon evidence without OCR, supplied text or remembered controls.
        hsv = cv2.cvtColor(cell[12:68, 18:102], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 100), (179, 120, 255))
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        content = [stats[i, cv2.CC_STAT_AREA] for i in range(1, count)
                   if stats[i, cv2.CC_STAT_WIDTH] >= 3 and stats[i, cv2.CC_STAT_HEIGHT] >= 6
                   and 12 <= stats[i, cv2.CC_STAT_AREA] < mask.size * .5]
        if sum(content) >= 18:
            result[name] = points
    return result


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
    coherent: bool = False,
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
    if coherent:
        # Fit the whole row pattern before selecting individual borders.
        # A shifted grid must not leave a missing edge at its nominal position.
        y_lines = _fit_axis_topology(
            horizontal, tuple(value * height for value in y_fractions),
            extent=height, cross_center=width * np.mean(x_fractions),
            min_length=max(horizontal_min_length, width * .25),
        )
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
    observed = np.asarray(detected, dtype=np.float64)
    expected = np.asarray(expected_positions, dtype=np.float64)
    # Score exactly the same hypotheses in their original order. A sorted
    # nearest-neighbor lookup replaces the Python scan over every detected
    # line; chunks bound the temporary arrays on texture-heavy crops.
    for start in range(0, len(hypotheses), 1024):
        batch = np.asarray(hypotheses[start:start + 1024], dtype=np.float64)
        scales, offsets = batch[:, 0], batch[:, 1]
        predicted = scales[:, None] * expected + offsets[:, None]
        indices = np.searchsorted(observed, predicted)
        lower = observed[np.clip(indices - 1, 0, len(observed) - 1)]
        upper = observed[np.clip(indices, 0, len(observed) - 1)]
        residuals = np.minimum(np.abs(predicted - lower), np.abs(predicted - upper))
        matched = residuals <= tolerance
        counts = matched.sum(axis=1)
        totals = np.zeros(len(batch))
        # Accumulate in the original order, preserving rounding and tie rules.
        for column in range(len(expected)):
            totals += np.where(matched[:, column], residuals[:, column], 0.0)
        scores = (-totals - np.abs(scales - 1.0) * extent * 0.01
                  - np.abs(offsets) * 0.05)
        eligible = np.flatnonzero(counts == counts.max())
        selected = int(eligible[np.argmax(scores[eligible])])
        score = (int(counts[selected]), float(scores[selected]))
        if score > best_score:
            best_score = score
            best = tuple(batch[selected])
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
