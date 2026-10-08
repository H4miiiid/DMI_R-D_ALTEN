"""DMI video screen-understanding package."""

from dmi_computer_vision.src.dmi.detection.display_geometry import (
    DisplayGeometry,
    detect_displays,
    rectify_display,
)
from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor, process_frame
from dmi_computer_vision.src.dmi.output.annotation import annotate_frame
from dmi_computer_vision.src.dmi.detection.left_display import analyze_left_display
from dmi_computer_vision.src.dmi.temporal.left_tracking import LeftDisplayStabilizer
from dmi_computer_vision.src.dmi.detection.right_display import analyze_right_display
from dmi_computer_vision.src.dmi.temporal.smoothing import GeometryStabilizer, RightDisplayStabilizer
from dmi_computer_vision.src.dmi.pipeline.video import VideoRunSummary, process_video

__all__ = [
    "FrameProcessor",
    "VideoRunSummary",
    "DisplayGeometry",
    "GeometryStabilizer",
    "RightDisplayStabilizer",
    "LeftDisplayStabilizer",
    "analyze_left_display",
    "annotate_frame",
    "analyze_right_display",
    "detect_displays",
    "process_frame",
    "process_video",
    "rectify_display",
]
