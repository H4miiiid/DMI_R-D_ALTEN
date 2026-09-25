"""Conservative obstruction evidence within a rectified blue DMI display.

This is an appearance gate, not a hand/robot identity classifier. It runs before
recognition, including on the first frame, and does not learn an occluded frame
as a clean background.
"""
from __future__ import annotations

import cv2
import numpy as np
from dmi.geometry import Frame


def right_display_obstructed(frame: Frame) -> bool:
    """Detect substantial non-screen foreground inside the active UI surface.

    Blue background/borders and small neutral glyphs are normal. Large dark or
    warm non-blue connected regions are obstruction evidence. Bright neutral
    fields are excluded; unseen robots with screen-like appearance remain a
    limitation, rather than an asserted universal occluder detector.
    """
    height, width = frame.shape[:2]
    blue, green, red = cv2.split(frame.astype(np.int16))
    foreground = (blue - green < 5) | (blue - red < 8)
    mask = (foreground & (blue + green + red < 240)).astype(np.uint8)
    # Large bright neutral tools in the lower UI are also foreground. A larger
    # opening removes ordinary text strokes before testing these components.
    bright = (foreground & (blue + green + red >= 240)).astype(np.uint8)
    bright[:round(height * .38)] = 0
    stroke_size = max(7, round(width * .025))
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN,
                             np.ones((stroke_size, stroke_size), np.uint8))
    mask |= bright
    # The physical bezel is not part of the active UI. The title's normal dark
    # band is not foreground evidence; warm intrusions there still qualify.
    mask[:round(height * .17)] &= (red[:round(height * .17)] >
                                   blue[:round(height * .17)] + 3)
    mask[:round(height * .055)] = 0
    mask[round(height * .96):] = 0
    mask[:, :round(width * .017)] = 0
    mask[:, round(width * .917):] = 0
    size = max(3, round(min(height, width) * .008))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                          np.ones((size, size), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    return any(
        area >= height * width * .0015
        and box_width >= width * .04
        and box_height >= height * .025
        for _, _, box_width, box_height, area in stats[1:]
    )
