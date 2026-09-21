"""DMI video screen-understanding package."""

from dmi.geometry import (
    DisplayGeometry,
    detect_displays,
    rectify_display,
)
from dmi.pipeline import annotate_frame, process_frame
from dmi.temporal import GeometryStabilizer
from dmi.video import VideoRunSummary, process_video

__all__ = [
    "VideoRunSummary",
    "DisplayGeometry",
    "GeometryStabilizer",
    "annotate_frame",
    "detect_displays",
    "process_frame",
    "process_video",
    "rectify_display",
]
