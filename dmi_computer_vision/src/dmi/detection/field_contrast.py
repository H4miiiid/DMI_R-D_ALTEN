"""Current-pixel contrast/border evidence for SENSE input fields; no OCR/state."""
from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi_computer_vision.src.dmi.detection.right_layout import field_quad_from_contour


def supported_field(gray: NDArray, contour: NDArray, size: tuple[int, int]) -> bool:
    """Require a filled bar and bright-inside evidence on all four measured sides."""
    width, height = size
    _, _, w, h = cv2.boundingRect(contour)
    if not (width * .7 <= w <= width + 24 and height * .05 <= h <= height * .2):
        return False
    if cv2.contourArea(contour) < w * h * .8:
        return False
    quad = field_quad_from_contour(contour)
    center = quad.mean(axis=0)
    background = float(np.percentile(gray[::4, ::4], 25))
    for a, b in zip(quad, np.roll(quad, -1, axis=0)):
        points = a + np.linspace(.1, .9, 96)[:, None] * (b - a)
        normal = center - (a + b) / 2
        normal /= max(float(np.linalg.norm(normal)), 1e-6)
        inside = np.rint(points + normal * 6).astype(int)
        outside = np.rint(points - normal * 6).astype(int)
        samples = np.vstack((inside, outside))
        if (samples[:, 0].min() < 0 or samples[:, 0].max() >= gray.shape[1]
                or samples[:, 1].min() < 0 or samples[:, 1].max() >= gray.shape[0]):
            return False  # Missing outside pixels cannot prove an edge.
        inner = gray[inside[:, 1], inside[:, 0]].astype(float)
        outer = gray[outside[:, 1], outside[:, 0]].astype(float)
        # Relative to local compression/noise; 3 gray levels is an 8-bit floor.
        noise = float(np.median(np.abs(np.diff(outer))))
        # A small color step within the pale bar is not its outer border.
        contrast_floor = max(3., 4 * noise, .5 * max(0., float(np.median(inner)) - background))
        if np.mean(inner - outer > contrast_floor) < .8:
            return False
    return True


def detect_contrast_field(gray: NDArray, *, size: tuple[int, int], margin: int) -> tuple | None:
    """Find one supported pale bar; multiple supported rectangles stay ambiguous."""
    width, height = size
    # A tall opening estimates the local background without the shorter field.
    background = cv2.morphologyEx(gray, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (15, round(height * .22) | 1)))
    contrast = cv2.subtract(gray, background)
    start, end = margin + round(height * .1), margin + round(height * .44)
    _, selected = cv2.threshold(contrast[start:end], 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    mask = np.zeros(gray.shape, np.uint8)
    mask[start:end] = selected
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    supported = [c for c in contours if supported_field(gray, c, size)]
    if len(supported) != 1:
        return None
    contour = supported[0]
    x, y, w, h = cv2.boundingRect(contour)
    return (x, y, x + w, y + h), contour
