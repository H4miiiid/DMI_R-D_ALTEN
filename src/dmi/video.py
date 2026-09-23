"""Recorded-video input and output handling.

Frame acquisition is kept separate from the frame-level understanding pipeline
so a live source can later call the same ``process_frame`` function.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import cv2

from dmi.pipeline import annotate_frame, process_frame
from dmi.temporal import GeometryStabilizer, RightDisplayStabilizer


@dataclass(frozen=True)
class VideoRunSummary:
    input_path: Path
    json_path: Path
    annotated_video_path: Path
    processed_frames: int
    fps: float
    frame_size: tuple[int, int]


def process_video(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    max_frames: int | None = None,
) -> VideoRunSummary:
    """Process a recorded video into frame JSON and an annotated MP4."""
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input video does not exist: {source}")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive when provided")

    json_path = destination / "results.json"
    video_path = destination / "annotated.mp4"
    if not overwrite:
        existing = [path for path in (json_path, video_path) if path.exists()]
        if existing:
            names = ", ".join(str(path) for path in existing)
            raise FileExistsError(f"refusing to overwrite existing output: {names}")

    destination.mkdir(parents=True, exist_ok=True)
    temporary_json = destination / ".results.tmp.json"
    temporary_video = destination / ".annotated.tmp.mp4"

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"could not open input video: {source}")

    writer: cv2.VideoWriter | None = None
    try:
        fps, width, height = _read_video_properties(capture, source)
        writer = cv2.VideoWriter(
            str(temporary_video),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            raise RuntimeError(f"could not create annotated video: {video_path}")

        results: list[dict[str, Any]] = []
        geometry_stabilizer = GeometryStabilizer()
        right_display_stabilizer = RightDisplayStabilizer()
        frame_index = 0
        while max_frames is None or frame_index < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_index / fps
            result = process_frame(
                frame,
                frame_index,
                timestamp,
                geometry_stabilizer,
                right_display_stabilizer,
            )
            writer.write(annotate_frame(frame, result))
            results.append(result)
            frame_index += 1

        if not results:
            raise RuntimeError(f"input video contains no readable frames: {source}")

        writer.release()
        writer = None
        payload = {"video": source.name, "frames": results}
        with temporary_json.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")

        os.replace(temporary_video, video_path)
        os.replace(temporary_json, json_path)
        return VideoRunSummary(
            input_path=source,
            json_path=json_path,
            annotated_video_path=video_path,
            processed_frames=len(results),
            fps=fps,
            frame_size=(width, height),
        )
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        temporary_json.unlink(missing_ok=True)
        temporary_video.unlink(missing_ok=True)


def _read_video_properties(
    capture: cv2.VideoCapture, source: Path
) -> tuple[float, int, int]:
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"invalid video properties for: {source}")
    return fps, width, height
