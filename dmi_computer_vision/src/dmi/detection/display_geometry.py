"""Detection and rectification of logical DMI regions on one or two surfaces."""

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
        oriented = np.rint(self.oriented_box).astype(int)
        outline = np.concatenate((corners, oriented))
        # The internal segmentation bounds support tracking, but serialized
        # bounds must enclose both reported fitted outlines.
        bbox = [*outline.min(axis=0).tolist(), *outline.max(axis=0).tolist()]
        return {
            "corners": corners.tolist(),
            "oriented_box": oriented.tolist(),
            "bbox": bbox,
            "center": list(self.center),
        }


def detect_displays(
    frame: Frame,
    *,
    diagnostics: dict[str, str] | None = None,
) -> dict[str, DisplayGeometry | None]:
    """Locate the left and right display surfaces in one BGR frame.

    The illuminated DMI surfaces have a consistent blue hue even as their
    brightness changes. Large blue components are grouped horizontally, then
    four boundary lines are fit to each group. A connected-surface fallback
    requires a monitor boundary and independently aligned current border segments.
    Optional diagnostics are per-call only; no warnings are emitted per frame.
    """
    if diagnostics is not None:
        diagnostics.clear()
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
        connected = _detect_connected_displays(frame, mask, diagnostics)
        if any(value is not None for value in connected.values()):
            return connected
        return _retain_partial_displays(
            frame, [[component] for component in components], strong_mask, diagnostics,
        )

    geometries: list[DisplayGeometry] = []
    for group in groups:
        geometry = _fit_display(group, strong_mask, (height, width))
        if geometry is None:
            connected = _detect_connected_displays(frame, mask, diagnostics)
            if any(value is not None for value in connected.values()):
                return connected
            return _retain_partial_displays(frame, list(groups), strong_mask, diagnostics)
        geometries.append(geometry)

    if geometries[0].center[0] >= geometries[1].center[0]:
        return {"left": None, "right": None}
    geometries = _align_display_box_aspect(geometries, height)
    if diagnostics is not None:
        diagnostics.update(path="separated", reason="")
    return {"left": geometries[0], "right": geometries[1]}


def _retain_partial_displays(
    frame: Frame, contour_groups: list[list[NDArray[np.int32]]],
    strong_mask: NDArray[np.uint8], diagnostics: dict[str, str] | None,
) -> dict[str, DisplayGeometry | None]:
    """Keep only a full portrait region with independently observed UI topology.

    A lone component has no horizontal partner to establish its role. Use the
    existing sidebar or verified grid-cell borders, never camera index, image
    half, screen OCR or the location of a missing partner. Wide connected
    surfaces cannot pass the portrait fit. No occluded boundary is extrapolated.
    """
    from dmi_computer_vision.src.dmi.detection.left_layout import BorderEvidence, sidebar_borders
    from dmi_computer_vision.src.dmi.detection.right_layout import has_button_grid

    candidates: dict[str, list[DisplayGeometry]] = {"left": [], "right": []}
    height, width = frame.shape[:2]
    for group in contour_groups:
        geometry = _fit_display(group, strong_mask, (height, width))
        if geometry is None:
            continue
        outline = geometry.corners
        if (outline[:, 0].min() <= 2 or outline[:, 1].min() <= 2
                or outline[:, 0].max() >= width - 3 or outline[:, 1].max() >= height - 3):
            continue
        rectified = rectify_display(frame, geometry, (800, 1280))
        if sidebar_borders(BorderEvidence(rectified)) is not None:
            candidates["left"].append(geometry)
            continue
        if has_button_grid(rectified):
            candidates["right"].append(geometry)
    if any(len(values) > 1 for values in candidates.values()):
        if diagnostics is not None:
            diagnostics.update(path="partial", reason="ambiguous_region")
        return {"left": None, "right": None}
    result = {side: values[0] if values else None for side, values in candidates.items()}
    if all(value is not None for value in result.values()):
        if result["left"].center[0] >= result["right"].center[0]:
            return {"left": None, "right": None}
        result["left"], result["right"] = _align_display_box_aspect(
            [result["left"], result["right"]], height,
        )
    if diagnostics is not None and any(value is not None for value in result.values()):
        diagnostics.update(path="partial", reason="partner_not_validated")
    return result


