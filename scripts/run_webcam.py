#!/usr/bin/env python3
"""Run the shared DMI pipeline on the latest available webcam frames."""
from __future__ import annotations

import argparse
import math
from datetime import datetime
from pathlib import Path
import sys

import cv2

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.io.camera import LatestCamera  # noqa: E402
from dmi.pipeline.live import process_live
from dmi.io.preview import LivePreview  # noqa: E402
from dmi.pipeline.frame_processor import FrameProcessor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="camera device index (default: 0)")
    parser.add_argument("--output-dir", type=Path,
                        help="default: repository outputs/Version 2/webcam_<camera>_<timestamp>/")
    parser.add_argument("--width", type=int, help="request capture width (requires --height)")
    parser.add_argument("--height", type=int, help="request capture height (requires --width)")
    parser.add_argument("--max-frames", type=int, help="stop after N processed frames")
    parser.add_argument("--no-preview", action="store_true", help="run without a GUI; Ctrl-C to stop")
    parser.add_argument("--timeout", type=float, default=5.0, help="camera wait timeout in seconds")
    parser.add_argument("--max-gap-seconds", type=float, default=1.0,
                        help="reset temporal history after this receipt-time gap (default: 1)")
    parser.add_argument("--debug", action="store_true", help="save detailed per-frame debug JSONL")
    parser.add_argument("--geometry-tolerance", type=float, default=5.0)
    args = parser.parse_args()
    directory = args.output_dir or (REPOSITORY_ROOT / "outputs" / "Version 2" /
        f"webcam_{args.camera}_{datetime.now():%Y%m%d_%H%M%S_%f}")
    preview = LivePreview()
    try:
        # Validate processing options/output collisions before opening a device.
        if args.max_frames is not None and args.max_frames <= 0:
            raise ValueError("max_frames must be positive")
        if not math.isfinite(args.geometry_tolerance) or args.geometry_tolerance < 0:
            raise ValueError("geometry-tolerance must be finite and nonnegative")
        FrameProcessor(max_gap_seconds=args.max_gap_seconds)
        for name in ("results.jsonl", "last_annotated.png", "results_debug.jsonl"):
            if (directory.expanduser() / name).exists():
                raise FileExistsError(f"output already exists: {directory / name}")
        print(f"Opening camera {args.camera}. Stop with Q/Escape or Ctrl-C.", flush=True)
        print(f"Results: {directory.expanduser().resolve()}", flush=True)
        with LatestCamera(args.camera, width=args.width, height=args.height,
                          timeout=args.timeout) as source:
            run = process_live(source, directory,
                               source_info={"kind": "camera", "index": args.camera},
                               max_frames=args.max_frames, max_gap_seconds=args.max_gap_seconds,
                               preview=None if args.no_preview else preview.show,
                               debug=args.debug, geometry_tolerance=args.geometry_tolerance)
        print(f"Processed {run.processed_frames} frames; skipped {run.skipped_frames}; "
              f"{run.processed_frames / max(run.elapsed_seconds, 1e-9):.2f} processed FPS")
        print(f"Stopped: {run.stop_reason}\nJSONL: {run.jsonl_path}")
        if run.preview_path:
            print(f"Last annotated frame: {run.preview_path}")
        return 0
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        preview.close()


if __name__ == "__main__":
    raise SystemExit(main())
