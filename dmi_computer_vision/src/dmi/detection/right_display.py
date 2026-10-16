"""Recognition of right-display state and visible UI elements."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry, Frame, rectify_display
from dmi_computer_vision.src.dmi.detection.title_ocr import read_field, read_title, title_state
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
) -> dict[str, Any]:
    """Recognize the visible right-display structure and original-frame boxes."""
    rectified = rectify_display(frame, geometry, RECTIFIED_SIZE)
    if right_display_obstructed(rectified, train_workflow=state_hint is not None):
        return {"state": "unknown", "title": None, "buttons": {},
                "data_field": None, "visibility": "occluded"}
    border_lines = detect_border_lines(rectified)
    field_detection = _detect_data_field(rectified)
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
                    value = read_field(rectified, value_box)
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
    detected_buttons = (detect_button_quads(rectified, state, border_lines)
                        if state != "unknown" or title_text is not None else {})
    for name, quad in detected_buttons.items():
        buttons[name] = _region_result(quad, geometry, frame.shape[:2])
    return {
        "visibility": "clear",
        "state": state,
        "title": title,
        "buttons": buttons,
        "data_field": data_field,
    }


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
