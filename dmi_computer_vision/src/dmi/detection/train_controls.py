"""Current-image cell measurements for the Train Data choice screen."""
from __future__ import annotations

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.left_layout import BorderEvidence, quad, valid_quad
from dmi_computer_vision.src.dmi.detection.right_layout import _border_peaks, _level_edge_supported


def train_button_cells(frame: np.ndarray) -> dict[str, np.ndarray]:
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
    evidence = BorderEvidence(frame)
    cells = []
    for x, y, glyph_width, glyph_height, area in stats[1:]:
        if area < 80 or not (8 < glyph_height < height * .09 and glyph_width > 8):
            continue
        horizontal = np.median(evidence.horizontal[:, x:x + glyph_width], axis=1)
        peaks = _border_peaks(horizontal, separation=8)
        tops = [p for p in peaks if y-height*.13 < p < y-4]
        bottoms = [p for p in peaks if y+glyph_height+4 < p < y+glyph_height+height*.13]
        best = None
        for top in tops:
            for bottom in bottoms:
                step = bottom - top
                if not height*.055 < step < height*.16:
                    continue
                vertical = np.median(evidence.vertical[:, round(top+step*.15):round(bottom-step*.15)], axis=1)
                columns = _border_peaks(vertical, separation=8)
                lefts = [p for p in columns if x+glyph_width/2-width*.22 < p < x-4]
                rights = [p for p in columns if x+glyph_width+4 < p < x+glyph_width/2+width*.22]
                # Border contrast is compared within each side's bounded
                # search. Weak camera-texture peaks cannot shrink a real cell.
                left_floor = max(1.5, max((vertical[p] for p in lefts), default=0)*.3)
                right_floor = max(1.5, max((vertical[p] for p in rights), default=0)*.3)
                for left in lefts:
                    if vertical[left] < left_floor:
                        continue
                    for right in rights:
                        if vertical[right] < right_floor:
                            continue
                        span = right-left
                        if not width*.12 < span < width*.44:
                            continue
                        # The glyph group must occupy the middle of its cell;
                        # this rejects spanning boxes and nearby texture edges.
                        cx, cy = (left+right)/2, (top+bottom)/2
                        if (abs(cx-(x+glyph_width/2)) > span*.2
                                or abs(cy-(y+glyph_height/2)) > step*.2):
                            continue
                        # Prefer the nearest fully supported enclosure, rather
                        # than a larger box reaching the monitor's outer edge.
                        score = -span * step
                        if best is not None and score <= best[0]:
                            continue
                        edges = (
                            evidence.fit('v', left, cy, top+step*.12, bottom-step*.12, radius=8, slope_radius=.06),
                            evidence.fit('v', right, cy, top+step*.12, bottom-step*.12, radius=8, slope_radius=.06),
                            evidence.fit('h', top, cx, left+span*.12, right-span*.12, radius=8, slope_radius=.06),
                            evidence.fit('h', bottom, cx, left+span*.12, right-span*.12, radius=8, slope_radius=.06),
                        )
                        if any(edge is None for edge in edges):
                            continue
                        if not all(_level_edge_supported(evidence, axis, edge, lo, hi)
                                   for axis, edge, lo, hi in (
                                       ('v', edges[0], top, bottom), ('v', edges[1], top, bottom),
                                       ('h', edges[2], left, right), ('h', edges[3], left, right))):
                            continue
                        # A measured internal divider rules out a cell spanning
                        # the real button and the monitor's lower border.
                        local = np.median(evidence.horizontal[:, round(left+span*.12):round(right-span*.12)], axis=1)
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
                            best = score, points
        if best is not None and not any(np.linalg.norm(best[1].mean(axis=0)-q.mean(axis=0)) < 10 for q in cells):
            cells.append(best[1])
    return {f'cell_{i}': q for i, q in enumerate(cells)}
