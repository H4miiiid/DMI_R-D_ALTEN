"""Recorded-video input and output handling.

Frame acquisition is kept separate from the frame-level understanding pipeline
so a live source can later call the same ``process_frame`` function.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import ExitStack
import math
import os
from pathlib import Path
import time

import cv2

from dmi.pipeline.frame_processor import FrameProcessor
from dmi.output.annotation import annotate_frame
from dmi.output.json_writer import CompactWriter, ProgressReporter, write_record


@dataclass(frozen=True)
class VideoRunSummary:
    input_path: Path
    json_path: Path
    annotated_video_path: Path
    processed_frames: int
    fps: float
    frame_size: tuple[int, int]
    declared_frames: int | None = None
    debug_path: Path | None = None


def process_video(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    max_frames: int | None = None,
    source_named: bool = False,
    debug: bool = False,
    geometry_tolerance: float = 5.0,
) -> VideoRunSummary:
    """Stream compact JSONL and annotations; retain partial files on failure.

    Existing completed outputs survive a failed overwrite. A previous partial
    run must be moved aside (or a fresh directory used) before retrying.
    """
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input video does not exist: {source}")
    if max_frames is not None and (type(max_frames) is not int or max_frames <= 0):
        raise ValueError("max_frames must be a positive integer when provided")
    if (type(geometry_tolerance) not in (int, float)
            or not math.isfinite(geometry_tolerance) or geometry_tolerance < 0):
        raise ValueError("geometry_tolerance must be a finite nonnegative number")
    stem = source.stem if source_named else "results"
    json_path = destination / f"{stem}.jsonl"
    debug_path = destination / f"{stem}_debug.jsonl" if debug else None
    video_path = destination / (f"{source.stem}_annotated.mp4" if source_named else "annotated.mp4")
    outputs = [json_path, video_path] + ([debug_path] if debug else [])
    partials = [path.with_name(f"{path.stem}.partial{path.suffix}") for path in outputs]
    if source in outputs + partials:
        raise ValueError("output paths must not replace the input video")
    collisions = [path for path in partials + ([] if overwrite else outputs) if path.exists()]
    if collisions:
        raise FileExistsError(f"refusing to overwrite existing output: {collisions}")
    destination.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"could not open input video: {source}")
    writer = None
    started = time.monotonic()
    count = 0
    try:
        fps, width, height = _read_video_properties(capture, source)
        declared_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        declared_frames = (round(declared_count) if math.isfinite(declared_count)
                           and declared_count > 0 else None)
        with ExitStack() as stack:
            stream = stack.enter_context(partials[0].open("x", encoding="utf-8"))
            logger = CompactWriter(stream, {"source": source.name, "width": width,
                "height": height, "fps": fps, "declared_frames": declared_frames,
                "timestamp_basis": "decoded_frame_index/source_fps"},
                geometry_tolerance=geometry_tolerance)
            debug_stream = None
            reason, failure = "eof", None
            progress = ProgressReporter(source.name, declared_frames)
            try:
                if debug:
                    debug_stream = stack.enter_context(partials[2].open("x", encoding="utf-8"))
                writer = cv2.VideoWriter(str(partials[1]), cv2.VideoWriter_fourcc(*"mp4v"),
                                         fps, (width, height))
                if not writer.isOpened():
                    raise RuntimeError(f"could not create annotated video: {video_path}")
                processor = FrameProcessor()
                while max_frames is None or count < max_frames:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    result = processor.process(frame, count / fps)
                    annotated = annotate_frame(frame, result)
                    logger.process(result)
                    if debug_stream is not None:
                        write_record(debug_stream, result)
                    writer.write(annotated)
                    count += 1
                    progress.report(count)
                if not count:
                    raise RuntimeError(f"input video contains no readable frames: {source}")
                if max_frames is not None and count == max_frames:
                    reason = "max_frames"
            except BaseException as exc:
                reason = "interrupted" if isinstance(exc, KeyboardInterrupt) else "error"
                failure = str(exc) or type(exc).__name__
                raise
            finally:
                if writer is not None:
                    writer.release()
                    writer = None
                logger.finish(processed_frames=count, duration_seconds=count / fps,
                              processing_seconds=time.monotonic() - started,
                              stop_reason=reason, error=failure)
                progress.report(count, force=True)
        for partial, output in zip(partials, outputs):
            os.replace(partial, output)
        return VideoRunSummary(source, json_path, video_path, count, fps,
                               (width, height), declared_frames, debug_path)
    finally:
        capture.release()
        if writer is not None:
            writer.release()


def _read_video_properties(
    capture: cv2.VideoCapture, source: Path
) -> tuple[float, int, int]:
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = float(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = float(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not all(math.isfinite(value) and value > 0 for value in (fps, width, height)):
        raise RuntimeError(f"invalid video properties for: {source}")
    if not width.is_integer() or not height.is_integer():
        raise RuntimeError(f"noninteger video dimensions for: {source}")
    return fps, int(width), int(height)
