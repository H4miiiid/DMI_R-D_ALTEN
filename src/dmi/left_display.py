"""Left-display structural localization, independent of the frame source."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from dmi.geometry import DisplayGeometry, Frame, rectify_display
from dmi.left_layout import (
    BorderEvidence,
    Line,
    consistent_sidebar,
    position,
    quad,
    sidebar_borders,
    valid_quad,
)
from dmi.left_tracking import LeftDisplayStabilizer

RECTIFIED_SIZE = (800, 1280)


def analyze_left_display(
    frame: Frame,
    geometry: DisplayGeometry,
    stabilizer: LeftDisplayStabilizer | None = None,
) -> dict[str, Any]:
    """Locate the 22 logical regions and speed panel using visible borders."""
    rectified = rectify_display(frame, geometry, RECTIFIED_SIZE)
    boxes, speed = detect_left_regions(rectified)
    if stabilizer is not None:
        boxes, speed = stabilizer.update(boxes, speed, rectified)
    boxes = {name: points for name, points in boxes.items() if valid_quad(points)}
    if speed is not None and not valid_quad(speed):
        speed = None
    width, height = RECTIFIED_SIZE
    source = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32
    )
    transform = cv2.getPerspectiveTransform(source, geometry.corners)
    return {
        "boxes": {
            name: {**_region_result(points, transform), "icon": None}
            for name, points in boxes.items()
        },
        "speed_indicator": _region_result(speed, transform)
        if speed is not None
        else None,
    }


def detect_left_regions(
    frame: Frame,
) -> tuple[dict[str, np.ndarray], np.ndarray | None]:
    """Fit separate local border lines; missing evidence produces omissions."""
    evidence = BorderEvidence(frame)
    sidebar = sidebar_borders(evidence)
    if sidebar is None:
        return {}, None
    divider, rows = sidebar
    height, width = frame.shape[:2]
    left, right = (0.0, 0.0), (0.0, float(width - 1))
    boxes = {}
    sx = position(divider, height / 2)
    step = np.median(np.diff([position(r, sx) for r in rows[2:]]))
    main = {}
    for index in (0, 3, 5, 9):
        line = evidence.fit(
            "h",
            position(rows[index], sx),
            sx,
            sx + width * 0.025,
            width * 0.98,
            radius=8 if index == 0 else 12,
            slope=rows[index][0] if index == 0 else 0,
            slope_radius=0.05 if index == 0 else 0.25,
        )
        if line is not None:
            main[index] = line
    # Shared physical borders use exactly the same fitted line on both sides.
    if len(main) >= 2:
        anchors = sorted((position(line, sx), line[0]) for line in main.values())
        for index, row in enumerate(rows):
            if index in main:
                rows[index] = main[index]
                continue
            y = position(row, sx / 2)
            slope = float(
                np.interp(y, [p[0] for p in anchors], [p[1] for p in anchors])
            )
            refined = evidence.fit(
                "h",
                y,
                sx / 2,
                sx * 0.13,
                sx * 0.82,
                radius=5,
                slope=slope,
                slope_radius=0.015,
            )
            if refined is not None:
                rows[index] = refined
    if not all(consistent_sidebar(rows, x) for x in (0, sx)):
        return {}, None
    # Adjacent long dividers must remain separated across the entire display.
    # A strong noise edge near another row is not a substitute for its border.
    for first, last, units in ((3, 5, 2), (5, 9, 4)):
        if first in main and last in main:
            gaps = [
                position(main[last], x) - position(main[first], x)
                for x in (sx, width - 1)
            ]
            if not all(0.65 * units * step < gap < 1.4 * units * step for gap in gaps):
                return {}, None
    boxes = {f"box_{i+1}": quad(left, divider, rows[i], rows[i + 1]) for i in range(9)}
    speed = quad(divider, right, main[0], main[3]) if 0 in main and 3 in main else None
    if 3 in main and 5 in main:
        verticals = _verticals(
            evidence, main[3], main[5], sx + width * 0.06, width * 0.95, 4
        )
        if len(verticals) == 4:
            boundaries = [divider, *verticals, right]
            for i in range(5):
                boxes[f"box_{15+i}"] = quad(
                    boundaries[i], boundaries[i + 1], main[3], main[5]
                )
    if 3 in main:
        cross = (sx + width) / 2
        top = evidence.fit(
            "h",
            position(main[3], cross) - step * 1.75,
            cross,
            sx + width * 0.04,
            width * 0.97,
            radius=step * 0.32,
            slope=main[3][0],
            slope_radius=0.02,
        )
        bottom = evidence.fit(
            "h",
            position(main[3], cross) - step * 0.3,
            cross,
            sx + width * 0.04,
            width * 0.97,
            radius=step * 0.12,
            slope=main[3][0],
            slope_radius=0.02,
        )
        if top is not None and bottom is not None:
            verticals = _verticals(
                evidence, top, bottom, sx + width * 0.015, width * 0.985, 8
            )
            if len(verticals) == 8:
                # The three adjacent cells share one physical top and bottom.
                group_left = position(verticals[2], height * 0.65)
                group_right = position(verticals[5], height * 0.65)
                group_cross = (group_left + group_right) / 2
                group_top = evidence.fit(
                    "h",
                    position(top, group_cross),
                    group_cross,
                    group_left + 8,
                    group_right - 8,
                    radius=8,
                    slope=top[0],
                    slope_radius=0.04,
                )
                group_bottom = evidence.fit(
                    "h",
                    position(bottom, group_cross),
                    group_cross,
                    group_left + 8,
                    group_right - 8,
                    radius=4,
                    slope=bottom[0],
                    slope_radius=0.04,
                )
                for i, (a, b) in enumerate(((0, 1), (2, 3), (3, 4), (4, 5), (6, 7))):
                    # Each short button gets its own top/bottom slope.
                    x1, x2 = (
                        position(verticals[a], height * 0.65),
                        position(verticals[b], height * 0.65),
                    )
                    local_top = evidence.fit(
                        "h",
                        position(top, (x1 + x2) / 2),
                        (x1 + x2) / 2,
                        x1 + 8,
                        x2 - 8,
                        radius=8,
                        slope=top[0],
                        slope_radius=0.06,
                    )
                    local_bottom = evidence.fit(
                        "h",
                        position(bottom, (x1 + x2) / 2),
                        (x1 + x2) / 2,
                        x1 + 8,
                        x2 - 8,
                        radius=4,
                        slope=bottom[0],
                        slope_radius=0.06,
                    )
                    if i in (1, 2, 3):
                        local_top, local_bottom = group_top, group_bottom
                    if local_top is not None and local_bottom is not None:
                        boxes[f"box_{10+i}"] = quad(
                            verticals[a], verticals[b], local_top, local_bottom
                        )
    if 5 in main and 9 in main:
        verticals = _verticals(
            evidence, main[5], main[9], width * 0.72, width * 0.94, 1
        )
        if verticals:
            scroll = verticals[0]
            x = position(scroll, height * 0.85)
            middle_y = (position(main[5], x) + position(main[9], x)) / 2
            middle = evidence.fit(
                "h",
                middle_y,
                x,
                x + 12,
                width * 0.98,
                radius=step * 0.25,
                slope=(main[5][0] + main[9][0]) / 2,
                slope_radius=0.08,
            )
            boxes["box_20"] = quad(divider, scroll, main[5], main[9])
            if middle is not None:
                boxes["box_21"] = quad(scroll, right, main[5], middle)
                boxes["box_22"] = quad(scroll, right, middle, main[9])
    boxes = {name: points for name, points in boxes.items() if valid_quad(points)}
    if speed is not None and not valid_quad(speed):
        speed = None
    return dict(sorted(boxes.items(), key=lambda item: int(item[0][4:]))), speed


def _verticals(
    evidence: BorderEvidence,
    top: Line,
    bottom: Line,
    start: float,
    end: float,
    count: int,
) -> list[Line]:
    xs = np.arange(round(start), round(end), dtype=np.float32)
    fractions = np.linspace(0.15, 0.85, 40, dtype=np.float32)
    ys = (top[0] * xs + top[1])[None, :] * (1 - fractions[:, None]) + (
        bottom[0] * xs + bottom[1]
    )[None, :] * fractions[:, None]
    values = cv2.remap(
        evidence.vertical.T, np.broadcast_to(xs, ys.shape), ys, cv2.INTER_LINEAR
    )
    scores = np.median(values, axis=0)
    found = []
    for _ in range(count):
        index = int(scores.argmax())
        if scores[index] < 1.2:
            break
        x = float(xs[index])
        y1, y2 = position(top, x), position(bottom, x)
        line = evidence.fit(
            "v",
            x,
            (y1 + y2) / 2,
            y1 + (y2 - y1) * 0.12,
            y2 - (y2 - y1) * 0.12,
            radius=6,
            slope_radius=0.06,
        )
        if line is not None:
            found.append(line)
        scores[max(0, index - 22) : index + 23] = 0
    return sorted(found, key=lambda line: position(line, (top[1] + bottom[1]) / 2))


def _region_result(points: np.ndarray, transform: np.ndarray) -> dict[str, Any]:
    corners = cv2.perspectiveTransform(points[None].astype(np.float32), transform)[0]
    center = cv2.perspectiveTransform(points.mean(axis=0).reshape(1, 1, 2), transform)[
        0, 0
    ]
    return {
        "corners": np.round(corners.astype(np.float64), 2).tolist(),
        "bbox": [
            int(np.floor(corners[:, 0].min())),
            int(np.floor(corners[:, 1].min())),
            int(np.ceil(corners[:, 0].max())),
            int(np.ceil(corners[:, 1].max())),
        ],
        "center": np.round(center.astype(np.float64), 2).tolist(),
    }
