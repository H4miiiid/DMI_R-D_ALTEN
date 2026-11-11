"""Frame-level orchestration for DMI screen understanding.

The public frame contract is established here so later stages can add
evidence-backed detections without changing video acquisition or output code.
"""

from __future__ import annotations

from typing import Any
from copy import deepcopy
import math
from contextlib import nullcontext
from collections.abc import Callable

from dmi_computer_vision.src.dmi.utils.image_ops import validate_frame
from dmi_computer_vision.src.dmi.detection.analysis_session import AnalysisSession, select_connected

from dmi_computer_vision.src.dmi.detection.display_geometry import Frame, detect_displays, rectify_display
from dmi_computer_vision.src.dmi.detection.right_display import analyze_right_display
from dmi_computer_vision.src.dmi.detection.left_display import (RECTIFIED_SIZE as LEFT_SIZE,
                                        analyze_left_display, analyze_train_left_display)
from dmi_computer_vision.src.dmi.temporal.left_tracking import LeftDisplayStabilizer
from dmi_computer_vision.src.dmi.temporal.smoothing import (
    GeometryStabilizer, LeftWorkflowStabilizer, RightDisplayStabilizer,
)

FrameResult = dict[str, Any]


class FrameProcessor:
    """One sequential source's temporal state, independent of frame acquisition.

    Video callers supply index/FPS timestamps. Live callers supply elapsed
    monotonic receipt times and may bound the gap across which history is used.
    """

    def __init__(self, *, max_gap_seconds: float | None = None, collect_target_evidence: bool = False,
                 optimize: bool = True, contrast_fallback: bool = False,
                 collect_layout_evidence: bool = False) -> None:
        if max_gap_seconds is not None and (
            not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0
        ):
            raise ValueError("max_gap_seconds must be finite and positive")
        self.collect_target_evidence = collect_target_evidence
        if type(contrast_fallback) is not bool:
            raise ValueError('contrast_fallback must be a boolean')
        self.contrast_fallback = contrast_fallback
        self.target_evidence: dict = {}
        self.layout_evidence: dict = {}
        if type(collect_layout_evidence) is not bool:
            raise ValueError('collect_layout_evidence must be a boolean')
        self.collect_layout_evidence = collect_layout_evidence
        self.max_gap_seconds = max_gap_seconds
        self._analysis = AnalysisSession() if optimize else None
        self.reset()

    def reset(self) -> None:
        """Begin a new source/session with no previous detections."""
        self.close()
        self.target_evidence.clear()
        self.layout_evidence.clear()
        self._index = 0
        self._timestamp: float | None = None
        self._shape: tuple[int, ...] | None = None
        self.last_reset_reason: str | None = None
        self._reset_history()

    def close(self) -> None:
        """Release session-owned native OCR resources."""
        if self._analysis is not None:
            self._analysis.close()

    def read_regions(self, reader: Callable[[], Any]) -> Any:
        """Share this owner's OCR engine for admitted SENSE ROI presentation.

        No full detector result, target evidence, temporal counters or processed
        timestamp is updated. The caller must independently verify the ROI basis.
        """
        with self._analysis.frame() if self._analysis is not None else nullcontext():
            select_connected(True)
            return reader()

    def _reset_history(self) -> None:
        self._geometry = GeometryStabilizer()
        self._right = RightDisplayStabilizer()
        self._left = LeftDisplayStabilizer()
        self._left_workflow = LeftWorkflowStabilizer()

    def process(self, frame: Frame, timestamp: float) -> FrameResult:
        validate_frame(frame)
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("timestamp must be finite and non-negative")
        if self._timestamp is not None and timestamp <= self._timestamp:
            raise ValueError("timestamps must increase within a session")
        reason = None
        if self._shape is not None and frame.shape != self._shape:
            reason = "frame_size_changed"
        elif (self._timestamp is not None and self.max_gap_seconds is not None
              and timestamp - self._timestamp > self.max_gap_seconds):
            reason = "capture_gap"
        if reason:
            self._reset_history()
        self.last_reset_reason = reason
        try:
            self.target_evidence.clear()
            self.layout_evidence.clear()
            arguments = (frame, self._index, timestamp, self._geometry, self._right,
                         self._left, self._left_workflow)
            with self._analysis.frame() if self._analysis is not None else nullcontext():
                features = {'contrast_fallback': True} if self.contrast_fallback else {}
                if self.collect_layout_evidence:
                    features['layout_evidence'] = self.layout_evidence
                result = (process_frame(*arguments, target_evidence=self.target_evidence, **features)
                          if self.collect_target_evidence else process_frame(*arguments, **features))
            if self.last_reset_reason is None:
                self.last_reset_reason = self._geometry.last_reset_reason
        except Exception:
            self.layout_evidence.clear()
            self.close()
            self._reset_history()
            raise
        self._index += 1
        self._timestamp = timestamp
        self._shape = frame.shape
        return result


