"""Live frame orchestration, incremental output and optional annotated preview."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import ExitStack
import math
from pathlib import Path
import time
from typing import Callable, Protocol

import cv2

from dmi.io.camera import CapturedFrame
from dmi.detection.display_geometry import Frame
from dmi.pipeline.frame_processor import FrameProcessor
from dmi.output.annotation import annotate_frame
from dmi.output.json_writer import CompactWriter, ProgressReporter, write_record


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


def process_live(source: LiveSource, output_dir: str | Path, *, source_info: dict | None = None,
                 max_frames: int | None = None, max_gap_seconds: float = 1.0,
                 preview: Callable[[Frame], bool] | None = None,
                 debug: bool = False, geometry_tolerance: float = 5.0) -> LiveRunSummary:
    """Consume received frames until a limit, preview stop, Ctrl-C or failure.

    Sources are opened/closed by the caller. Each emitted JSONL record is flushed;
    a terminal record marks clean stops or errors. No frames/results accumulate
    in memory. Existing session files are never overwritten.
    """
    if max_frames is not None and (type(max_frames) is not int or max_frames <= 0):
        raise ValueError("max_frames must be a positive integer")
    if (type(geometry_tolerance) not in (int, float)
            or not math.isfinite(geometry_tolerance) or geometry_tolerance < 0):
        raise ValueError("geometry_tolerance must be a finite nonnegative number")
    processor = FrameProcessor(max_gap_seconds=max_gap_seconds)
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    jsonl_path, preview_path = directory / "results.jsonl", directory / "last_annotated.png"
    debug_path = directory / "results_debug.jsonl" if debug else None
    for path in [jsonl_path, preview_path] + ([debug_path] if debug else []):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")
    count = skipped = 0
    processing_seconds = 0.0
    first_received = last_received = None
    previous_index = -1
    last_image = None
    start = time.monotonic()
    reason = "max_frames"
    failure: str | None = None
    progress = ProgressReporter("Live")
    with ExitStack() as stack:
        stream = stack.enter_context(jsonl_path.open("x", encoding="utf-8"))
        debug_stream = stack.enter_context(debug_path.open("x", encoding="utf-8")) if debug else None
        logger = CompactWriter(stream, {"source": source_info or {"kind": "live_frames"},
               "timestamp_basis": "monotonic_receipt_seconds_since_first_processed_frame",
               "max_gap_seconds": max_gap_seconds}, geometry_tolerance=geometry_tolerance)
        try:
            while max_frames is None or count < max_frames:
                packet = source.read()
                if (type(packet.capture_index) is not int or packet.capture_index <= previous_index
                        or not math.isfinite(packet.received_at)
                        or (last_received is not None and packet.received_at <= last_received)):
                    raise ValueError("live capture indices and finite receipt times must increase")
                if packet.received_at > time.monotonic():
                    raise ValueError("live receipt time must not be in the future")
                if first_received is None:
                    first_received = packet.received_at
                timestamp = packet.received_at - first_received
                started_processing = time.monotonic()
                result = processor.process(packet.image, timestamp)
                annotated = annotate_frame(packet.image, result)
                finished_processing = time.monotonic()
                seconds = finished_processing - started_processing
                dropped = packet.capture_index - previous_index - 1
                logger.process(result, force_snapshot=processor.last_reset_reason is not None,
                               context={"capture_index": packet.capture_index,
                                        "frame_size": [packet.image.shape[1], packet.image.shape[0]],
                                        "temporal_reset": processor.last_reset_reason})
                if debug_stream is not None:
                    write_record(debug_stream, {"type": "frame", "capture_index": packet.capture_index,
                        "skipped_frames": dropped,
                        "frame_size": [packet.image.shape[1], packet.image.shape[0]],
                        "processing_seconds": seconds,
                        "receipt_to_result_seconds": finished_processing - packet.received_at,
                        "temporal_reset": processor.last_reset_reason, "result": result})
                count += 1
                skipped += dropped
                processing_seconds += seconds
                previous_index, last_received = packet.capture_index, packet.received_at
                last_image = annotated
                progress.report(count)
                if preview is not None and not preview(annotated):
                    reason = "preview_closed"
                    break
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
                              elapsed_seconds=elapsed, processing_seconds=processing_seconds,
                              duration_seconds=(last_received - first_received) if count else 0.0,
                              stop_reason=reason, error=failure)
                progress.report(count, force=True)
    return LiveRunSummary(jsonl_path, preview_path if last_image is not None else None,
                          count, skipped, elapsed, processing_seconds, reason, debug_path)
