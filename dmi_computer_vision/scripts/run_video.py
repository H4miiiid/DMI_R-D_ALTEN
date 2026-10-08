#!/usr/bin/env python3
"""Process one recorded DMI video."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi_computer_vision.src.dmi.pipeline.video import process_video  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate compact incremental JSONL and an annotated DMI video."
    )
    parser.add_argument("input_video", type=Path, help="path to an input MP4")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="output directory (default: repository outputs/Version 2/<video-stem>/); filenames use the input stem",
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
    parser.add_argument("--debug", action="store_true", help="also save full per-frame debug JSONL")
    parser.add_argument("--geometry-tolerance", type=float, default=5.0, help="output geometry tolerance in source pixels (default: 5)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = REPOSITORY_ROOT / "outputs" / "Version 2" / args.input_video.stem

    try:
        summary = process_video(
            args.input_video,
            output_dir,
            overwrite=args.overwrite,
            max_frames=args.max_frames,
            source_named=True, debug=args.debug, geometry_tolerance=args.geometry_tolerance,
        )
    except KeyboardInterrupt:
        print(f"Interrupted; completed records remain under {output_dir}", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    width, height = summary.frame_size
    print(f"Processed {summary.processed_frames} frames; source rate {summary.fps:.3f} FPS")
    print(f"Source frame size: {width}x{height}")
    print(f"JSONL: {summary.json_path}")
    print(f"Annotated video: {summary.annotated_video_path}")
    if summary.debug_path:
        print(f"Debug JSONL: {summary.debug_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
