"""Recognition of right-display state and visible UI elements."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi.geometry import DisplayGeometry, Frame, rectify_display
from dmi.right_layout import (
    BorderLines,
    detect_border_lines,
    detect_button_quads,
    detect_title_quad,
    field_quad_from_contour,
    matches_known_layout,
)

RECTIFIED_SIZE = (600, 960)


def analyze_right_display(
    frame: Frame, geometry: DisplayGeometry
) -> dict[str, Any]:
    """Recognize the visible right-display structure and original-frame boxes."""
    rectified = rectify_display(frame, geometry, RECTIFIED_SIZE)
    border_lines = detect_border_lines(rectified)
    field_detection = _detect_data_field(rectified)
    field_box = field_detection[0] if field_detection is not None else None
    title_box = _detect_title_box(rectified, field_box)
    state = _classify_state(rectified, title_box, field_box, border_lines)
    title = None
    if title_box is not None:
        title = _region_result(
            detect_title_quad(rectified, title_box),
            geometry,
            frame.shape[:2],
        )
        title["text"] = state if state != "unknown" else None

    data_field = None
    if field_box is not None and state in {"Driver ID", "Level"}:
        field_image = _crop_box(rectified, field_box)
        digits = _read_digits(field_image, last_only=state == "Level")
        value = digits if state == "Driver ID" else (f"Level {digits}" if digits else None)
        data_field = _region_result(
            field_quad_from_contour(field_detection[1]),
            geometry,
            frame.shape[:2],
        )
        data_field["value"] = value

    buttons = {}
    for name, quad in detect_button_quads(rectified, state, border_lines).items():
        buttons[name] = _region_result(quad, geometry, frame.shape[:2])
    return {
        "state": state,
        "title": title,
        "buttons": buttons,
        "data_field": data_field,
    }


def _detect_title_box(
    frame: Frame, field_box: tuple[int, int, int, int] | None = None
) -> tuple[int, int, int, int] | None:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    width, height = RECTIFIED_SIZE
    search_y1, search_y2 = round(height * 0.07), round(height * 0.19)
    if field_box is not None:
        search_y2 = min(search_y2, field_box[1] - 5)
    mask = cv2.inRange(
        hsv[search_y1:search_y2, : round(width * 0.55)],
        (0, 0, 75),
        (179, 120, 255),
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
        return None
    return max(
        candidates,
        key=lambda item: (item[0][2] - item[0][0]) * (item[0][3] - item[0][1]),
    )


def _classify_state(
    frame: Frame,
    title_box: tuple[int, int, int, int] | None,
    field_box: tuple[int, int, int, int] | None,
    border_lines: BorderLines,
) -> str:
    if title_box is None:
        return "unknown"
    if field_box is None:
        title_width = title_box[2] - title_box[0]
        return (
            "Main"
            if title_width >= 45
            and matches_known_layout(frame, "Main", border_lines)
            else "unknown"
        )
    title_width = title_box[2] - title_box[0]
    if title_width < 90:
        return "Level"
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, 90, 255)
    mask[: field_box[3] + 25] = 0
    mask[round(frame.shape[0] * 0.92) :] = 0
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    visible_components = sum(
        8 <= stats[index, cv2.CC_STAT_AREA] <= 2000
        and stats[index, cv2.CC_STAT_HEIGHT] >= 4
        for index in range(1, count)
    )
    candidate = "Level" if visible_components >= 28 else "Driver ID"
    return (
        candidate
        if matches_known_layout(frame, candidate, border_lines)
        else "unknown"
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
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    characters: list[tuple[int, str, float]] = []
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        if not (3 <= width <= 50 and 12 <= height <= 60 and area >= 30):
            continue
        glyph = (labels[y : y + height, x : x + width] == index).astype(np.uint8) * 255
        normalized = _normalize_glyph(glyph)
        scores = {
            digit: max(_correlation(normalized, template) for template in variants)
            for digit, variants in _digit_templates().items()
        }
        digit = max(scores, key=scores.get)
        characters.append((int(x), digit, scores[digit]))
    reliable = [(x, digit) for x, digit, score in characters if score >= 0.3]
    if not reliable:
        return None
    reliable.sort()
    if last_only:
        return reliable[-1][1]
    return "".join(digit for _, digit in reliable)


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
