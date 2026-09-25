"""Sequence-level checks for bounded history and genuine value changes."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi.pipeline import process_frame
from dmi.temporal import RightDisplayStabilizer


def content(value):
    return {"state": "Driver ID", "title": None, "buttons": {},
            "data_field": {"corners": [[10, 10], [110, 10], [110, 40], [10, 40]],
                           "bbox": [10, 10, 110, 40], "center": [60, 25],
                           "value": value}}


class TemporalSequenceTest(unittest.TestCase):
    def test_brief_ocr_loss_is_stable_but_prolonged_loss_expires(self):
        tracker = RightDisplayStabilizer()
        tracker.update(content("12"))
        for _ in range(3):
            self.assertEqual(tracker.update(content(None))["data_field"]["value"], "12")
        for _ in range(10):
            self.assertIsNone(tracker.update(content(None))["data_field"]["value"])
        self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "235")

    def test_missing_observation_breaks_candidate_confirmation(self):
        tracker = RightDisplayStabilizer(confirmation_frames=3)
        tracker.update(content("12"))
        for value in ("235", "235", None, "235", "235"):
            self.assertEqual(tracker.update(content(value))["data_field"]["value"], "12")
        self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "235")

    def test_uncertain_state_also_breaks_ocr_confirmation(self):
        tracker = RightDisplayStabilizer(confirmation_frames=3)
        tracker.update(content("12"))
        tracker.update(content("235"))
        tracker.update(content("235"))
        tracker.update({"state": "unknown", "title": None,
                        "buttons": {}, "data_field": None})
        for _ in range(2):
            self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "12")
        self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "235")

    def test_genuine_change_confirms_at_the_documented_bound(self):
        tracker = RightDisplayStabilizer()
        tracker.update(content("12"))
        for _ in range(14):
            self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "12")
        self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "235")

    def test_field_removal_clears_history_immediately(self):
        tracker = RightDisplayStabilizer()
        tracker.update(content("12"))
        missing = content(None)
        missing["data_field"] = None
        self.assertIsNone(tracker.update(missing)["data_field"])
        self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "235")

    def test_display_loss_cannot_replay_old_content(self):
        tracker = RightDisplayStabilizer()
        tracker.update(content("12"))
        black = np.zeros((240, 640, 3), np.uint8)
        result = process_frame(black, 1, 1 / 30, right_display_stabilizer=tracker)
        self.assertEqual(result["right_display"], {
            "geometry": None, "visibility": "unknown", "state": "unknown", "title": None,
            "buttons": {}, "data_field": None})
        # Reacquisition is a fresh observation, not a vote against stale state.
        self.assertEqual(tracker.update(content("235"))["data_field"]["value"], "235")

    def test_reset_preserves_configuration_and_clears_all_history(self):
        tracker = RightDisplayStabilizer(confirmation_frames=2, max_missing_frames=1)
        tracker.update(content("12"))
        tracker.update(content("235"))
        tracker.reset()
        self.assertEqual(tracker.update(content("5"))["data_field"]["value"], "5")
        self.assertEqual(tracker.update(content(None))["data_field"]["value"], "5")
        self.assertIsNone(tracker.update(content(None))["data_field"]["value"])
        tracker.update(content("5"))
        self.assertEqual(tracker.update(content("6"))["data_field"]["value"], "5")
        self.assertEqual(tracker.update(content("6"))["data_field"]["value"], "6")


if __name__ == "__main__":
    unittest.main()
