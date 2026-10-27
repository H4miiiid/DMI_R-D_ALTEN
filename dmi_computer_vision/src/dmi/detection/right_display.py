"""Recognition of right-display state and visible UI elements."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry, Frame, rectify_display
from dmi_computer_vision.src.dmi.detection.title_ocr import read_field, read_title, read_titles, title_state
from dmi_computer_vision.src.dmi.detection.train_controls import train_button_cells
from dmi_computer_vision.src.dmi.detection.visibility import right_display_obstructed
from dmi_computer_vision.src.dmi.detection.right_layout import (
    detect_border_lines,
    detect_button_quads,
    detect_title_quad,
    field_quad_from_contour,
)

RECTIFIED_SIZE = (600, 960)


def analyze_right_display(
    frame: Frame, geometry: DisplayGeometry, state_hint: str | None = None,
    *, connected: bool = False,
) -> dict[str, Any]:
    """Recognize the visible right-display structure and original-frame boxes."""
    rectified = rectify_display(frame, geometry, RECTIFIED_SIZE)
    if right_display_obstructed(rectified, train_workflow=state_hint is not None):
        return {"state": "unknown", "title": None, "buttons": {},
                "data_field": None, "visibility": "occluded"}
    page_one = connected and state_hint == "Train Data (1/2)"
    page_two = connected and state_hint == "Train Data (2/2)"
    numbered_page = page_one or page_two
    border_lines = ([], []) if numbered_page else detect_border_lines(rectified)
    field_detection = None if numbered_page else _detect_data_field(rectified)
    field_box = field_detection[0] if field_detection is not None else None
    # Train workflow titles belong to the left display. Pale summary rows on
    # the right can otherwise be mistaken for a right-hand title band.
    title_box = (_detect_title_box(rectified, field_box)
                 if state_hint is None else None)
    title_crop = _title_crop(frame, geometry, title_box)
    title_text = (read_title(title_crop, (0, 0, title_crop.shape[1], title_crop.shape[0]))
                  if title_crop is not None else None)
    state = title_state(title_text)
    upper_title_used = False
    if state == "unknown" and state_hint is None:
        # An active-area crop can put the title above the legacy bezel band.
        # Search above the observed field, without using a field to infer state.
        upper_title = _detect_title_box(rectified, field_box, upper=True)
        if upper_title is not None and upper_title != title_box:
            crop = _title_crop(frame, geometry, upper_title)
            text = read_title(crop, (0, 0, crop.shape[1], crop.shape[0]))
            if title_state(text) != "unknown":
                title_box, title_text, state = upper_title, text, title_state(text)
                upper_title_used = True
    if state == "unknown" and state_hint is not None:
        state = state_hint
    title = None
    if title_box is not None:
        x1, y1, x2, y2 = title_box
        title_quad = (np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)
                      if upper_title_used else detect_title_quad(rectified, title_box))
        title = _region_result(
            title_quad,
            geometry,
            frame.shape[:2],
        )
        corners = np.asarray(title["corners"], dtype=np.float32)
        if cv2.isContourConvex(corners) and cv2.contourArea(corners) > 0:
            title["text"] = title_text
        else:
            # Occluded border fits can cross; do not publish invented geometry.
            title = None

    data_field = None
    if state == "Train Data":
        field_detection = _detect_train_field(rectified)
        field_box = field_detection[0] if field_detection is not None else None
    if field_box is not None and state not in {"Train Data (1/2)", "Train Data (2/2)"}:
        field_image = _crop_box(rectified, field_box)
        value = None
        if state in {"Driver ID", "Level", "Train Running Number"}:
            digits = _read_digits(field_image, last_only=state == "Level")
            value = (f"Level {digits}" if digits else None) if state == "Level" else digits
        elif state in {"Train Data", "Validate Train Data"}:
            x1, y1, x2, y2 = field_box
            inset = round((y2 - y1) * .12)
            if state == "Train Data":
                # Locate the brightness step between the label and value.
                # Including the divider can turn its border into an OCR letter.
                gray = cv2.cvtColor(field_image[inset:-inset], cv2.COLOR_BGR2GRAY)
                profile = np.median(gray, axis=0)
                start, end = round(len(profile) * .45), round(len(profile) * .85)
                contrast = profile[start + 3:end + 3] - profile[start - 3:end - 3]
                divider = start + int(np.argmax(contrast))
                value_box = (x1 + divider + inset, y1 + inset, x2 - inset, y2 - inset)
                if contrast.max() >= 10:
                    label = read_title(rectified, (x1+inset, y1+inset,
                                                  x1+divider-inset, y2-inset))
                    if label == "Train type":
                        value_image = _crop_box(rectified, value_box)
                        gray_value = cv2.cvtColor(value_image, cv2.COLOR_BGR2GRAY)
                        ink = (gray_value < float(np.median(gray_value))-18).astype(np.uint8)
                        _, _, parts, _ = cv2.connectedComponentsWithStats(ink)
                        letters = [p for p in parts[1:] if p[4] >= 10
                                   and gray_value.shape[0]*.15 < p[3] < gray_value.shape[0]*.9]
                        if letters:
                            lo = np.min([p[:2] for p in letters], axis=0)
                            hi = np.max([p[:2]+p[2:4] for p in letters], axis=0)
                            box = (max(0, int(lo[0])-5), max(0, int(lo[1])-5),
                                   min(value_image.shape[1], int(hi[0])+5), min(value_image.shape[0], int(hi[1])+5))
                            value = read_field(value_image, box)
                        if value not in {"Gamma", "Lambda"}:
                            # One bounded retry on the same current value area;
                            # no supplied answer or retained value enters OCR.
                            value = read_field(rectified, value_box)
                        if value not in {"Gamma", "Lambda"}:
                            value = None
            else:
                x2 = x1 + round((x2 - x1) * .33)
                value = read_field(rectified, (x1, y1 + inset, x2, y2 - inset))
            if value is not None:
                value = value.strip(" |") or None
        data_field = _region_result(
            field_quad_from_contour(field_detection[1]),
            geometry,
            frame.shape[:2],
        )
        data_field["value"] = value

    buttons = {}
    if state == "Level":
        level_read_cells = {}
        detected_buttons = detect_button_quads(
            rectified, state, border_lines, level_read_cells=level_read_cells,
        )
        controls = _recognize_level_buttons(rectified, detected_buttons, read_cells=level_read_cells)
    elif state == "Train Data" or numbered_page:
        # Include real source pixels just outside the geometry enclosure so a
        # border clipped by rectification can still be independently measured.
        width, height = RECTIFIED_SIZE
        margin = 32 if numbered_page else 16
        destination = np.float32([[margin, margin], [width-1+margin, margin],
                                  [width-1+margin, height-1+margin], [margin, height-1+margin]])
        expanded = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(geometry.corners, destination),
                                       (width+2*margin, height+2*margin))
        controls = {name: (quad-margin, None)
                    for name, quad in _recognize_train_buttons(
                        expanded, page_one=page_one, page_two=page_two).items()}
    else:
        detected_buttons = (detect_button_quads(rectified, state, border_lines)
                            if state != "unknown" or title_text is not None else {})
        controls = {name: (quad, None) for name, quad in detected_buttons.items()}
    for name, (quad, active) in controls.items():
        buttons[name] = _region_result(quad, geometry, frame.shape[:2])
        if state == "Level":
            buttons[name]["active"] = active
    return {
        "visibility": "clear",
        "state": state,
        "title": title,
        "buttons": buttons,
        "data_field": data_field,
    }


def _detect_train_field(
    frame: Frame,
) -> tuple[tuple[int, int, int, int], NDArray[np.int32]] | None:
    """Measure the two-tone row near the top, including its darker label half."""
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 90), (179, 240, 255))
    mask[round(height*.3):] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > width*.7 and height*.05 < h < height*.2 and cv2.contourArea(contour) > w*h*.8:
            candidates.append(((x, y, x+w, y+h), contour))
    return max(candidates, key=lambda item: cv2.contourArea(item[1])) if candidates else None


def _recognize_train_buttons(
    frame: Frame, *, page_one: bool = False, page_two: bool = False,
) -> dict[str, NDArray]:
    """Read each measured cell; blank/ambiguous/duplicate identities are omitted."""
    result, duplicates, text_rows = {}, set(), []
    identities = {"Gamma": "gamma", "Lambda": "lambda", "Enter data": "enter_data"}
    if page_one:
        identities = {**{str(i): f"digit_{i}" for i in range(10)},
                      "Del": "delete", "Select type": "select_type"}
    elif page_two:
        identities = {"G1": "g1", "GA": "ga", "GB": "gb", "GC": "gc",
                      "Out of GC": "out_of_gc", "Select type": "select_type"}
    words_allowed = set(identities) | {"Select", "type"}
    if page_two:
        words_allowed |= {"Out", "of"}
    for points in train_button_cells(frame, page_one=page_one, page_two=page_two).values():
        size = tuple(max(20, round(np.linalg.norm(points[i]-points[0]))) for i in (1, 3))
        target = np.float32([[0, 0], [size[0]-1, 0], [size[0]-1, size[1]-1], [0, size[1]-1]])
        crop = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(points, target), size)
        iy, ix = round(size[1]*.15), round(size[0]*.1)
        interior = crop[iy:-iy, ix:-ix]
        gray = cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY)
        ink = (gray > float(np.median(gray))+25).astype(np.uint8)*255
        name = _level_action_icon(ink)
        if page_one and _decimal_button(ink):
            name = "decimal"
        if name not in {"close", "decimal"}:
            name = _train_arrow(ink, rounded_tip=page_one or page_two)
        if name is not None:
            if name in result:
                duplicates.add(name)
            result[name] = points
            continue
        # Keep the observed text lines separate for OCR, then join their words.
        present = np.flatnonzero(np.count_nonzero(ink, axis=1) >= 2)
        if not len(present):
            continue
        groups = np.split(present, np.flatnonzero(np.diff(present)>3)+1)
        crops = []
        for group in groups:
            y1, y2 = max(0, int(group[0])-4), min(interior.shape[0], int(group[-1])+5)
            xs = np.flatnonzero(np.any(ink[y1:y2], axis=0))
            if len(xs):
                crops.append(interior[y1:y2, max(0, int(xs[0])-4):min(interior.shape[1], int(xs[-1])+5)])
        text_rows.append((points, crops))
    texts = iter(read_titles([crop for _, crops in text_rows for crop in crops]))
    for points, crops in text_rows:
        words = [next(texts) for _ in crops]
        if page_one or page_two:
            words = [word if word in words_allowed
                     else read_title(crop, (0, 0, crop.shape[1], crop.shape[0]))
                     for word, crop in zip(words, crops)]
        if page_two:
            # Camera blur can make a digit look like a letter. Retry uncertain
            # current glyphs with relative contrast; never alias OCR strings.
            for index, (word, crop) in enumerate(zip(words, crops)):
                if word in words_allowed:
                    continue
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                mask = (gray > float(np.median(gray)) + 25).astype(np.uint8) * 255
                binary = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                words[index] = read_title(binary, (0, 0, binary.shape[1], binary.shape[0]))
                if words[index] not in words_allowed:
                    enlarged = cv2.resize(binary, None, fx=1.5, fy=1.5,
                                          interpolation=cv2.INTER_LINEAR)
                    words[index] = read_title(enlarged, (0, 0, enlarged.shape[1], enlarged.shape[0]))
        name = identities.get(" ".join(words)) if words and all(words) else None
        if name is not None:
            if name in result:
                duplicates.add(name)
            result[name] = points
    return {name: points for name, points in result.items() if name not in duplicates}


def _decimal_button(mask: Frame) -> bool:
    """Require one small, solid, roughly circular current glyph."""
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    parts = [s for s in stats[1:] if s[4] >= 4]
    if len(parts) != 1:
        return False
    _, _, width, height, area = parts[0]
    return bool(2 <= min(width, height) and max(width, height) < min(mask.shape) * .2
                and .5 < width / height < 2 and area >= 8 and area > width * height * .5)


def _train_arrow(mask: Frame, *, rounded_tip: bool = False) -> str | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) > 15]
    if len(contours) != 1:
        return None
    contour = contours[0]
    hull = cv2.convexHull(contour)
    polygon = cv2.approxPolyDP(hull, cv2.arcLength(hull, True)*.06, True).reshape(-1, 2)
    if rounded_tip and len(polygon) == 4:
        lengths = np.linalg.norm(polygon - np.roll(polygon, -1, axis=0), axis=1)
        index = int(lengths.argmin())
        if lengths[index] < np.median(lengths) * .4:
            polygon = np.float32([(polygon[index] + polygon[(index+1) % 4]) / 2,
                                  polygon[(index+2) % 4], polygon[(index+3) % 4]])
    if len(polygon) != 3 or cv2.contourArea(contour) < cv2.contourArea(hull)*.85:
        return None
    x, y, w, h = cv2.boundingRect(polygon)
    if min(w, h) < 12 or not .6 < w/h < 1.5:
        return None
    normalized = (polygon-(x, y))/(w, h)
    left = normalized[:, 0].argmin()
    right = normalized[:, 0].argmax()
    for index, name, base in ((left, "left_arrow", 1.), (right, "right_arrow", 0.)):
        tip = normalized[index]
        others = np.delete(normalized, index, axis=0)
        if abs(tip[1]-.5) < .2 and np.all(abs(others[:, 0]-base) < .2) and np.ptp(others[:, 1]) > .7:
            return name
    return None


def _recognize_level_buttons(
    frame: Frame, cells: dict[str, NDArray], *, read_cells: dict[str, NDArray] | None = None,
) -> dict[str, tuple[NDArray, bool | None]]:
    """Read identities inside measured cells; omit blank/uncertain/duplicate labels."""
    identities = {**{f"LEVEL {i}": f"level_{i}" for i in range(4)},
                  **{name.upper(): name for name in ("pzb", "kvb", "scmt", "lzb", "memor")},
                  "ATC-2": "atc_2", "TBL1+": "tbl1_plus"}
    result, duplicates = {}, set()
    readings = []
    for cell, measured_quad in cells.items():
        # Both quads come from current validated borders. Keep the established
        # reading crop while exporting this cell's more precise outline.
        quad = read_cells[cell] if read_cells is not None else measured_quad
        span = np.linalg.norm(quad[1] - quad[0])
        step = np.linalg.norm(quad[3] - quad[0])
        size = (max(20, round(span)), max(20, round(step)))
        target = np.float32([[0, 0], [size[0]-1, 0], [size[0]-1, size[1]-1], [0, size[1]-1]])
        crop = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(quad, target), size)
        inset_y, inset_x = round(size[1] * .15), round(size[0] * .12)
        interior = crop[inset_y:-inset_y, inset_x:-inset_x]
        gray = cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY)
        # Skip empty slots before OCR; contrast is relative to the local background.
        foreground = (gray > float(np.median(gray)) + 18).astype(np.uint8) * 255
        if cv2.countNonZero(foreground) < 20:
            continue
        name = _level_action_icon(foreground)
        readings.append((name, measured_quad, quad, interior, foreground))
    texts = iter(read_titles([interior for name, _, _, interior, _ in readings if name is None]))
    for name, measured_quad, quad, interior, foreground in readings:
        if name is None:
            text = next(texts)
            name = identities.get(" ".join((text or "").upper().split()))
        if name is None:
            text = read_title(interior, (0, 0, interior.shape[1], interior.shape[0]))
            normalized = " ".join((text or "").upper().split())
            name = identities.get(normalized)
            if name is None:
                # Relative contrast exposes dim disabled-looking labels without
                # lowering OCR confidence or supplying an expected answer.
                text = read_title(cv2.cvtColor(foreground, cv2.COLOR_GRAY2BGR),
                                  (0, 0, foreground.shape[1], foreground.shape[0]))
                name = identities.get(" ".join((text or "").upper().split()))
            if name is None:
                enlarged = cv2.resize(interior, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
                text = read_title(enlarged, (0, 0, enlarged.shape[1], enlarged.shape[0]))
                name = identities.get(" ".join((text or "").upper().split()))
            if name is None:
                # A second perspective resampling can blur small photographed
                # glyphs. Retry the same measured cell in original rectified
                # pixels, retaining OCR's confidence and exact-text requirements.
                low, high = quad.min(axis=0), quad.max(axis=0)
                inset = (high-low) * (.12, .15)
                box = tuple(np.rint(np.r_[low+inset, high-inset]).astype(int))
                original = _crop_box(frame, box)
                if original.size:
                    text = read_title(original, (0, 0, original.shape[1], original.shape[0]))
                    name = identities.get(" ".join((text or "").upper().split()))
        if name is not None:
            if name in result:
                duplicates.add(name)
            result[name] = (measured_quad, _level_button_active(interior, foreground))
    return {name: q for name, q in result.items() if name not in duplicates}


def _level_button_active(interior: Frame, foreground: NDArray) -> bool | None:
    """Separate light enabled glyphs from muted blue glyphs in the current cell.

    Use color proportions rather than brightness so exposure does not assign
    activity. The uncertain band avoids forcing ambiguous styles into a class.
    Identity and position never determine availability.
    """
    pixels = interior[foreground > 0].astype(np.float32)
    if len(pixels) < 20:
        return None
    red_to_blue = float(np.median(pixels[:, 2] / np.maximum(pixels[:, 0], 1)))
    if red_to_blue >= .5:
        return True
    if red_to_blue <= .4:
        return False
    return None


def _level_action_icon(mask: Frame) -> str | None:
    """Recognize an observed cross or three-dot icon, without slot assumptions."""
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    largest = int(stats[1:, cv2.CC_STAT_AREA].max()) if count > 1 else 0
    components = [i for i in range(1, count)
                  if stats[i, cv2.CC_STAT_AREA] >= max(3, largest * .1)]
    if len(components) == 3:
        boxes, points = stats[components], centers[components]
        if (np.ptp(points[:, 1]) < mask.shape[0] * .08
                and np.ptp(points[:, 0]) > mask.shape[1] * .12
                and np.all(boxes[:, 2:4] < min(mask.shape) * .3)
                and np.all(boxes[:, 2] / boxes[:, 3] > .5)
                and np.all(boxes[:, 2] / boxes[:, 3] < 2)):
            return "more"
    if len(components) != 1:
        return None
    ys, xs = np.where(labels == components[0])
    if not len(xs) or np.ptp(xs) < 12 or np.ptp(ys) < 12:
        return None
    x = (xs - xs.min()) / np.ptp(xs)
    y = (ys - ys.min()) / np.ptp(ys)
    diagonal = np.minimum(abs(x-y), abs(x+y-1)) < .2
    if (.65 < np.ptp(xs) / np.ptp(ys) < 1.5 and np.mean(diagonal) > .96
            and np.mean(abs(x-y) < .2) > .4 and np.mean(abs(x+y-1) < .2) > .4):
        return "close"
    return None


def _title_crop(
    frame: Frame, geometry: DisplayGeometry,
    box: tuple[int, int, int, int] | None,
) -> Frame | None:
    """Read beyond the estimated left edge so rectification cannot cut letters."""
    if box is None:
        return None
    x1, y1, x2, y2 = box
    margin = round(RECTIFIED_SIZE[0] * .04)
    x1 -= margin
    x2 += margin
    y1 -= 4
    y2 += 4
    source = _map_quad(np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
                                dtype=np.float32), geometry)
    width, height = x2 - x1, y2 - y1
    destination = np.array([[0, 0], [width-1, 0], [width-1, height-1],
                            [0, height-1]], np.float32)
    transform = cv2.getPerspectiveTransform(source, destination)
    return cv2.warpPerspective(frame, transform, (width, height))


def _detect_title_box(
    frame: Frame, field_box: tuple[int, int, int, int] | None = None,
    *, upper: bool = False,
) -> tuple[int, int, int, int] | None:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    width, height = RECTIFIED_SIZE
    search_y1, search_y2 = round(height * 0.07), round(height * 0.19)
    if upper:
        search_y1, search_y2 = round(height * 0.02), round(height * 0.12)
    if field_box is not None:
        search_y2 = min(search_y2, field_box[1] - 5)
    mask = cv2.inRange(
        hsv[search_y1:search_y2, : round(width * 0.55)],
        (0, 0, 75),
        (179, 170 if upper else 120, 255),
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = [
        stats[index]
        for index in range(1, count)
        if stats[index, cv2.CC_STAT_AREA] >= 15
        and stats[index, cv2.CC_STAT_HEIGHT] >= 8
    ]
    if not components:
        return None
    x1 = min(int(item[cv2.CC_STAT_LEFT]) for item in components)
    y1 = min(int(item[cv2.CC_STAT_TOP]) for item in components) + search_y1
    x2 = max(
        int(item[cv2.CC_STAT_LEFT] + item[cv2.CC_STAT_WIDTH])
        for item in components
    )
    y2 = max(
        int(item[cv2.CC_STAT_TOP] + item[cv2.CC_STAT_HEIGHT])
        for item in components
    ) + search_y1
    return max(0, x1 - 5), max(0, y1 - 5), min(width - 1, x2 + 5), min(height - 1, y2 + 5)


def _detect_data_field(
    frame: Frame,
) -> tuple[tuple[int, int, int, int], NDArray[np.int32]] | None:
    width, height = RECTIFIED_SIZE
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 90), (179, 110, 255))
    mask[: round(height * 0.1)] = 0
    mask[round(height * 0.44) :] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[tuple[int, int, int, int], NDArray[np.int32]]] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if box_width >= width * 0.7 and box_height >= height * 0.05:
            candidates.append(
                ((x, y, x + box_width, y + box_height), contour)
            )
    if not candidates:
        # A cool camera white balance can make the pale input field cyan.
        # Retry only when the accepted neutral-field search found nothing.
        mask = cv2.inRange(hsv, (0, 0, 120), (179, 190, 255))
        mask[:round(height * 0.1)] = 0
        mask[round(height * 0.44):] = 0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            if (box_width >= width * .7 and height * .05 <= box_height <= height * .2
                    and cv2.contourArea(contour) >= box_width * box_height * .8):
                candidates.append(((x, y, x + box_width, y + box_height), contour))
        if not candidates:
            return None
    return max(
        candidates,
        key=lambda item: (item[0][2] - item[0][0]) * (item[0][3] - item[0][1]),
    )


def _region_result(
    quad: NDArray[np.float32],
    geometry: DisplayGeometry,
    frame_shape: tuple[int, int],
) -> dict[str, list[int] | list[list[int]]]:
    mapped = _map_quad(quad, geometry)
    frame_height, frame_width = frame_shape
    mapped[:, 0] = np.clip(mapped[:, 0], 0, frame_width - 1)
    mapped[:, 1] = np.clip(mapped[:, 1], 0, frame_height - 1)
    rounded = np.rint(mapped).astype(int)
    bbox = [
        int(np.floor(mapped[:, 0].min())),
        int(np.floor(mapped[:, 1].min())),
        int(np.ceil(mapped[:, 0].max())),
        int(np.ceil(mapped[:, 1].max())),
    ]
    center = np.rint(mapped.mean(axis=0)).astype(int).tolist()
    return {"corners": rounded.tolist(), "bbox": bbox, "center": center}


def _map_quad(
    quad: NDArray[np.float32], geometry: DisplayGeometry
) -> NDArray[np.float32]:
    width, height = RECTIFIED_SIZE
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    inverse = cv2.getPerspectiveTransform(destination, geometry.corners)
    return cv2.perspectiveTransform(quad.reshape(1, 4, 2), inverse)[0]


def _crop_box(frame: Frame, box: tuple[int, int, int, int]) -> Frame:
    x1, y1, x2, y2 = box
    return frame[y1:y2, x1:x2]


def _read_digits(field: Frame, *, last_only: bool) -> str | None:
    gray = cv2.cvtColor(field, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, 0, 200)
    value = _digits_from_mask(mask, last_only=last_only)
    if value is not None:
        return value
    if float(np.median(gray)) > 200:
        # An absolute mask is meaningful on a bright field. Faint legacy text
        # needs independent OCR agreement, not a relaxed template decision.
        value = _confirmed_bright_digits(field, mask, last_only=last_only)
        if value is not None:
            return value
    # Remove slow illumination gradients and encoded display texture before
    # extracting dark glyphs in a dim/cyan field. Keep the same digit matcher.
    inset = max(2, round(gray.shape[0] * .1))
    interior = gray[inset:-inset, inset:-inset]
    if interior.size == 0:
        return None
    interior = cv2.medianBlur(interior, 5)
    size = max(15, round(gray.shape[0] * .3) | 1)
    contrast = cv2.morphologyEx(interior, cv2.MORPH_BLACKHAT, np.ones((size, size), np.uint8))
    _, mask = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _digits_from_mask(mask, last_only=last_only)


def _confirmed_bright_digits(field: Frame, mask: Frame, *, last_only: bool) -> str | None:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    glyph_mask = np.zeros_like(mask)
    boxes = []
    for index in range(1, count):
        x, y, width, height, area = map(int, stats[index])
        if area < 30 or height < 12 or width < 3 or height > 60:
            continue
        if width > 50 or width > height:
            return None
        glyph_mask[labels == index] = 255
        boxes.append((x, y, x + width, y + height))
    if not boxes:
        return None
    # This weak proposal is never published on its own. The existing general
    # OCR reader must independently recognize exactly the same complete value.
    proposal = _digits_from_mask(glyph_mask, last_only=last_only,
                                minimum_score=.3, minimum_margin=0.)
    if proposal is None:
        return None
    x1 = max(0, min(box[0] for box in boxes) - 4)
    y1 = max(0, min(box[1] for box in boxes) - 4)
    x2 = min(field.shape[1], max(box[2] for box in boxes) + 4)
    y2 = min(field.shape[0], max(box[3] for box in boxes) + 4)
    text = read_field(field, (x1, y1, x2, y2))
    if last_only and text:
        text = text[-1]
    return proposal if text == proposal else None


def _digits_from_mask(
    mask: Frame, *, last_only: bool, minimum_score: float = .6, minimum_margin: float = .05,
) -> str | None:
    # A field background selected by an absolute threshold is not glyph evidence.
    if np.mean(mask > 0) > .2:
        return None
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    characters: list[tuple[int, int, int, str, float, float]] = []
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        if not last_only and area >= 30 and height >= 12 and (width > 50 or height > 60):
            return None
        if not (3 <= width <= 50 and 12 <= height <= 60 and area >= 30):
            continue
        glyph = (labels[y : y + height, x : x + width] == index).astype(np.uint8) * 255
        normalized = _normalize_glyph(glyph)
        scores = {
            digit: max(_correlation(normalized, template) for template in variants)
            for digit, variants in _digit_templates().items()
        }
        ordered = sorted(scores, key=scores.get, reverse=True)
        digit = ordered[0]
        # Retain uncertain candidates until whole-value validation. Dropping
        # one glyph would turn a multi-digit value into a plausible partial value.
        characters.append((int(x), int(y), int(height), digit, scores[digit],
                           scores[digit] - scores[ordered[1]] if width <= height else -1.0))
    if not characters:
        return None
    characters.sort()
    if last_only:
        characters = characters[-1:]
    if any(score < minimum_score or margin < minimum_margin
           for _, _, _, _, score, margin in characters):
        return None
    tops = [y for _, y, _, _, _, _ in characters]
    heights = [height for _, _, height, _, _, _ in characters]
    if max(tops) - min(tops) > max(heights) * .3 or min(heights) < max(heights) * .65:
        return None
    return "".join(digit for _, _, _, digit, _, _ in characters)


@lru_cache(maxsize=1)
def _digit_templates() -> dict[str, list[NDArray[np.float32]]]:
    templates = {str(digit): [] for digit in range(10)}
    for digit, variants in templates.items():
        fonts = (
            cv2.FONT_HERSHEY_SIMPLEX,
            cv2.FONT_HERSHEY_DUPLEX,
            cv2.FONT_HERSHEY_TRIPLEX,
        )
        for font in fonts:
            for thickness in (1, 2, 3):
                image = np.zeros((70, 60), dtype=np.uint8)
                cv2.putText(image, digit, (5, 55), font, 1.7, 255, thickness, cv2.LINE_AA)
                variants.append(_normalize_glyph(image))
    return templates


def _normalize_glyph(mask: NDArray[np.uint8]) -> NDArray[np.float32]:
    rows, columns = np.where(mask > 0)
    crop = mask[rows.min() : rows.max() + 1, columns.min() : columns.max() + 1]
    scale = min(26 / crop.shape[1], 42 / crop.shape[0])
    resized = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    canvas = np.zeros((48, 32), dtype=np.float32)
    y = (48 - resized.shape[0]) // 2
    x = (32 - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized / 255
    return canvas


def _correlation(first: NDArray[np.float32], second: NDArray[np.float32]) -> float:
    value = np.corrcoef(first.ravel(), second.ravel())[0, 1]
    return float(value) if np.isfinite(value) else -1.0
