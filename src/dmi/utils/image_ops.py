"""Shared BGR frame validation."""

import numpy as np

from dmi.detection.display_geometry import Frame


def validate_frame(frame: Frame) -> None:
    if not isinstance(frame, np.ndarray):
        raise TypeError("frame must be a NumPy array")
    if frame.dtype != np.uint8:
        raise ValueError("frame must use uint8 pixels")
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame must be a three-channel BGR image")
    if frame.size == 0:
        raise ValueError("frame must not be empty")
