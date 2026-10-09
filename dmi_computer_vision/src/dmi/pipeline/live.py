"""Live frame orchestration, incremental output and optional annotated preview."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import ExitStack
import math
from pathlib import Path
import time
from typing import Callable, Protocol

import cv2

from dmi_computer_vision.src.dmi.io.camera import CapturedFrame
from dmi_computer_vision.src.dmi.detection.display_geometry import Frame
from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor
from dmi_computer_vision.src.dmi.output.annotation import annotate_frame
from dmi_computer_vision.src.dmi.output.json_writer import CompactWriter, ProgressReporter, write_record
from dmi_computer_vision.src.dmi.output.latest_state import LatestState


class ProcessingPolicy(Protocol):
    def start_session(self) -> None: ...
    def should_process(self, packet: CapturedFrame, now: float) -> bool: ...


class LiveSource(Protocol):
    def read(self) -> CapturedFrame: ...


@dataclass(frozen=True)
class LiveRunSummary:
    jsonl_path: Path
    preview_path: Path | None
    processed_frames: int
    skipped_frames: int
    elapsed_seconds: float
    processing_seconds: float
    stop_reason: str
    debug_path: Path | None = None
    mean_receipt_to_result_seconds: float = 0.0
    max_receipt_to_result_seconds: float = 0.0
    max_capture_age_seconds: float = 0.0
    detection_seconds: float = 0.0
    annotation_seconds: float = 0.0
    consumed_frames: int = 0
    policy_skipped_frames: int = 0


def process_live(source: LiveSource, output_dir: str | Path, *, source_info: dict | None = None,
                 max_frames: int | None = None, max_gap_seconds: float = 1.0,
                 preview: Callable[[Frame], bool] | None = None,
                 debug: bool = False, geometry_tolerance: float = 5.0,
                 latest_state: LatestState | None = None,
                 processing_policy: ProcessingPolicy | None = None,
                 annotate: bool = True,
                 on_detection: Callable[[dict, CapturedFrame, float], None] | None = None,
                 on_skipped: Callable[[], bool] | None = None,
                 max_capture_frames: int | None = None,
                 on_detection_evidence: Callable[[dict, CapturedFrame, float, dict], None] | None = None) -> LiveRunSummary:
    """Consume received frames until a limit, preview stop, Ctrl-C or failure.

    Sources are opened/closed by the caller. Each emitted JSONL record is flushed;
    a terminal record marks clean stops or errors. No frames/results accumulate
    in memory. Existing session files are never overwritten.
    """
    if max_frames is not None and (type(max_frames) is not int or max_frames <= 0):
        raise ValueError("max_frames must be a positive integer")
    if max_capture_frames is not None and (type(max_capture_frames) is not int or max_capture_frames <= 0):
        raise ValueError("max_capture_frames must be positive")
    if not annotate and preview is not None:
        raise ValueError("Preview requires annotation")
    if (type(geometry_tolerance) not in (int, float)
            or not math.isfinite(geometry_tolerance) or geometry_tolerance < 0):
        raise ValueError("geometry_tolerance must be a finite nonnegative number")
    processor = (FrameProcessor(max_gap_seconds=max_gap_seconds, collect_target_evidence=True)
                 if on_detection_evidence is not None else FrameProcessor(max_gap_seconds=max_gap_seconds))
    if processing_policy is not None:
        processing_policy.start_session()
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    jsonl_path, preview_path = directory / "results.jsonl", directory / "last_annotated.png"
    debug_path = directory / "results_debug.jsonl" if debug else None
    for path in [jsonl_path, preview_path] + ([debug_path] if debug else []):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")
    count = skipped = consumed = policy_skipped = 0
    detection_seconds = annotation_seconds = 0.0
    previous_consumed_index = -1
    last_consumed_receipt = None
    processing_seconds = 0.0
    latency_total = latency_max = capture_age_max = 0.0
    first_received = last_received = None
    previous_index = -1
    last_image = None
    start = time.monotonic()
    reason = "max_frames"
    failure: str | None = None
    progress = ProgressReporter("Live")
    with ExitStack() as stack:
        if latest_state is not None:
            stack.enter_context(latest_state)
        stream = stack.enter_context(jsonl_path.open("x", encoding="utf-8"))
        debug_stream = stack.enter_context(debug_path.open("x", encoding="utf-8")) if debug else None
        logger = CompactWriter(stream, {"source": source_info or {"kind": "live_frames"},
               "timestamp_basis": "monotonic_receipt_seconds_since_first_processed_frame",
               "max_gap_seconds": max_gap_seconds}, geometry_tolerance=geometry_tolerance)
        try:
            while (max_frames is None or count < max_frames) and (max_capture_frames is None or consumed < max_capture_frames):
                try:
                    packet = source.read()
                except EOFError:
                    reason = "eof"
                    break
                if (type(packet.capture_index) is not int or packet.capture_index <= previous_consumed_index
                        or not math.isfinite(packet.received_at)
                        or (last_consumed_receipt is not None and packet.received_at <= last_consumed_receipt)):
                    raise ValueError("live capture indices and finite receipt times must increase")
                if packet.received_at > time.monotonic():
                    raise ValueError("live receipt time must not be in the future")
                consumed += 1
                previous_consumed_index, last_consumed_receipt = packet.capture_index, packet.received_at
                if processing_policy is not None and not processing_policy.should_process(packet, time.monotonic()):
                    policy_skipped += 1
                    if on_skipped is not None and not on_skipped():
                        reason = "preview_closed"
                        break
                    continue
                if first_received is None:
                    first_received = packet.received_at
                timestamp = packet.received_at - first_received
                started_processing = time.monotonic()
                capture_age = started_processing - packet.received_at
                result = processor.process(packet.image, timestamp)
                finished_detection = time.monotonic()
                annotated = annotate_frame(packet.image, result) if annotate else None
                finished_processing = time.monotonic()
                detection_seconds += finished_detection - started_processing
                annotation_seconds += finished_processing - finished_detection if annotate else 0.0
                seconds = finished_processing - started_processing
                latency = finished_processing - packet.received_at
                dropped = packet.capture_index - previous_index - 1
                logger.process(result, force_snapshot=processor.last_reset_reason is not None,
                               context={"capture_index": packet.capture_index,
                                        "frame_size": [packet.image.shape[1], packet.image.shape[0]],
                                        "temporal_reset": processor.last_reset_reason})
                if debug_stream is not None:
                    write_record(debug_stream, {"type": "frame", "capture_index": packet.capture_index,
                        "received_at_monotonic": packet.received_at,
                        "received_at_utc": getattr(packet, "received_at_utc", None),
                        "source_video_seconds": getattr(packet, "source_video_seconds", None),
                        "skipped_frames": dropped,
                        "frame_size": [packet.image.shape[1], packet.image.shape[0]],
                        "processing_seconds": seconds,
                        "receipt_to_result_seconds": finished_processing - packet.received_at,
                        "temporal_reset": processor.last_reset_reason, "result": result})
                if latest_state is not None:
                    latest_state.publish(result, capture_index=packet.capture_index,
                        received_at=packet.received_at, processed_at=finished_processing,
                        frame_size=(packet.image.shape[1], packet.image.shape[0]),
                        temporal_reset=processor.last_reset_reason)
                if on_detection is not None:
                    on_detection(result, packet, finished_processing)
                if on_detection_evidence is not None:
                    on_detection_evidence(result, packet, finished_processing, processor.target_evidence)
                count += 1
                skipped += dropped
                processing_seconds += seconds
                latency_total += latency
                latency_max = max(latency_max, latency)
                capture_age_max = max(capture_age_max, capture_age)
                previous_index, last_received = packet.capture_index, packet.received_at
                last_image = annotated
                progress.report(count)
                if preview is not None and not preview(annotated):
                    reason = "preview_closed"
                    break
            if (reason == "max_frames" and max_capture_frames is not None and consumed >= max_capture_frames
                    and (max_frames is None or count < max_frames)):
                reason = "max_capture_frames"
        except KeyboardInterrupt:
            reason = "interrupted"
        except Exception as exc:
            reason, failure = "error", str(exc)
            raise
        finally:
            # Completed JSONL records survive failures; the summary is not a
            # claim that an errored or forcibly killed session completed.
            elapsed = time.monotonic() - start
            try:
                if last_image is not None and not cv2.imwrite(str(preview_path), last_image):
                    raise RuntimeError(f"could not save preview: {preview_path}")
            except Exception as exc:
                reason, failure = "error", str(exc)
                raise
            finally:
                logger.finish(processed_frames=count, skipped_frames=skipped,
                              detection_seconds=detection_seconds, annotation_seconds=annotation_seconds,
                              consumed_frames=consumed, policy_skipped_frames=policy_skipped,
                              elapsed_seconds=elapsed, processing_seconds=processing_seconds,
                              mean_receipt_to_result_seconds=latency_total / count if count else 0.0,
                              max_receipt_to_result_seconds=latency_max,
                              max_capture_age_seconds=capture_age_max,
                              duration_seconds=(last_received - first_received) if count else 0.0,
                              stop_reason=reason, error=failure)
                progress.report(count, force=True)
    return LiveRunSummary(jsonl_path, preview_path if last_image is not None else None,
                          count, skipped, elapsed, processing_seconds, reason, debug_path,
                          latency_total / count if count else 0.0, latency_max, capture_age_max,
                          detection_seconds, annotation_seconds, consumed, policy_skipped)