def _detect_connected_displays(
    frame: Frame,
    blue_seed: NDArray[np.uint8],
    diagnostics: dict[str, str] | None,
) -> dict[str, DisplayGeometry | None]:
    """Require a unique blue-seeded surface and an observed logical division."""
    # Work at a bounded scale: gradients in native high-resolution captures
    # spread over more pixels. Map pixel centers back after fitting, never use
    # the analysis image as the published coordinate system.
    original_height, original_width = frame.shape[:2]
    scale = min(1.0, 960 / max(original_height, original_width))
    if scale < 1:
        size = (round(original_width * scale), round(original_height * scale))
        frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        blue_seed = cv2.resize(blue_seed, size, interpolation=cv2.INTER_NEAREST)
    height, width = frame.shape[:2]
    sx, sy = original_width / width, original_height / height
    to_original = np.array([[sx, 0, (sx - 1) / 2], [0, sy, (sy - 1) / 2], [0, 0, 1]])
    # Dim upper margins are less saturated than the illuminated lower surface.
    # This mask only proposes boundaries; it cannot establish a DMI by itself.
    broad = cv2.inRange(
        cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), (85, 40, 18), (125, 255, 255)
    )
    size = _odd_kernel_size(min(height, width) * 0.01, minimum=3)
    broad = cv2.morphologyEx(
        broad, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8), iterations=2
    )
    broad = cv2.morphologyEx(broad, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(broad, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    accepted = []
    reason = "no_surface"
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if cv2.contourArea(contour) < height * width * 0.1 or not 1.05 < w / h < 2.1:
            continue
        local = np.zeros((h, w), np.uint8)
        cv2.drawContours(local, [contour - (x, y)], -1, 255, -1)
        if np.count_nonzero(blue_seed[y:y + h, x:x + w] & local) < w * h * 0.25:
            continue
        surface = _connected_surface_corners(frame, contour)
        if surface is None:
            clipped = x <= 2 or y <= 2 or x + w >= width - 2 or y + h >= height - 2
            reason = "unobserved_boundary" if clipped else "invalid_surface"
            continue
        side_lengths = np.linalg.norm(np.roll(surface, -1, axis=0) - surface, axis=1)
        rect_width = 800
        rect_height = round(
            rect_width * (side_lengths[1] + side_lengths[3])
            / (side_lengths[0] + side_lengths[2])
        )
        destination = np.array(
            [[0, 0], [rect_width - 1, 0], [rect_width - 1, rect_height - 1],
             [0, rect_height - 1]], np.float32,
        )
        transform = cv2.getPerspectiveTransform(surface, destination)
        rectified = cv2.warpPerspective(frame, transform, (rect_width, rect_height))
        division_diagnostics: dict[str, str] = {}
        division = _connected_division(rectified, diagnostics=division_diagnostics)
        if division is None:
            reason = "ambiguous_division"
            continue
        top_x, bottom_x = division
        inverse = to_original @ np.linalg.inv(transform)
        regions = []
        for corners in (
            [[0, 0], [top_x, 0], [bottom_x, rect_height - 1], [0, rect_height - 1]],
            [[top_x, 0], [rect_width - 1, 0], [rect_width - 1, rect_height - 1],
             [bottom_x, rect_height - 1]],
        ):
            original = cv2.perspectiveTransform(np.array([corners], np.float32), inverse)[0]
            # The connected path has smaller logical areas than the legacy mask;
            # validate each real quadrilateral without changing legacy thresholds.
            sides = np.linalg.norm(np.roll(original, -1, axis=0) - original, axis=1)
            if (
                not cv2.isContourConvex(original)
                or cv2.contourArea(original, oriented=True) <= 0
                or (sides[1] + sides[3]) <= 1.2 * (sides[0] + sides[2])
            ):
                regions.append(None)
                continue
            oriented = _fit_oriented_box(original.reshape(-1, 1, 2))
            outline = np.concatenate((original, oriented))
            x1, y1 = np.floor(outline.min(axis=0))
            x2, y2 = np.ceil(outline.max(axis=0))
            bbox = (int(x1), int(y1), int(x2), int(y2))
            regions.append(DisplayGeometry(original, oriented, bbox))
        if any(region is not None for region in regions):
            accepted.append(({"left": regions[0], "right": regions[1]}, division_diagnostics))
        else:
            reason = "invalid_region"
    if len(accepted) == 1:
        reason = ("" if all(value is not None for value in accepted[0][0].values())
                  else "invalid_region")
    elif len(accepted) > 1:
        reason = "ambiguous_surface"
    if diagnostics is not None:
        diagnostics.update(path="connected", reason=reason)
        if len(accepted) == 1:
            diagnostics.update(accepted[0][1])
    return accepted[0][0] if len(accepted) == 1 else {"left": None, "right": None}


def _connected_surface_corners(
    frame: Frame, contour: NDArray[np.int32],
) -> PointArray | None:
    """Refine a color-boundary hypothesis against measured inward blue edges."""
    hull = cv2.convexHull(contour)
    approximation = cv2.approxPolyDP(hull, cv2.arcLength(hull, True) * 0.02, True)
    if len(approximation) == 4:
        points = approximation.reshape(-1, 2).astype(np.float32)
        sums, differences = points.sum(axis=1), np.diff(points, axis=1).ravel()
        guess = points[[sums.argmin(), differences.argmin(), sums.argmax(), differences.argmax()]]
    else:
        guess = _fit_oriented_box(hull)
    span = max(5, round(min(cv2.boundingRect(contour)[2:]) * 0.05))
    enclosure = _fit_oriented_box(hull)
    corners = _refine_connected_surface(frame, guess, span)
    if corners is None and len(approximation) == 4:
        corners = _refine_connected_surface(frame, enclosure, span)
    # A pale UI block can pull a top fit materially into the content even
    # while its residual passes. Compare an independently supported dim-margin
    # crossing, preserving existing fits when disagreement is ordinary jitter.
    outer = _refine_connected_surface(frame, enclosure, span, outer_transition=True)
    if outer is not None and (corners is None or
            np.max(np.linalg.norm(corners[:2] - outer[:2], axis=1)) > span * 0.5):
        corners = outer
    return corners


def _structure_mask(frame: Frame) -> NDArray[np.uint8]:
    """Exclude saturated non-blue marks from blue/neutral border evidence.

    Bright green/magenta annotations (or unrelated colored objects) cannot
    supply a measured screen boundary. Dark background remains usable contrast.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    unrelated = (((hsv[:, :, 0] < 75) | (hsv[:, :, 0] > 130))
                 & (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 70)).astype(np.uint8)
    return 1 - cv2.dilate(unrelated, np.ones((7, 7), np.uint8))


def _refine_connected_surface(
    frame: Frame, guess: PointArray, search_span_px: int,
    *, outer_transition: bool = False,
) -> PointArray | None:
    """Fit one boundary hypothesis from distributed, contrast-supported edges."""
    chroma = frame[:, :, 0].astype(np.float32) - frame[:, :, 2].astype(np.float32)
    chroma = cv2.GaussianBlur(chroma, (5, 5), 1)
    valid_structure = _structure_mask(frame)
    lines = []
    for index in range(4):
        start, end = guess[index], guess[(index + 1) % 4]
        edge = end - start
        inward = np.array([-edge[1], edge[0]]) / np.linalg.norm(edge)
        span = search_span_px
        positions = start + np.linspace(0.1, 0.9, 64)[:, None] * edge
        offsets = np.arange(-span, span + 1)
        samples = positions[:, None, :] + offsets[None, :, None] * inward
        values = cv2.remap(
            chroma, samples[:, :, 0].astype(np.float32), samples[:, :, 1].astype(np.float32),
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )
        valid = cv2.remap(
            valid_structure, samples[:, :, 0].astype(np.float32),
            samples[:, :, 1].astype(np.float32), cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        ).astype(bool)
        gradient = np.diff(values, axis=1)
        margin = max(2, span // 2)
        measured = np.ma.array(values, mask=~valid)
        outside = np.ma.median(measured[:, :margin], axis=1).filled(0)
        inside = np.ma.median(measured[:, -margin:], axis=1).filled(0)
        midpoint = (inside + outside)[:, None] / 2
        if outer_transition and index == 0:
            midpoint = (outside + np.minimum((inside - outside) / 2, 4.0))[:, None]
        crossing = ((values[:, :-1] < midpoint) & (values[:, 1:] >= midpoint)
                    & valid[:, :-1] & valid[:, 1:])
        peaks = np.where(crossing, gradient, 0).argmax(axis=1)
        strength = np.where(crossing, gradient, 0)[np.arange(len(peaks)), peaks]
        # A control line inside a clipped blue surface is not its outer edge.
        noise = np.ma.median(
            np.ma.array(np.abs(gradient), mask=~(valid[:, :-1] & valid[:, 1:])),
            axis=1,
        ).filled(0)
        contrast_floor = np.maximum(4.0, np.maximum(inside * 0.25, noise * 6))
        keep = ((strength >= np.maximum(0.8, noise * 2.5))
                & ((inside - outside) >= contrast_floor)
                & (valid[:, :margin].mean(axis=1) >= 0.5)
                & (valid[:, -margin:].mean(axis=1) >= 0.5))
        if np.count_nonzero(keep) < len(keep) * 0.6:
            return None
        observed = positions + (offsets[peaks] + 0.5)[:, None] * inward
        if index % 2 == 0:
            independent, dependent = observed[:, 0], observed[:, 1]
        else:
            independent, dependent = observed[:, 1], observed[:, 0]
        fit = _robust_linear_fit(independent[keep], dependent[keep])
        residual = np.abs(dependent - np.polyval(fit, independent))
        if np.count_nonzero(residual < 3.0) < len(keep) * 0.6:
            return None
        lines.append(fit)
    top, right, bottom, left = lines
    corners = np.array(
        [_intersect_lines(left, top), _intersect_lines(right, top),
         _intersect_lines(right, bottom), _intersect_lines(left, bottom)], np.float32,
    )
    height, width = frame.shape[:2]
    if (
        not np.isfinite(corners).all() or not cv2.isContourConvex(corners)
        or cv2.contourArea(corners, oriented=True) < height * width * 0.1
        or (corners < 2).any() or (corners[:, 0] >= width - 2).any()
        or (corners[:, 1] >= height - 2).any()
    ):
        return None
    return corners


def _connected_division(
    rectified: Frame, *, diagnostics: dict[str, str] | None = None,
) -> tuple[float, float] | None:
    """Prefer upper-to-lower border support over shorter layout hypotheses.

    When spanning borders are absent, retain the measured field/grid or menu
    fits. No screen title or prior screen selects a path. Conflicting spanning
    fits are rejected; neither method can invent an unobserved border.
    """
    persistent = _connected_border_divisions(rectified)
    if persistent and np.ptp(np.array(persistent), axis=0).max() > rectified.shape[1] * 0.025:
        return None
    persistent_fit = np.median(persistent, axis=0) if persistent else None
    height, width = rectified.shape[:2]
    value = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)[:, :, 2]
    background = float(np.median(value))
    threshold = max(
        70, float(np.percentile(value, 90)), background + max(15, background * 0.25)
    )
    valid = _structure_mask(rectified)
    bright = ((value >= threshold) & (valid > 0)).astype(np.uint8) * 255
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    chroma = rectified[:, :, 0].astype(np.float32) - rectified[:, :, 1].astype(np.float32)
    chroma = cv2.GaussianBlur(chroma, (5, 5), 1)
    gradient = cv2.Sobel(chroma, cv2.CV_32F, 1, 0) * valid
    border_signal = (chroma - cv2.blur(chroma, (17, 1))) * valid
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if (
            not 0.3 * width < x < 0.68 * width or x + w < 0.9 * width
            or not 0.25 * width < w < 0.7 * width or y + h > 0.4 * height
            or not 0.035 * height < h < 0.22 * height or w < h * 3
            or cv2.contourArea(contour) < w * h * 0.7
        ):
            continue
        lower_start = round(max(0.48 * height, y + h + 0.1 * height))
        lower = gradient[lower_start:round(0.94 * height)]
        profile = np.mean(np.abs(lower), axis=0)
        noise = float(np.median(profile))
        search = max(4, round(w * 0.045))
        borders = []
        for hypothesis in (x, x + w / 3, x + 2 * w / 3):
            low, high = round(hypothesis) - search, round(hypothesis) + search + 1
            peak = low + int(np.argmax(profile[low:high]))
            if profile[peak] < max(2.0, noise * 1.8):
                break
            borders.append(peak)
        if len(borders) != 3:
            continue
        if abs((borders[1] - borders[0]) - (borders[2] - borders[1])) > w * 0.08:
            continue
        # Fit the division using separated lower-row evidence plus the field edge;
        # do not extrapolate a midpoint or publish the field edge by itself.
        ys, xs = [float(y + h / 2)], [float(x)]
        # Locate the blue line's center, rather than either of its two gradient
        # edges. This matters when fitting and extrapolating a thin sloping line.
        lower_signal = border_signal[lower_start:round(0.94 * height)]
        signal_profile = lower_signal.mean(axis=0)
        left = x - search + int(np.argmax(signal_profile[x - search:x + search + 1]))
        local_search = max(2, round(w * 0.008))
        consumed_rows = 0
        for rows in np.array_split(lower_signal, 5):
            local_profile = rows.mean(axis=0)
            low, high = left - local_search, left + local_search + 1
            peak = low + int(np.argmax(local_profile[low:high]))
            if local_profile[peak] >= max(0.75, float(np.median(np.abs(local_profile))) * 2.5):
                ys.append(lower_start + consumed_rows + len(rows) / 2)
                xs.append(float(peak))
            consumed_rows += len(rows)
        if len(xs) < 4:
            continue
        fit = _robust_linear_fit(np.array(ys), np.array(xs))
        if np.max(np.abs(np.array(xs) - np.polyval(fit, ys))) > width * 0.015:
            continue
        top_x, bottom_x = float(np.polyval(fit, 0)), float(np.polyval(fit, height - 1))
        if (
            abs(top_x - bottom_x) <= width * 0.035
            and 0.3 * width < min(top_x, bottom_x)
            and max(top_x, bottom_x) < 0.7 * width
        ):
            candidates.append((top_x, bottom_x))
    field_candidates = len(candidates)
    candidates.extend(_connected_menu_divisions(gradient, rectified))
    legacy_valid = bool(candidates) and np.ptp(np.array(candidates), axis=0).max() <= width * 0.025
    legacy_fit = np.median(candidates, axis=0) if legacy_valid else None
    # Preserve a compatible current-image placement instead of introducing
    # subpixel crop/OCR churn merely because another border method is available.
    # A materially different spanning fit takes precedence over shorter layouts.
    if persistent_fit is not None and (legacy_fit is None or
            np.max(np.abs(persistent_fit - legacy_fit)) > width * 0.005):
        if diagnostics is not None:
            diagnostics["division_basis"] = "spanning_borders"
        return float(persistent_fit[0]), float(persistent_fit[1])
    if legacy_fit is None:
        return None
    if diagnostics is not None:
        diagnostics["division_basis"] = "field_grid" if field_candidates else "menu"
    top_x, bottom_x = legacy_fit
    return float(top_x), float(bottom_x)


def _connected_border_divisions(rectified: Frame) -> list[tuple[float, float]]:
    """Fit aligned border segments spanning independently bordered UI areas.

    Upper and lower evidence must both be present now. No title, field type,
    grid count or previous screen determines the division.
    """
    height, width = rectified.shape[:2]
    chroma = rectified[:, :, 0].astype(np.float32) - rectified[:, :, 1].astype(np.float32)
    gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY).astype(np.float32)
    signals = [cv2.GaussianBlur(channel, (5, 5), 1) for channel in (chroma, gray)]
    gx = np.maximum.reduce([np.abs(cv2.Sobel(channel, cv2.CV_32F, 1, 0))
                            for channel in signals])
    gy = np.maximum.reduce([np.abs(cv2.Sobel(channel, cv2.CV_32F, 0, 1))
                            for channel in signals])
    valid = _structure_mask(rectified)
    gx *= valid
    gy *= valid
    threshold = max(12.0, float(np.median(gx)) * 6)
    vertical = (gx > threshold).astype(np.uint8) * 255
    vertical = cv2.morphologyEx(
        vertical, cv2.MORPH_OPEN, np.ones((max(9, round(height * 0.035)), 1), np.uint8),
    )
    contours, _ = cv2.findContours(vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hypotheses = sorted({round(x + w / 2) for contour in contours
                         for x, y, w, h in [cv2.boundingRect(contour)]
                         if 0.3 * width < x < 0.68 * width and w < width * 0.025})
    candidates = []
    horizontal_threshold = max(8.0, float(np.median(gy)) * 6)
    for x in hypotheses:
        columns = np.arange(max(0, x - 5), min(width, x + 6))
        local = gx[:, columns]
        peaks = local.argmax(axis=1)
        row_noise = np.median(gx[:, max(0, x - 20):min(width, x + 21)], axis=1)
        supported = local[np.arange(height), peaks] > np.maximum(threshold, row_noise * 2.5)
        rows = np.flatnonzero(supported)
        groups = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
        segments = [group for group in groups if len(group) >= height * 0.045]
        if not segments:
            continue
        # Each segment must connect to measured horizontal borders extending
        # into the right-hand region; isolated glyph strokes cannot establish it.
        bordered = []
        reach = max(12, round(width * 0.08))
        horizontal = (gy[:, x + 5:min(width, x + reach)] > horizontal_threshold).mean(axis=1)
        junction_span = max(7, round(height * 0.035))
        for segment in segments:
            span = 7 if segment[0] < height * 0.1 else junction_span
            junctions = []
            for edge in (segment[0], segment[-1]):
                low, high = max(0, edge - span), min(height, edge + span + 1)
                rows = np.flatnonzero(horizontal[low:high] > 0.6) + low
                if len(rows):
                    junctions.append(int(rows[np.argmin(np.abs(rows - edge))]))
            if (len(junctions) == 2 and junctions[1] > junctions[0]
                    and supported[junctions[0]:junctions[1] + 1].mean() >= 0.8):
                bordered.append(segment)
        if (not bordered or bordered[0][0] > height * 0.1
                or bordered[-1][-1] < height * 0.82
                or sum(map(len, bordered)) < height * 0.23):
            continue
        ys = np.concatenate(bordered)
        weights = np.maximum(local - threshold, 0)
        centers = np.divide(weights @ columns, weights.sum(axis=1),
                            out=np.full(height, float(x)), where=weights.sum(axis=1) > 0)
        xs = centers[ys]
        fit = _robust_linear_fit(ys, xs)
        if any(np.mean(np.abs(centers[segment] - np.polyval(fit, segment)) < 3) < 0.85
               for segment in bordered):
            continue
        top, bottom = float(np.polyval(fit, 0)), float(np.polyval(fit, height - 1))
        if abs(top - bottom) < width * 0.035:
            candidates.append((top, bottom))
    return candidates


def _connected_menu_divisions(
    gradient_x: NDArray[np.float32], rectified: Frame,
) -> list[tuple[float, float]]:
    """Require two measured columns and at least three bordered menu rows.

    This is structure evidence only, not screen recognition. Both column edges
    and each horizontal row must be observed; no field or title is required.
    """
    height, width = rectified.shape[:2]
    chroma = rectified[:, :, 0].astype(np.float32) - rectified[:, :, 1].astype(np.float32)
    gradient_y = (cv2.Sobel(cv2.GaussianBlur(chroma, (5, 5), 1), cv2.CV_32F, 0, 1)
                  * _structure_mask(rectified))
    profile = np.abs(gradient_x[round(height * 0.1):round(height * 0.7)]).mean(axis=0)
    noise = float(np.median(profile))
    peaks = np.flatnonzero((profile > np.roll(profile, 1)) & (profile >= np.roll(profile, -1))
                           & (profile > max(4.0, noise * 2.5)))
    candidates = []
    for x in peaks:
        # Validate the two resulting portrait regions independently after the
        # border-supported division, rather than rejecting a valid partner here.
        if not 0.3 * width < x < 0.68 * width:
            continue
        half_width = (width - 1 - x) / 2
        search = max(4, round(half_width * 0.08))
        middle = round(x + half_width)
        middle = middle - search + int(np.argmax(profile[middle - search:middle + search + 1]))
        if profile[middle] < max(4.0, noise * 2.5):
            continue
        region = np.abs(gradient_y[:, x + 4:round(width * 0.98)])
        coverage = (region > max(2.0, float(np.median(region)) * 3)).mean(axis=1)
        supported = np.flatnonzero((coverage > 0.88)
                                   & (np.arange(height) > 0.07 * height)
                                   & (np.arange(height) < 0.72 * height))
        groups = np.split(supported, np.flatnonzero(np.diff(supported) > 1) + 1)
        rows = [int(group[np.argmax(coverage[group])]) for group in groups if len(group)]
        best = []
        for first, second in zip(rows, rows[1:]):
            spacing = second - first
            if not 0.07 * height < spacing < 0.18 * height:
                continue
            chain = [first, second]
            for row in rows:
                if row > chain[-1] and abs(row - chain[-1] - spacing) < spacing * 0.2:
                    chain.append(row)
            if len(chain) > len(best):
                best = chain
        if len(best) < 4:
            continue
        # Row endpoints alone can produce a column peak. Require each vertical
        # edge to persist between the observed rows as well as at intersections.
        menu_edges = np.abs(gradient_x[best[0]:best[-1], x:round(width * 0.98)])
        threshold = max(2.0, float(np.median(menu_edges)) * 2.5)
        if any(np.mean(np.abs(gradient_x[best[0]:best[-1], column - 3:column + 4]).max(axis=1)
                       > threshold) < 0.6 for column in (x, middle)):
            continue
        xs, ys = [], []
        columns = np.arange(max(0, x - 5), min(width, x + 6))
        for top, bottom in zip(best, best[1:]):
            local = np.abs(gradient_x[top + 3:bottom - 3, columns]).mean(axis=0)
            weights = np.maximum(local - noise, 0)
            if weights.sum() > 0:
                xs.append(float(np.dot(columns, weights) / weights.sum()))
                ys.append((top + bottom) / 2)
        if len(xs) < 3:
            continue
        fit = _robust_linear_fit(np.array(ys), np.array(xs))
        top_x, bottom_x = float(np.polyval(fit, 0)), float(np.polyval(fit, height - 1))
        if (max(abs(np.array(xs) - np.polyval(fit, ys))) < width * 0.012
                and abs(top_x - bottom_x) < width * 0.035):
            candidates.append((top_x, bottom_x))
    return candidates


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
    oriented_box = _fit_oriented_box(points)
    if not _valid_geometry(oriented_box, frame_shape):
        return None
    if not _valid_geometry(corners, frame_shape):
        # Weak blue evidence near a pale header can make the fitted top
        # boundaries cross. The detected outer rectangle is still usable.
        corners = oriented_box.copy()
    bounding_box = _fit_axis_aligned_box(
        left_x, right_x, top_y, bottom_y, frame_shape
    )
    if bounding_box is None:
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
    if not cv2.isContourConvex(corners) or cv2.contourArea(corners, oriented=True) <= 0:
        return False
    top_width = np.linalg.norm(corners[1] - corners[0])
    bottom_width = np.linalg.norm(corners[2] - corners[3])
    if top_width < bottom_width * 0.45 or bottom_width < top_width * 0.45:
        return False
    left_height = np.linalg.norm(corners[3] - corners[0])
    right_height = np.linalg.norm(corners[2] - corners[1])
    mean_width = (top_width + bottom_width) / 2
    mean_height = (left_height + right_height) / 2
    return bool(area >= height * width * 0.1 and mean_height > mean_width * 1.2)


def _odd_kernel_size(value: float, minimum: int) -> int:
    size = max(minimum, int(round(value)))
    return size if size % 2 else size + 1
