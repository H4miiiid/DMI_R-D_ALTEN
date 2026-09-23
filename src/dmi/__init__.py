"""DMI video screen-understanding package."""

from dmi.geometry import (
    DisplayGeometry,
    detect_displays,
    rectify_display,
)
from dmi.pipeline import annotate_frame, process_frame
from dmi.right_display import analyze_right_display
from dmi.temporal import GeometryStabilizer, RightDisplayStabilizer
from dmi.video import VideoRunSummary, process_video

__all__ = [
    "VideoRunSummary",
    "DisplayGeometry",
    "GeometryStabilizer",
    "RightDisplayStabilizer",
    "annotate_frame",
    "analyze_right_display",
    "detect_displays",
    "process_frame",
    "process_video",
    "rectify_display",
]
