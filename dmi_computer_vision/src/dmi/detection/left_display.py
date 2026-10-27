"""Left-display structural localization, independent of the frame source."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry, Frame, rectify_display
from dmi_computer_vision.src.dmi.detection.left_layout import (
    BorderEvidence,
    Line,
    consistent_sidebar,
    position,
    quad,
    sidebar_borders,
    valid_quad,
)
from dmi_computer_vision.src.dmi.temporal.left_tracking import LeftDisplayStabilizer
from dmi_computer_vision.src.dmi.detection.right_layout import field_quad_from_contour
from dmi_computer_vision.src.dmi.detection.icons import recognize_icons
from dmi_computer_vision.src.dmi.detection.title_ocr import read_field, read_light_title, read_title, title_state

RECTIFIED_SIZE = (800, 1280)


def analyze_train_left_display(
    rectified: Frame, geometry: DisplayGeometry, *, connected: bool = False,
) -> tuple[str, dict[str, Any]] | None:
    """Read the left title and bordered confirmation control in train workflows."""
    width, height = RECTIFIED_SIZE
    gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
    header = gray[round(height * .03):round(height * .16), round(width * .5):]
    if cv2.countNonZero((header > 130).astype(np.uint8)) < 800:
        return None
    title_mask = (gray[:round(height * .19), round(width * .25):] > 130).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(title_mask)
    glyphs = [stats[index] for index in range(1, count)
              if stats[index, cv2.CC_STAT_AREA] >= 20
              and 10 <= stats[index, cv2.CC_STAT_HEIGHT] <= height * .07
              and not (connected and stats[index, cv2.CC_STAT_WIDTH] <= 3
                       and stats[index, cv2.CC_STAT_LEFT] + stats[index, cv2.CC_STAT_WIDTH]
                       == title_mask.shape[1])]
    if glyphs:
        # A title is a text row. Gauge ticks/numbers form an arc and used to
        # trigger every expensive OCR retry on the connected active-area crop.
        # Check the current image on every pass; no cached identity is reused.
        centers = np.array([item[cv2.CC_STAT_TOP] + item[cv2.CC_STAT_HEIGHT] / 2
                            for item in glyphs])
        text_height = float(np.median([item[cv2.CC_STAT_HEIGHT] for item in glyphs]))
        if np.percentile(centers, 90) - np.percentile(centers, 10) > text_height:
            return None
    if glyphs:
        x1 = min(int(item[cv2.CC_STAT_LEFT]) for item in glyphs) + round(width * .25)
        x2 = max(int(item[cv2.CC_STAT_LEFT] + item[cv2.CC_STAT_WIDTH])
                 for item in glyphs) + round(width * .25)
        y1 = min(int(item[cv2.CC_STAT_TOP]) for item in glyphs)
        y2 = max(int(item[cv2.CC_STAT_TOP] + item[cv2.CC_STAT_HEIGHT]) for item in glyphs)
        title_box = (max(0, x1 - 15), max(0, y1 - 15),
                     min(width, x2 + 15), min(height, y2 + 15))
    else:
        title_box = (round(width * .25), round(height * .025),
                     width, round(height * .18))
    if glyphs:
        # A bright split border beside the last letter is not a title glyph.
        # Bound the OCR margin by observed tall, narrow components.
        separators = [item for item in stats[1:]
                      if item[cv2.CC_STAT_HEIGHT] > height * .07
                      and item[cv2.CC_STAT_WIDTH] < text_height * .4
                      and item[cv2.CC_STAT_LEFT] + round(width*.25) >= x2]
        if separators:
            edge = min(int(item[cv2.CC_STAT_LEFT]) + round(width*.25)
                       for item in separators)
            title_box = (*title_box[:2], min(title_box[2], edge), title_box[3])
    text = read_title(rectified, title_box)
    state = title_state(text)
    if state == "unknown" and glyphs:
        text = read_light_title(rectified, (x1, y1, x2, y2))
        state = title_state(text)
    if state == "unknown" and glyphs:
        title_box = (round(width * .25), round(height * .025),
                     width, round(height * .18))
        text = read_title(rectified, title_box)
        state = title_state(text)
    if connected and state in {"unknown", "Train Data"}:
        page_title = _read_numbered_train_title(rectified)
        if page_title is not None:
            title_box, text = page_title
            if text is None:
                # Extra current title glyphs cannot be discarded to classify
                # a numbered page as the accepted unnumbered choice screen.
                return None
            state = title_state(text)
    if state not in {"Train Data", "Validate Train Data",
                     "Train Data (1/2)", "Train Data (2/2)"}:
        return None
    source = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1],
                       [0, height - 1]], np.float32)
    transform = cv2.getPerspectiveTransform(source, geometry.corners)
    if glyphs:
        title_quad = np.array([[x1 - 6, y1 - 6], [x2 + 6, y1 - 6],
                               [x2 + 6, y2 + 6], [x1 - 6, y2 + 6]], np.float32)
    else:
        x1, y1, x2, y2 = title_box
        title_quad = np.array([[x1, y1], [x2, y1],
                               [x2, y2], [x1, y2]], np.float32)
    title = {**_region_result(title_quad, transform), "text": text}
    buttons = {}
    numbered_page = connected and state in {"Train Data (1/2)", "Train Data (2/2)"}
    if state != "Validate Train Data":
        hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 100), (179, 130, 255))
        mask[:round(height * .75)] = 0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        candidates = [contour for contour in contours
                      if cv2.boundingRect(contour)[2] >= width * .7
                      and cv2.boundingRect(contour)[3] >= height * .04]
        if numbered_page and len(candidates) > 1:
            candidates = []  # Ambiguous completion cells do not establish Yes.
        if candidates:
            box = cv2.boxPoints(cv2.minAreaRect(max(candidates,
                                                    key=cv2.contourArea)))
            ordered = box[np.argsort(box[:, 1])]
            top = ordered[:2][np.argsort(ordered[:2, 0])]
            bottom = ordered[2:][np.argsort(ordered[2:, 0])[::-1]]
            points = np.vstack((top, bottom))
            # Do not name a pale blank rectangle Yes. Other train pages retain
            # their existing path until their separately authorized steps.
            text = "Yes"
            if state == "Train Data" or numbered_page:
                points = field_quad_from_contour(max(candidates, key=cv2.contourArea))
                text = _read_train_completion(
                    rectified, points, local_background=numbered_page)
            if text == "Yes":
                buttons["yes"] = _region_result(points, transform)
    content = {"boxes": {}, "speed_indicator": None, "title": title, "buttons": buttons}
    if state == "Train Data":
        content["summary"] = _read_train_summary(rectified, transform)
    return state, content


def _read_numbered_train_title(frame: Frame) -> tuple[tuple[int, int, int, int], str | None] | None:
    """Retry a complete measured text row when a dim page suffix was clipped.

    Glyph count only proposes OCR. Only an exact current title selects a page.
    The accepted unnumbered Train Data path does not enter this OCR retry.
    """
    width, height = RECTIFIED_SIZE
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = (gray[:round(height * .19), round(width * .25):] > 90).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    glyphs = [g for g in stats[1:] if g[4] >= 20 and 10 <= g[3] < height * .07
              and not (g[0] + g[2] == mask.shape[1] and g[2] <= 3)]
    if len(glyphs) < 12:
        return None
    centers = [g[1] + g[3] / 2 for g in glyphs]
    if np.ptp(centers) > np.median([g[3] for g in glyphs]):
        return None
    low = np.min([g[:2] for g in glyphs], axis=0) + (round(width * .25), 0)
    high = np.max([g[:2] + g[2:4] for g in glyphs], axis=0) + (round(width * .25), 0)
    box = tuple(map(int, np.r_[np.maximum(low - 10, 0), np.minimum(high + 10, (width, height))]))
    text = read_title(frame, box)
    # A measured vertical separator may touch the OCR margin, not the letters.
    text = text.strip(" |") if text else None
    return box, text if title_state(text) in {"Train Data (1/2)", "Train Data (2/2)"} else None


def _read_train_summary(frame: Frame, transform: np.ndarray) -> dict[str, Any]:
    """Measure current summary glyph rows, independently of the right field.

    These are text observations, never button cells or robot targets. Unknown
    or duplicate rows are omitted; no previous value or screen order is used.
    """
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = (gray > max(80, float(np.median(gray)) + 25)).astype(np.uint8)
    mask[:round(height * .16)] = 0
    mask[round(height * .7):] = 0
    _, _, components, _ = cv2.connectedComponentsWithStats(mask)
    glyphs = [item for item in components[1:]
              if item[cv2.CC_STAT_AREA] >= 8
              and 8 < item[cv2.CC_STAT_HEIGHT] < height * .065
              and item[cv2.CC_STAT_WIDTH] < width * .6]
    rows = []
    for glyph in sorted(glyphs, key=lambda item: item[1] + item[3] / 2):
        center = glyph[1] + glyph[3] / 2
        if not rows or center - np.median([g[1] + g[3] / 2 for g in rows[-1]]) > glyph[3] * .5:
            rows.append([])
        rows[-1].append(glyph)
    # More text rows are ambiguous for this single-summary screen. Bound OCR
    # work and fail closed rather than searching an unsupported text page.
    if len(rows) > 4:
        return {}
    result, duplicates = {}, set()
    values = {"train type gamma": "Gamma", "train type lambda": "Lambda"}
    for row in rows:
        left = max(0, min(g[0] for g in row) - 8)
        top = max(0, min(g[1] for g in row) - 8)
        right = min(width, max(g[0] + g[2] for g in row) + 8)
        bottom = min(height, max(g[1] + g[3] for g in row) + 8)
        if right - left < width * .15:
            continue
        text = read_title(frame, (left, top, right, bottom))
        value = values.get(" ".join((text or "").casefold().split()))
        if value is None:
            continue
        name = "train_type"
        if name in result:
            duplicates.add(name)
        points = np.float32([[left, top], [right, top], [right, bottom], [left, bottom]])
        result[name] = {**_region_result(points, transform), "value": value}
    return {name: region for name, region in result.items() if name not in duplicates}


def _read_train_completion(
    frame: Frame, points: np.ndarray, *, local_background: bool = False,
) -> str | None:
    """Read current dark glyphs in a measured, wide pale completion cell."""
    if not valid_quad(points):
        return None
    width = round(np.linalg.norm(points[1] - points[0]))
    height = round(np.linalg.norm(points[3] - points[0]))
    if width < frame.shape[1] * .65 or not frame.shape[0] * .035 < height < frame.shape[0] * .2:
        return None
    target = np.float32([[0, 0], [width - 1, 0],
                         [width - 1, height - 1], [0, height - 1]])
    cell = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(points, target), (width, height))
    inset = max(2, round(height * .15))
    if 2 * inset >= min(width, height) - 4:
        return None
    crop = cell[inset:-inset, inset:-inset]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    background = np.median(gray, axis=0)[None] if local_background else float(np.median(gray))
    ink = (gray < background - 12).astype(np.uint8)
    _, _, components, _ = cv2.connectedComponentsWithStats(ink)
    letters = [item for item in components[1:]
               if item[cv2.CC_STAT_AREA] >= 10
               and crop.shape[0] * .15 < item[cv2.CC_STAT_HEIGHT] < crop.shape[0] * .9]
    if not letters:
        return None
    left = max(0, min(item[0] for item in letters) - 6)
    top = max(0, min(item[1] for item in letters) - 6)
    right = min(crop.shape[1], max(item[0] + item[2] for item in letters) + 6)
    bottom = min(crop.shape[0], max(item[1] + item[3] for item in letters) + 6)
    return read_field(crop, (left, top, right, bottom))


def analyze_left_display(
    frame: Frame,
    geometry: DisplayGeometry,
    stabilizer: LeftDisplayStabilizer | None = None,
    rectified: Frame | None = None,
) -> dict[str, Any]:
    """Locate the 22 logical regions and speed panel using visible borders."""
    if rectified is None:
        rectified = rectify_display(frame, geometry, RECTIFIED_SIZE)
    boxes, speed = detect_left_regions(rectified)
    if stabilizer is not None:
        boxes, speed = stabilizer.update(boxes, speed, rectified)
    boxes = {name: points for name, points in boxes.items() if valid_quad(points)}
    if speed is not None and not valid_quad(speed):
        speed = None
    icons = recognize_icons(rectified, boxes)
    width, height = RECTIFIED_SIZE
    source = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32
    )
    transform = cv2.getPerspectiveTransform(source, geometry.corners)
    return {
        "boxes": {
            name: {**_region_result(points, transform), "icon": icons[name]}
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
        if rows[index] is None:
            continue
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
            if row is None:
                continue
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
    boxes = {f"box_{i+1}": quad(left, divider, rows[i], rows[i + 1]) for i in range(9)
             if rows[i] is not None and rows[i + 1] is not None}
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
                    # Center cells share borders; outer buttons fit their own slopes.
                    x1, x2 = (
                        position(verticals[a], height * 0.65),
                        position(verticals[b], height * 0.65),
                    )
                    if i in (1, 2, 3):
                        local_top, local_bottom = group_top, group_bottom
                    else:
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
