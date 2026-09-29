"""Shared frame processing and recorded/live orchestration."""

from dmi.pipeline.frame_processor import FrameProcessor, process_frame
from dmi.output.annotation import annotate_frame

__all__ = ["FrameProcessor", "process_frame", "annotate_frame"]
