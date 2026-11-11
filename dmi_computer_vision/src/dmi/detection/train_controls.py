"""Current-image cell measurements for the Train Data choice screen."""
from __future__ import annotations

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.left_layout import BorderEvidence, quad, valid_quad
from dmi_computer_vision.src.dmi.detection.right_layout import (
    _border_peaks, _level_edge_supported, _level_inner_edge,
)


def refine_boundary_cells(
    frame: np.ndarray, cells: dict[str, np.ndarray], bounds: tuple[float, float, float, float],
    *, diagnostics: dict[str, str] | None = None,
) -> dict[str, np.ndarray]:
    """Re-fit small overhangs on current border faces; never clip to an enclosure.

    Bounds describe the independently measured display in this expanded crop.
    One existing eight-pixel cell-border search is allowed. A larger overhang,
    missing border support or a crop that cuts recognized content is rejected.
    The caller applies the existing native-pixel containment check to candidates.
    """
    x1, y1, x2, y2 = bounds
    result, evidence = {}, None
    for name, points in cells.items():
        reason = 'invalid_quad'
        if valid_quad(points):
            overhang = np.array([x1-points[:, 0].min(), points[:, 0].max()-x2,
                                 y1-points[:, 1].min(), points[:, 1].max()-y2])
            if np.max(overhang) <= 0:
                result[name] = points
                reason = 'inside_measured_display'
            elif np.max(overhang) > 8:
                reason = 'overhang_exceeds_existing_refit_radius'
            else:
                if evidence is None:
                    evidence = BorderEvidence(frame, preserve_wide_regions=True)
                edges, spans = [], []
                # Lines use dependent = slope * independent + intercept.
                for a, b, axis in ((0, 3, 'v'), (1, 2, 'v'), (0, 1, 'h'), (3, 2, 'h')):
                    independent, dependent = (1, 0) if axis == 'v' else (0, 1)
                    start, end = float(points[a, independent]), float(points[b, independent])
                    if end <= start:
                        break
                    slope = float((points[b, dependent]-points[a, dependent])/(end-start))
                    edges.append((slope, float(points[a, dependent]-slope*start)))
                    spans.append((start, end))
                if len(edges) != 4:
                    if diagnostics is not None:
                        diagnostics[name] = 'invalid_edge_order'
                    continue
                changed = False
                for index, (axis, positive) in enumerate((('v', True), ('v', False), ('h', True), ('h', False))):
                    if overhang[index] > 0:
                        fitted = _level_inner_edge(evidence, axis, edges[index], *spans[index],
                                                  radius=8, positive=positive, minimum=1.5)
                        changed |= fitted != edges[index]
                        edges[index] = fitted
                refined = quad(*edges)
                reason = 'no_supported_border_face'
                if changed and valid_quad(refined) and np.max(np.abs(refined-points)) <= 8:
                    # Retain the entire interior used for recognition (10% X,
                    # 15% Y inset), not merely a center inside an invented box.
                    core = cv2.perspectiveTransform(np.float32([[[.1, .15], [.9, .15],
                        [.9, .85], [.1, .85]]]), cv2.getPerspectiveTransform(
                            np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), points.astype(np.float32)))[0]
                    supported = all(_level_edge_supported(evidence, axis, edge, *span)
                        for axis, edge, span in zip(('v', 'v', 'h', 'h'), edges, spans))
                    if supported and all(cv2.pointPolygonTest(refined, tuple(map(float, p)), False) >= 0 for p in core):
                        result[name] = refined
                        reason = 'refitted_current_supported_border'
                    else:
                        reason = 'refit_lost_border_or_recognized_interior'
        if diagnostics is not None:
            diagnostics[name] = reason
    return result


