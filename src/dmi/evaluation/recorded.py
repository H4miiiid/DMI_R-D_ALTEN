"""Run development videos and compare geometry against an approved baseline.

Counts describe predictions, not ground-truth recognition accuracy. Annotated
frames and videos require visual review when verified annotations are absent.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import time

import cv2
import numpy as np

from dmi.pipeline.video import process_video
from dmi.evaluation.compact import validate_compact
from dmi.evaluation.validation import validate_results, compare_frames, compare_annotated_videos


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


def validate_geometry(frames, side="left"):
    checked = 0
    for frame in frames:
        display = frame[f"{side}_display"]
        if side == "left":
            regions = list(display["boxes"].values())
            regions += [display["speed_indicator"]] if display["speed_indicator"] else []
        else:
            regions = list(display["buttons"].values())
            regions += [display[key] for key in ("title", "data_field") if display[key]]
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


def validation_result(check, allow_invalid=False):
    """Keep invalid baseline evidence explicit without weakening default checks."""
    try:
        return check()
    except (ValueError, RuntimeError) as exc:
        if not allow_invalid:
            raise
        return {"error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, default=Path("data/videos/dev"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--video", action="append", help="video stem to include (repeatable)")
    parser.add_argument("--allow-new", action="store_true",
                        help="process videos without baseline JSON; report comparison as unavailable")
    parser.add_argument("--allow-changes", action="store_true",
                        help="record baseline differences for investigation instead of stopping")
    parser.add_argument("--allow-invalid", action="store_true",
                        help="record contract/geometry failures as errors for baseline investigation")
    args = parser.parse_args()
    report_path = args.output_dir / "verification.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    processed = 0
    for source in sorted(args.videos.glob("*.mp4")):
        if args.video and source.stem not in args.video:
            continue
        baseline_path = args.baseline / source.stem / "results.json"
        if not baseline_path.exists() and not args.allow_new:
            raise FileNotFoundError(f"No approved baseline: {baseline_path}; use --allow-new for new inputs")
        directory = args.output_dir / source.stem
        print(f"Processing {source.name}", flush=True)
        start = time.perf_counter()
        run = process_video(source, directory, debug=True)
        elapsed = time.perf_counter() - start
        frames = [json.loads(line) for line in run.debug_path.read_text().splitlines()]
        baseline = json.loads(baseline_path.read_text())["frames"] if baseline_path.exists() else None
        changed = all_changed = None
        if baseline is not None:
            if len(frames) != len(baseline):
                raise RuntimeError(f"Baseline frame count mismatch: {source}")
            changed = [i for i, (a, b) in enumerate(zip(frames, baseline))
                       if without_icons(a) != without_icons(b)]
            all_changed = [i for i, (a, b) in enumerate(zip(frames, baseline)) if a != b]
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
            "compact": validate_compact(run.json_path, frames),
            "contract": validation_result(lambda: validate_results(frames, run.fps), args.allow_invalid),
            "comparison": compare_frames(frames, baseline) if baseline is not None else None,
            "source_declared_frames": run.declared_frames,
            "frames": len(frames), "icon_counts": dict(counts),
            "associations": dict(associations), "no_match_frames": no_match,
            "baseline_available": baseline is not None,
            "all_field_changed_frames": all_changed,
            "non_icon_regression_frames": changed,
            "geometry_regions_checked": validation_result(lambda: validate_geometry(frames), args.allow_invalid),
            "right_geometry_regions_checked": validation_result(lambda: validate_geometry(frames, "right"), args.allow_invalid),
            "decoded_annotated_frames": inspect_video(directory, frames),
            "annotation_comparison": compare_annotated_videos(
                directory / "annotated.mp4", args.baseline / source.stem / "annotated.mp4"),
            "end_to_end_seconds": elapsed, "fps": len(frames) / elapsed,
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        processed += 1
        print(source.stem, len(frames), dict(counts), "changed frames", len(all_changed) if all_changed is not None else "no baseline", flush=True)
        if all_changed and not args.allow_changes:
            raise RuntimeError(f"Baseline difference: {source}; inspect before accepting")
    if not processed:
        raise RuntimeError("No input videos found")
