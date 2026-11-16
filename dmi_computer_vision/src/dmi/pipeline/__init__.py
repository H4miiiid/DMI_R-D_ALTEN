"""Shared frame processing and recorded/live orchestration."""

from dmi_computer_vision.src.dmi.shared.pipeline.frame_processor import FrameProcessor, process_frame
from dmi_computer_vision.src.dmi.shared.output.annotation import annotate_frame

__all__ = ["FrameProcessor", "process_frame", "annotate_frame"]