def process_frame(
    frame: Frame,
    frame_index: int,
    timestamp: float,
    geometry_stabilizer: GeometryStabilizer | None = None,
    right_display_stabilizer: RightDisplayStabilizer | None = None,
    left_display_stabilizer: LeftDisplayStabilizer | None = None,
    left_workflow_stabilizer: LeftWorkflowStabilizer | None = None,
    *, target_evidence: dict | None = None, contrast_fallback: bool = False,
    layout_evidence: dict | None = None,
) -> FrameResult:
    """Process one source-independent BGR frame.

    Unimplemented recognition stages return explicit unknown values rather
    than fabricated detections.
    """
    validate_frame(frame)
    if type(frame_index) is not int or frame_index < 0:
        raise ValueError("frame_index must be a non-negative integer")
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("timestamp must be finite and non-negative")

    diagnostics: dict[str, str] = {}
    displays = detect_displays(frame, diagnostics=diagnostics)
    monitor_geometry = ({side+'_display': geometry.as_result() if geometry is not None else None
                         for side, geometry in displays.items()}
                        if layout_evidence is not None and contrast_fallback
                        and diagnostics.get('path') == 'connected' else None)
    select_connected(diagnostics.get("path") == "connected")
    if geometry_stabilizer is not None:
        layout = diagnostics.get("path")
        # An independently fitted orphan uses a different crop basis from a
        # connected-surface partition, even when their enclosures nearly agree.
        if layout not in {"connected", "separated", "partial"} or not any(displays.values()):
            layout = None
        if layout == "connected":
            layout = f"connected:{diagnostics.get('division_basis', 'unknown')}"
        displays = geometry_stabilizer.update(displays, frame.shape[:2], layout=layout)
        if "right" in geometry_stabilizer.reset_regions and right_display_stabilizer is not None:
            right_display_stabilizer.reset()
        if "left" in geometry_stabilizer.reset_regions:
            if left_display_stabilizer is not None:
                left_display_stabilizer.reset()
            if left_workflow_stabilizer is not None:
                left_workflow_stabilizer.reset()
    left_geometry = displays["left"]
    right_geometry = displays["right"]
    left_rectified = (rectify_display(frame, left_geometry, LEFT_SIZE)
                      if left_geometry is not None else None)
    connected = diagnostics.get("path") == "connected"
    train_left = (analyze_train_left_display(left_rectified, left_geometry, connected=connected,
                  **({'read_summary': False} if connected and layout_evidence is not None else {}),
                  **({'tight_title': True} if connected and contrast_fallback else {}))
                  if left_geometry is not None else None)
    train_state = train_left[0] if train_left is not None else None
    edge_buttons = {} if connected and contrast_fallback and layout_evidence is not None else None
    right_content = (
        analyze_right_display(frame, right_geometry, train_state, connected=connected,
                              **({'contrast_fallback': True} if connected and contrast_fallback else {}),
                              **({'edge_buttons': edge_buttons} if edge_buttons is not None else {}))
        if right_geometry is not None
        else {
            "visibility": "unknown",
            "state": "unknown",
            "title": None,
            "buttons": {},
            "data_field": None,
        }
    )
    if layout_evidence is not None:
        layout_evidence.clear()
        if monitor_geometry is not None:
            # Same current native measurements, before the accepted detector's
            # temporal geometry smoothing. Never target/calibration evidence.
            layout_evidence['monitor_geometry'] = monitor_geometry
        if connected and right_content['state'] != 'unknown':
            # Optional same-pass geometry before legacy display smoothing. This
            # separate side channel never changes detection/target outputs.
            layout_evidence['right_display'] = deepcopy(right_content)
            if edge_buttons is not None:
                layout_evidence['edge_buttons'] = deepcopy(edge_buttons)
    if target_evidence is not None:
        target_evidence.clear()
        target_evidence.update({
            "right_state": right_content["state"],
            "right_visibility": right_content["visibility"],
            "right_buttons": {name: list(region["center"])
                              for name, region in right_content["buttons"].items() if region is not None},
            "right_field_value": (right_content["data_field"].get("value")
                                  if right_content["data_field"] is not None else None),
            "right_field": (list(right_content["data_field"]["center"])
                            if right_content["data_field"] is not None else None),
        })
    if right_display_stabilizer is not None:
        if right_geometry is None:
            right_display_stabilizer.reset()
        else:
            right_content = right_display_stabilizer.update(
                right_content, right_geometry,
                measured_buttons=connected and train_state in {
                    "Train Data (1/2)", "Train Data (2/2)", "Validate Train Data"},
            )
    if train_left is not None:
        left_content = train_left[1]
        if layout_evidence is not None and layout_evidence:
            layout_evidence['left_display'] = deepcopy(left_content)
        if connected and target_evidence is not None:
            # Current SENSE completion controls, before temporal stabilization.
            # Separated/TWIN output and evidence remain unchanged.
            target_evidence['left_buttons'] = {
                name: list(region['center']) for name, region in left_content.get('buttons', {}).items()
                if region is not None}
        if left_workflow_stabilizer is not None:
            left_content = left_workflow_stabilizer.update(
                train_state, left_content, left_geometry
            )
    elif left_geometry is not None:
        measured_left = {} if layout_evidence is not None and layout_evidence else None
        left_content = analyze_left_display(
            frame, left_geometry, left_display_stabilizer, left_rectified,
            **({'layout_evidence': measured_left} if measured_left is not None else {})
        )
        if measured_left is not None:
            layout_evidence['left_display'] = measured_left
    else:
        left_content = {"boxes": {}, "speed_indicator": None}
    if (train_left is not None or left_geometry is None) and left_display_stabilizer is not None:
        left_display_stabilizer.reset()
    if train_left is None and left_workflow_stabilizer is not None:
        left_workflow_stabilizer.reset()
    return {
        "frame_index": int(frame_index),
        "timestamp": round(float(timestamp), 6),
        "right_display": {
            "geometry": right_geometry.as_result() if right_geometry else None,
            **right_content,
        },
        "left_display": {
            "geometry": left_geometry.as_result() if left_geometry else None,
            **left_content,
        },
    }
