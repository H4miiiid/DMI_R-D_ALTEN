#!/usr/bin/env python3
"""Run development videos and compare geometry against an approved baseline.

Counts describe predictions, not ground-truth recognition accuracy. Annotated
frames and videos require visual review when verified annotations are absent.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi.video import process_video


def without_icons(frame):
    result = deepcopy(frame)
    for box in result["left_display"]["boxes"].values():
        box.pop("icon", None)
    return result


def inspect_video(directory, frames):
    """Fully decode annotations and retain first/middle/last review frames."""
    selected = {0, len(frames) // 2, len(frames) - 1}
    capture = cv2.VideoCapture(str(directory / "annotated.mp4"))
    count, crops = 0, []
    while True:
        ok, image = capture.read()
        if not ok:
            break
        if count in selected:
            cv2.imwrite(str(directory / f"frame_{count:04d}.jpg"), image)
            geometry = frames[count]["left_display"]["geometry"]
            if geometry is not None:
                points = np.array(geometry["corners"])
                x1, y1 = np.maximum(points.min(axis=0) - 20, 0).astype(int)
                x2, y2 = np.minimum(points.max(axis=0) + 20, image.shape[1::-1]).astype(int)
                crop = image[y1:y2, x1:x2]
                cv2.imwrite(str(directory / f"left_{count:04d}.png"), crop)
                tile = cv2.resize(crop, (400, 640))
                cv2.putText(tile, f"frame {count}", (12, 25), 0, .6, (255, 255, 255), 2)
                crops.append(tile)
        count += 1
    capture.release()
    if crops:
        cv2.imwrite(str(directory / "review_strip.jpg"), np.hstack(crops))
    if count != len(frames):
        raise RuntimeError(f"Annotated frame count mismatch in {directory}")
    return count


def validate_geometry(frames):
    checked = 0
    for frame in frames:
        left = frame["left_display"]
        regions = list(left["boxes"].values())
        if left["speed_indicator"] is not None:
            regions.append(left["speed_indicator"])
        for region in regions:
            corners = np.array(region["corners"], np.float32)
            x1, y1, x2, y2 = region["bbox"]
            if (not np.isfinite(corners).all()
                    or not cv2.isContourConvex(corners)
                    or cv2.contourArea(corners) <= 0
                    or not (corners[:, 0].min() >= x1 and corners[:, 0].max() <= x2
                            and corners[:, 1].min() >= y1 and corners[:, 1].max() <= y2)
                    or cv2.pointPolygonTest(corners, tuple(region["center"]), False) < 0):
                raise RuntimeError(f"Invalid geometry at frame {frame['frame_index']}")
            checked += 1
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, default=Path("data/videos/dev"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    report = {}
    for source in sorted(args.videos.glob("*.mp4")):
        directory = args.output_dir / source.stem
        start = time.perf_counter()
        run = process_video(source, directory)
        elapsed = time.perf_counter() - start
        frames = json.loads(run.json_path.read_text())["frames"]
        baseline = json.loads((args.baseline / source.stem / "results.json").read_text())["frames"]
        if len(frames) != len(baseline):
            raise RuntimeError(f"Baseline frame count mismatch: {source}")
        changed = [i for i, (a, b) in enumerate(zip(frames, baseline))
                   if without_icons(a) != without_icons(b)]
        counts, associations, no_match = Counter(), Counter(), []
        for i, frame in enumerate(frames):
            found = False
            for name, box in frame["left_display"]["boxes"].items():
                if box["icon"] is not None:
                    counts[box["icon"]] += 1
                    associations[f"{name}: {box['icon']}"] += 1
                    found = True
            if not found:
                no_match.append(i)
        report[source.stem] = {
            "frames": len(frames), "icon_counts": dict(counts),
            "associations": dict(associations), "no_match_frames": no_match,
            "non_icon_regression_frames": changed,
            "geometry_regions_checked": validate_geometry(frames),
            "decoded_annotated_frames": inspect_video(directory, frames),
            "end_to_end_seconds": elapsed, "fps": len(frames) / elapsed,
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(source.stem, len(frames), dict(counts), "regressions", len(changed), flush=True)
        if changed:
            raise RuntimeError(f"Non-icon regression: {source}")
    if not report:
        raise RuntimeError("No input videos found")


if __name__ == "__main__":
    main()
