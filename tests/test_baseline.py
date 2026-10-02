"""Check movement measurements do not invent continuity across missing data."""
from copy import deepcopy
import unittest

from test_validation import frame
from dmi.evaluation.baseline import summarize_frames
from dmi.evaluation.recorded import validation_result


class BaselineTest(unittest.TestCase):
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
        frames[2]["right_display"]["data_field"]["value"] = "128"
        original = deepcopy(frames)
        result = summarize_frames(frames)
        self.assertEqual(result["center_movement_px"]["right.buttons.digit_1"],
                         {"adjacent_pairs": 2, "mean": 5., "p95": 5., "max": 5.})
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
