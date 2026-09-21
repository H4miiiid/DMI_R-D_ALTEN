#!/usr/bin/env python3
"""Process one recorded DMI video."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.video import process_video  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate frame-level JSON and an annotated DMI video."
    )
    parser.add_argument("input_video", type=Path, help="path to an input MP4")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="output directory (default: outputs/<video-stem>)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing generated results in the output directory",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        help="process only the first N frames (useful for quick checks)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = REPOSITORY_ROOT / "outputs" / args.input_video.stem

    try:
        summary = process_video(
            args.input_video,
            output_dir,
            overwrite=args.overwrite,
            max_frames=args.max_frames,
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    width, height = summary.frame_size
    print(f"Processed {summary.processed_frames} frames at {summary.fps:.3f} FPS")
    print(f"Source frame size: {width}x{height}")
    print(f"JSON: {summary.json_path}")
    print(f"Annotated video: {summary.annotated_video_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