def train_button_cells(
    frame: np.ndarray, *, page_one: bool = False, page_two: bool = False,
    validation: bool = False,
    display_bounds: tuple[float, float, float, float] | None = None,
    search_regions: tuple[np.ndarray, ...] | None = None,
) -> dict[str, np.ndarray]:
    """Use glyph groups to propose searches, then require four measured borders.

    Text and icons seed independent cells, never a row of implied partners.
    Searches are bounded by control size; neither order nor location names them.
    """
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    foreground = (gray > float(np.median(gray)) + 25).astype(np.uint8)
    foreground[:round(height * .3)] = 0
    grouped = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, np.ones((25, 15), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(grouped)
    compact_buttons = page_one or page_two or validation
    local_search = page_two or validation
    evidence = BorderEvidence(frame, preserve_wide_regions=compact_buttons)
    cells = []
    for x, y, glyph_width, glyph_height, area in stats[1:]:
        # A retry searches only glyphs within the rejected current measurements.
        # Those quads propose searches; they supply neither final borders nor
        # identities. The same fitting/recognition gates still decide each cell.
        if search_regions is not None and not any(
                cv2.pointPolygonTest(region, (float(x+glyph_width/2), float(y+glyph_height/2)), False) >= 0
                for region in search_regions):
            continue
        minimum = 1 if compact_buttons else 8
        if area < (5 if compact_buttons else 80) or not (minimum < glyph_height < height * .09
                                                 and glyph_width > minimum):
            continue
        if compact_buttons and glyph_width > width * .4:
            continue
        # A decimal glyph alone is too narrow for a robust border profile.
        pad = max(0, round(width * .035 - glyph_width / 2)) if compact_buttons else 0
        horizontal = evidence.profile('h', max(0, x-pad), min(width, x+glyph_width+pad))
        if local_search:
            # Compare dim control edges within the current glyph's bounded
            # search, rather than against the much brighter outer bezel.
            start = max(0, int(y-height*.13))
            end = min(height, int(y+glyph_height+height*.13))
            peaks = [start+p for p in _border_peaks(horizontal[start:end], separation=8)]
        else:
            peaks = _border_peaks(horizontal, separation=8)
        tops = [p for p in peaks if y-height*.13 < p < y-4]
        bottoms = [p for p in peaks if y+glyph_height+4 < p < y+glyph_height+height*.13]
        best = None
        for top in tops:
            for bottom in bottoms:
                step = bottom - top
                if not height*.055 < step < height*.16:
                    continue
                vertical = evidence.profile('v', round(top+step*.15), round(bottom-step*.15))
                if validation:
                    # The bright enclosure outside a sparse button row must
                    # not set the peak threshold for this current glyph's cell.
                    start = max(0, int(x+glyph_width/2-width*.22))
                    end = min(width, int(x+glyph_width/2+width*.22)+1)
                    columns = [start+p for p in _border_peaks(vertical[start:end], separation=8)]
                else:
                    columns = _border_peaks(vertical, separation=8)
                boundary_seeds = set()
                if validation and display_bounds is not None:
                    # The independently measured display edge is an additional
                    # local search seed, even if a weak peak was suppressed.
                    # It supplies no final line: all four fitted borders must
                    # still pass the unchanged image-support checks below.
                    boundary_seeds = {round(display_bounds[0]), round(display_bounds[2])}
                    columns = sorted(set(columns) | boundary_seeds)
                lefts = [p for p in columns if x+glyph_width/2-width*.22 < p < x-4]
                rights = [p for p in columns if x+glyph_width+4 < p < x+glyph_width/2+width*.22]
                # Border contrast is compared within each side's bounded
                # search. Weak camera-texture peaks cannot shrink a real cell.
                # A sparse validation row can have a dim cell outline beside a
                # much brighter division. Keep its measured peak as a proposal;
                # the same distributed/background support gates still decide it.
                ratio = 0 if validation else .3
                left_floor = max(1.5, max((vertical[p] for p in lefts), default=0)*ratio)
                right_floor = max(1.5, max((vertical[p] for p in rights), default=0)*ratio)
                for left in lefts:
                    if vertical[left] < left_floor and left not in boundary_seeds:
                        continue
                    for right in rights:
                        if vertical[right] < right_floor and right not in boundary_seeds:
                            continue
                        span = right-left
                        if not width*.12 < span < width*.44:
                            continue
                        # The glyph group must occupy the middle of its cell;
                        # this rejects spanning boxes and nearby texture edges.
                        cx, cy = (left+right)/2, (top+bottom)/2
                        center_tolerance = .1 if local_search else .2
                        if (abs(cx-(x+glyph_width/2)) > span*center_tolerance
                                or abs(cy-(y+glyph_height/2)) > step*center_tolerance):
                            continue
                        # Prefer the nearest fully supported enclosure, rather
                        # than a larger box reaching the monitor's outer edge.
                        score = -span * step
                        if not validation and best is not None and score <= best[0]:
                            continue
                        edges = (
                            evidence.fit('v', left, cy, top+step*.12, bottom-step*.12, radius=8, slope_radius=.06),
                            evidence.fit('v', right, cy, top+step*.12, bottom-step*.12, radius=8, slope_radius=.06),
                            evidence.fit('h', top, cx, left+span*.12, right-span*.12, radius=8, slope_radius=.06),
                            evidence.fit('h', bottom, cx, left+span*.12, right-span*.12, radius=8, slope_radius=.06),
                        )
                        if any(edge is None for edge in edges):
                            continue
                        if validation:
                            # Reuse measured-face refinement for unsupported
                            # outlines and faces near the independently measured
                            # shared edge. Its support is checked again below.
                            edges = tuple(
                                _level_inner_edge(evidence, axis, edge, lo, hi,
                                    radius=8, positive=positive, minimum=1.5)
                                if (not _level_edge_supported(evidence, axis, edge, lo, hi)
                                    or display_bounds is not None and axis == 'v' and
                                    abs(edge[0]*cy+edge[1]-display_bounds[0 if positive else 2]) <= 8)
                                else edge
                                for axis, edge, lo, hi, positive in (
                                    ('v', edges[0], top, bottom, True),
                                    ('v', edges[1], top, bottom, False),
                                    ('h', edges[2], left, right, True),
                                    ('h', edges[3], left, right, False)))
                        if not all(_level_edge_supported(evidence, axis, edge, lo, hi)
                                   for axis, edge, lo, hi in (
                                       ('v', edges[0], top, bottom), ('v', edges[1], top, bottom),
                                       ('h', edges[2], left, right), ('h', edges[3], left, right))):
                            continue
                        # A measured internal divider rules out a cell spanning
                        # the real button and the monitor's lower border.
                        local = evidence.profile('h', round(left+span*.12), round(right-span*.12))
                        divided = False
                        for row in _border_peaks(local, separation=8):
                            if not top+step*.15 < row < bottom-step*.15:
                                continue
                            line = evidence.fit('h', row, cx, left+span*.12, right-span*.12,
                                                radius=4, slope_radius=.06)
                            if line is not None and _level_edge_supported(evidence, 'h', line, left, right):
                                divided = True
                                break
                        if divided:
                            continue
                        points = quad(*edges)
                        if valid_quad(points):
                            if validation:
                                # Rank the actual fitted enclosure, not its
                                # seed: a weak inner texture edge can otherwise
                                # win simply by making a smaller rectangle.
                                offset = abs(points.mean(0)-(x+glyph_width/2, y+glyph_height/2))/(span, step)
                                if np.any(offset > .1):
                                    continue
                                score = -float(offset.sum())
                                if display_bounds is not None:
                                    x1, y1, x2, y2 = display_bounds
                                    protrusion = max(0., x1-float(points[:, 0].min()),
                                        float(points[:, 0].max())-x2, y1-float(points[:, 1].min()),
                                        float(points[:, 1].max())-y2)
                                    if protrusion > 8:
                                        continue  # Wrong enclosure, beyond the existing local fit radius.
                                if best is not None and score <= best[0]:
                                    continue
                            best = score, points
        if best is not None and not any(np.linalg.norm(best[1].mean(axis=0)-q.mean(axis=0)) < 10 for q in cells):
            cells.append(best[1])
    return {f'cell_{i}': q for i, q in enumerate(cells)}
