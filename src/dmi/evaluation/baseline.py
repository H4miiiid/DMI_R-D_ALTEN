"""Summarize existing evaluation outputs without rerunning detection.

Movement is in source-image pixels between adjacent frames with the same
reported state. It includes camera motion and is not ground-truth jitter.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np


def regions(frame):
    for side in ("left", "right"):
        display = frame[f"{side}_display"]
        if display["geometry"] is not None:
            yield f"{side}.display", display["geometry"]
        collection = "boxes" if side == "left" else "buttons"
        for name, region in display[collection].items():
            yield f"{side}.{collection}.{name}", region
        for name in (("speed_indicator",) if side == "left" else ("title", "data_field")):
            if display[name] is not None:
                yield f"{side}.{name}", display[name]


def summarize_frames(frames):
    if not frames:
        raise ValueError("cannot summarize an empty recording")
    movement = defaultdict(list)
    states, titles, values, buttons = Counter(), Counter(), Counter(), Counter()
    intervals = []
    previous, previous_frame = {}, None
    for frame in frames:
        right = frame["right_display"]
        title = right["title"]["text"] if right["title"] else None
        value = right["data_field"]["value"] if right["data_field"] else None
        states[right["state"]] += 1
        titles[title] += 1
        values[value] += 1
        buttons.update(right["buttons"].keys())
        semantic = (right["state"], right["visibility"], title, value)
        if not intervals or semantic != intervals[-1]["semantic"]:
            intervals.append({"semantic": semantic, "start_frame": frame["frame_index"],
                              "start_seconds": frame["timestamp"]})
        intervals[-1]["end_frame"] = frame["frame_index"]
        intervals[-1]["end_seconds"] = frame["timestamp"]
        current = {name: np.asarray(region["center"], dtype=float)
                   for name, region in regions(frame)}
        if (previous_frame is not None
                and frame["frame_index"] == previous_frame["frame_index"] + 1
                and right["state"] == previous_frame["right_display"]["state"]
                and right["visibility"] == previous_frame["right_display"]["visibility"]):
            for name in current.keys() & previous.keys():
                movement[name].append(float(np.linalg.norm(current[name] - previous[name])))
        previous, previous_frame = current, frame
    return {
        "frames": len(frames), "state_frame_counts": dict(states),
        "title_frame_counts": [{"text": text, "frames": count} for text, count in titles.items()],
        "field_value_frame_counts": [{"value": value, "frames": count} for value, count in values.items()],
        "button_frame_counts": dict(buttons),
        "semantic_intervals": [
            {**{key: value for key, value in item.items() if key != "semantic"},
             **dict(zip(("state", "visibility", "title", "value"), item["semantic"]))}
            for item in intervals],
        "center_movement_px": {
            name: {"adjacent_pairs": len(values), "mean": float(np.mean(values)),
                   "p95": float(np.percentile(values, 95)), "max": max(values)}
            for name, values in sorted(movement.items())},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = json.loads((args.evaluation_dir / "verification.json").read_text())
    report = {"method": "Adjacent source-frame center distance; same reported state/visibility; "
              "no bridging missing regions. Includes physical motion. Predictions are not accuracy.",
              "videos": {}}
    for name, run in verification.items():
        directory = args.evaluation_dir / name
        path = directory / "results.jsonl"
        is_jsonl = path.exists()
        if is_jsonl:
            frames = [json.loads(line) for line in (directory / "results_debug.jsonl").read_text().splitlines()]
        else:
            path = directory / "results.json"
            frames = json.loads(path.read_text())["frames"]
        if len(frames) != run["frames"]:
            raise ValueError(f"verification frame count mismatch: {name}")
        summary = summarize_frames(frames)
        summary.update({
            "source_declared_frames": run["source_declared_frames"],
            "end_to_end_seconds": run["end_to_end_seconds"],
            "processed_fps": len(frames) / run["end_to_end_seconds"],
            "mean_end_to_end_ms_per_frame": 1000 * run["end_to_end_seconds"] / len(frames),
            "json_bytes": path.stat().st_size,
            "json_frame_records": run["compact"]["records"] - 2 if is_jsonl else len(frames),
            "json_top_level_documents": run["compact"]["records"] if is_jsonl else 1, "jsonl": is_jsonl,
            "compact": run.get("compact"),
            "json_bytes_per_frame": path.stat().st_size / len(frames),
            "baseline_available": run["baseline_available"],
            "changed_frame_count": (len(run["all_field_changed_frames"])
                                    if run["all_field_changed_frames"] is not None else None),
            "annotation_comparison": run["annotation_comparison"],
            "validation_errors": {key: value["error"] for key, value in run.items()
                                  if isinstance(value, dict) and "error" in value},
        })
        report["videos"][name] = summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(args.output)
