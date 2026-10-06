"""Check movement measurements do not invent continuity across missing data."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_validation import frame
from dmi.evaluation.baseline import read_recorded_frames, summarize_frames
from dmi.evaluation.recorded import validation_result


class BaselineTest(unittest.TestCase):
    def test_recorded_baselines_preserve_both_saved_formats(self):
        frames = [frame(), frame()]
        frames[1].update(frame_index=1, timestamp=1 / 30)
        with TemporaryDirectory() as directory:
            for name, text in (("results.json", json.dumps({"frames": frames})),
                               ("results_debug.jsonl", "\n".join(map(json.dumps, frames)))):
                path = Path(directory) / name
                path.write_text(text)
                self.assertEqual(read_recorded_frames(path), frames)

    def test_recorded_baseline_rejects_compact_live_and_incomplete_frames(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            for rows in ([], [{"type": "snapshot", "frame": 0, "state": {}}],
                         [{"type": "frame", "result": frame()}],
                         [{**frame(), "frame_index": False}],
                         [frame(), {**frame(), "frame_index": 2}]):
                path.write_text("\n".join(map(json.dumps, rows)))
                with self.assertRaises(ValueError):
                    read_recorded_frames(path)

    def test_invalid_baseline_requires_explicit_opt_in(self):
        def fail():
            raise ValueError("invalid polygon")
        with self.assertRaisesRegex(ValueError, "invalid polygon"):
            validation_result(fail)
        self.assertEqual(validation_result(fail, True), {"error": "invalid polygon"})
        self.assertEqual(validation_result(lambda: 42, True), 42)

    def test_movement_and_semantic_intervals(self):
        frames = [frame() for _ in range(3)]
        for index, item in enumerate(frames):
            item.update(frame_index=index, timestamp=index / 30)
            item["right_display"]["buttons"]["digit_1"]["center"] = [30 + 3 * index, 30 + 4 * index]
            item["left_display"]["buttons"] = {"yes": {"center": [30, 40 + index]}}
        frames[2]["right_display"]["data_field"]["value"] = "128"
        original = deepcopy(frames)
        result = summarize_frames(frames)
        self.assertEqual(result["center_movement_px"]["right.buttons.digit_1"],
                         {"adjacent_pairs": 2, "mean": 5., "p95": 5., "max": 5.})
        self.assertEqual(result["center_movement_px"]["left.buttons.yes"]["mean"], 1.)
        self.assertEqual([item["start_frame"] for item in result["semantic_intervals"]], [0, 2])
        self.assertEqual(frames, original)

    def test_missing_regions_state_changes_and_frame_gaps_are_not_bridged(self):
        frames = [frame() for _ in range(5)]
        for index, item in enumerate(frames):
            item.update(frame_index=index, timestamp=index / 30)
        frames[1]["right_display"]["buttons"] = {}
        frames[3]["right_display"]["state"] = "unknown"
        frames[4]["frame_index"] = 6
        result = summarize_frames(frames)
        self.assertNotIn("right.buttons.digit_1", result["center_movement_px"])
        with self.assertRaises(ValueError):
            summarize_frames([])
