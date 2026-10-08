"""Sequence-level checks for bounded history and genuine value changes."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi_computer_vision.src.dmi.pipeline.frame_processor import process_frame
from dmi_computer_vision.src.dmi.temporal.smoothing import RightDisplayStabilizer, LeftWorkflowStabilizer
from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry


def content(value):
    return {"state": "Driver ID", "title": None, "buttons": {},
            "data_field": {"corners": [[10, 10], [110, 10], [110, 40], [10, 40]],
                           "bbox": [10, 10, 110, 40], "center": [60, 25],
                           "value": value}}


class TemporalSequenceTest(unittest.TestCase):
    def test_train_keypad_does_not_jump_when_perspective_quality_fluctuates(self):
        box = np.array([[0, 0], [600, 0], [600, 960], [0, 960]], np.float32)
        tracker = RightDisplayStabilizer()
        screen = content(None)
        screen.update(state="Train Data (1/2)", data_field=None)
        screen["buttons"] = {"digit_0": content(None)["data_field"]}
        # The UI and oriented box are steady; only an unreliable fitted corner
        # moves either side of the perspective-mapping fallback threshold.
        for offset in (0, 40, 80, 40, 80, 0):
            corners = box.copy()
            corners[0, 0] += offset
            geometry = DisplayGeometry(corners, box, (0, 0, 600, 960))
            result = tracker.update(screen, geometry)
            self.assertEqual(result["buttons"]["digit_0"]["center"], [60, 25])
        moved = box + [100, 50]
        screen["buttons"]["digit_0"]["corners"] = (
            np.array(screen["buttons"]["digit_0"]["corners"]) + [100, 50]
        ).tolist()
        result = tracker.update(screen, DisplayGeometry(moved, moved, (100, 50, 700, 1010)))
        self.assertEqual(result["buttons"]["digit_0"]["center"], [160, 75])

    def test_workflow_jitter_is_damped_but_camera_motion_is_followed(self):
        quad = np.array([[0, 0], [600, 0], [600, 960], [0, 960]], np.float32)
        geometry = DisplayGeometry(quad, quad, (0, 0, 600, 960))
        tracker = LeftWorkflowStabilizer()
        region = content(None)["data_field"]
        screen = {"title": {**region, "text": "Train data"}, "buttons": {"yes": region}}
        first = tracker.update("Train Data", screen, geometry)
        self.assertEqual(first["title"], screen["title"])
        shifted = {**region, "corners": (np.array(region["corners"]) + [4, 0]).tolist()}
        result = tracker.update("Train Data", {"title": None, "buttons": {"yes": shifted}}, geometry)
        self.assertLess(result["buttons"]["yes"]["center"][0], 64)
        self.assertGreaterEqual(result["buttons"]["yes"]["center"][0], 60)
        moved = DisplayGeometry(quad + [100, 50], quad + [100, 50], (100, 50, 700, 1010))
        shifted["corners"] = (np.array(region["corners"]) + [100, 50]).tolist()
        result = tracker.update("Train Data", {"title": None, "buttons": {"yes": shifted}}, moved)
        np.testing.assert_allclose(result["buttons"]["yes"]["center"], [160, 75], atol=1)

    def test_workflow_changes_and_missing_regions_drop_history(self):
        quad = np.array([[0, 0], [600, 0], [600, 960], [0, 960]], np.float32)
        geometry = DisplayGeometry(quad, quad, (0, 0, 600, 960))
        tracker = LeftWorkflowStabilizer()
        region = content(None)["data_field"]
        screen = {"title": None, "buttons": {"yes": region}}
        tracker.update("Train Data", screen, geometry)
        self.assertEqual(tracker.update("Train Data", {"title": None, "buttons": {}}, geometry)["buttons"], {})
        region["corners"] = (np.array(region["corners"]) + [20, 20]).tolist()
        self.assertEqual(tracker.update("Train Data", screen, geometry)["buttons"]["yes"]["center"], [80, 45])
        region["corners"] = (np.array(region["corners"]) + [20, 20]).tolist()
        self.assertEqual(tracker.update("Train Data (1/2)", screen, geometry)["buttons"]["yes"]["center"], [100, 65])

    def test_relocated_title_does_not_freeze_at_old_position(self):
        quad = np.array([[0, 0], [600, 0], [600, 960], [0, 960]], np.float32)
        geometry = DisplayGeometry(quad, quad, (0, 0, 600, 960))
        tracker = RightDisplayStabilizer()
        screen = content(None)
        screen["title"] = {**screen["data_field"], "text": "Driver ID"}
        tracker.update(screen, geometry)
        screen["title"]["corners"] = (np.array(screen["title"]["corners"]) + [0, 100]).tolist()
        self.assertEqual(tracker.update(screen, geometry)["title"]["center"], [60, 125])

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
