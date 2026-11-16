"""Version 2 measured field fallback; the shared caller owns primary detection."""
from collections.abc import Callable
from logging import Logger

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi_computer_vision.src.dmi.shared.detection.display_geometry import DisplayGeometry, Frame
from dmi_computer_vision.src.dmi.v2.detection.field_contrast import supported_field, detect_contrast_field

FieldDetection = tuple[tuple[int, int, int, int], NDArray[np.int32]]


def detect_data_field(
    frame: Frame, *, size: tuple[int, int], primary_detector: Callable[..., FieldDetection | None],
    logger: Logger, evidence_frame: Frame | None = None, diagnostics: dict | None = None,
) -> FieldDetection | None:
    """Keep supported primary evidence, otherwise require one measured rectangle."""
    if evidence_frame is None:
        evidence_frame = frame
    if diagnostics is not None:
        diagnostics['method'] = 'none'
    proposals = []
    primary = primary_detector(frame, candidates_out=proposals)
    if diagnostics is not None:
        diagnostics['primary'] = primary
    margin = (evidence_frame.shape[1] - size[0]) // 2
    gray = cv2.cvtColor(evidence_frame, cv2.COLOR_BGR2GRAY)
    supported = [p for p in proposals if supported_field(gray, p[1] + margin, size)]
    if len(supported) > 1:
        logger.debug('SENSE field detector: ambiguous HSV rectangles')
        return None
    if primary is not None and any(p is primary for p in supported):
        logger.debug('SENSE field detector: HSV primary')
        if diagnostics is not None:
            diagnostics['method'] = 'hsv'
        return primary
    detected = detect_contrast_field(gray, size=size, margin=margin)
    if detected is None:
        logger.debug('SENSE field detector: no supported contrast rectangle')
        return None
    box, contour = detected
    x1, y1, x2, y2 = box
    box = (max(0, x1-margin), max(0, y1-margin),
           min(size[0], x2-margin), min(size[1], y2-margin))
    logger.debug('SENSE field detector: contrast fallback')
    if diagnostics is not None:
        diagnostics['method'] = 'contrast'
    return box, contour - margin


def field_evidence(frame: Frame, geometry: DisplayGeometry, *, size: tuple[int, int]) -> Frame | None:
    """A small measured native-pixel margin supplies field sides clipped by rectification."""
    width, height = size
    margin = 16
    destination = np.float32([[margin, margin], [width-1+margin, margin],
                              [width-1+margin, height-1+margin], [margin, height-1+margin]])
    matrix = cv2.getPerspectiveTransform(geometry.corners, destination)
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-12:
        return None
    enclosure = np.float32([[[0, 0], [width-1+2*margin, 0],
                             [width-1+2*margin, height-1+2*margin], [0, height-1+2*margin]]])
    native = cv2.perspectiveTransform(enclosure, np.linalg.inv(matrix))[0]
    if (not np.isfinite(native).all() or np.min(native) < 0
            or native[:, 0].max() >= frame.shape[1]-1 or native[:, 1].max() >= frame.shape[0]-1):
        return None  # Warp fill outside the camera must never supply a field edge.
    return cv2.warpPerspective(frame, matrix, (width+2*margin, height+2*margin))

