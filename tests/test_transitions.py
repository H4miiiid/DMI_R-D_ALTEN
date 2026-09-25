"""Transition semantics and evidence checks without reference-frame geometry."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi.geometry import DisplayGeometry
from dmi.right_display import analyze_right_display
from dmi.right_layout import detect_button_quads
from dmi.temporal import RightDisplayStabilizer


def region(x):
    return {"corners": [[x, 20], [x+40, 20], [x+40, 50], [x, 50]],
            "bbox": [x, 20, x+40, 50], "center": [x+20, 35]}


def screen(state, x=0, value=None):
    return {"state": state, "title": {**region(x), "text": state},
            "buttons": {"action": region(x+50)},
            "data_field": {**region(x+100), "value": value}
            if state in {"Driver ID", "Level"} else None}


class TransitionTest(unittest.TestCase):
    def test_pending_new_screen_uses_current_geometry_and_neutral_semantics(self):
        tracker = RightDisplayStabilizer()
        tracker.update(screen("Driver ID", value="235"))
        for i in range(4):
            current = screen("Level", x=80+i*5, value="Level 0")
            original = deepcopy(current)
            result = tracker.update(current)
            self.assertEqual(current, original)
            self.assertEqual(result["state"], "unknown")
            self.assertIsNone(result["title"]["text"])
            self.assertIsNone(result["data_field"]["value"])
            self.assertEqual(result["buttons"], {"button_1": current["buttons"]["action"]})
            self.assertEqual(result["title"]["corners"], current["title"]["corners"])
        result = tracker.update(screen("Level", x=100, value="Level 0"))
        self.assertEqual(result["state"], "Level")
        self.assertEqual(result["data_field"]["value"], "Level 0")
        self.assertEqual(result["title"]["corners"], region(100)["corners"])

    def test_disappearing_field_is_not_replayed_during_level_to_main(self):
        tracker = RightDisplayStabilizer()
        tracker.update(screen("Level", value="Level 0"))
        for _ in range(4):
            result = tracker.update(screen("Main", x=200))
            self.assertIsNone(result["data_field"])
            self.assertEqual(result["state"], "unknown")
        self.assertEqual(tracker.update(screen("Main", x=200))["state"], "Main")

    def test_unknown_candidate_keeps_current_elements_without_old_coordinates(self):
        tracker = RightDisplayStabilizer(state_confirmation_frames=3)
        tracker.update(screen("Driver ID", value="12"))
        unknown = screen("unknown", x=300)
        for _ in range(2):
            result = tracker.update(unknown)
            self.assertEqual(result["state"], "Driver ID")
            self.assertEqual(result["buttons"]["button_1"]["corners"], region(350)["corners"])
            self.assertIsNone(result["data_field"])
        self.assertEqual(tracker.update(unknown)["state"], "unknown")

    def test_interrupted_state_candidate_does_not_accumulate_confirmation(self):
        tracker = RightDisplayStabilizer(state_confirmation_frames=3)
        tracker.update(screen("Level", value="Level 0"))
        tracker.update(screen("Main"))
        tracker.update(screen("Main"))
        self.assertEqual(tracker.update(screen("Level", value="Level 0"))["state"], "Level")
        for _ in range(2):
            self.assertEqual(tracker.update(screen("Main"))["state"], "unknown")
        self.assertEqual(tracker.update(screen("Main"))["state"], "Main")

    def test_uncertain_frame_during_transition_cannot_flash_the_old_state(self):
        tracker = RightDisplayStabilizer()
        tracker.update(screen("Level", value="Level 0"))
        self.assertEqual(tracker.update(screen("Main"))["state"], "unknown")
        self.assertEqual(tracker.update(screen("unknown"))["state"], "unknown")
        for _ in range(4):
            self.assertEqual(tracker.update(screen("Main"))["state"], "unknown")
        self.assertEqual(tracker.update(screen("Main"))["state"], "Main")

    def test_reacquired_screen_does_not_seed_a_noisy_single_frame_value(self):
        tracker = RightDisplayStabilizer(confirmation_frames=3, state_confirmation_frames=3)
        tracker.update(screen("Driver ID", value="235"))
        for _ in range(3):
            tracker.update(screen("unknown"))
        for value in ("7", "3", "2"):
            result = tracker.update(screen("Driver ID", value=value))
            self.assertIsNone(result["data_field"]["value"])
        for _ in range(2):
            self.assertIsNone(tracker.update(screen("Driver ID", value="235"))["data_field"]["value"])
        self.assertEqual(tracker.update(screen("Driver ID", value="235"))["data_field"]["value"], "235")

    def test_blue_background_cannot_support_extrapolated_button_borders(self):
        image = np.full((960, 600, 3), (45, 18, 4), np.uint8)
        lines = ([(0., 400., 400.), (0., 500., 400.)],
                 [(0., 20., 200.), (0., 200., 200.)])
        self.assertEqual(detect_button_quads(image, "unknown", lines), {})
        cv2.rectangle(image, (20, 400), (200, 500), (110, 50, 8), 3)
        self.assertEqual(len(detect_button_quads(image, "unknown", lines)), 1)

    def test_crossed_title_border_is_omitted(self):
        image = np.zeros((960, 600, 3), np.uint8)
        q = np.array([[0, 0], [599, 0], [599, 959], [0, 959]], np.float32)
        crossed = np.array([[0, 30], [550, 60], [550, 40], [0, 80]], np.float32)
        geometry = DisplayGeometry(q, q.copy(), (0, 0, 599, 959))
        with patch("dmi.right_display._detect_title_box", return_value=(10, 30, 80, 60)), patch("dmi.right_display.detect_title_quad", return_value=crossed):
            self.assertIsNone(analyze_right_display(image, geometry)["title"])

    def test_unknown_screen_preserves_visible_field_without_invented_value(self):
        image = np.full((960, 600, 3), (45, 18, 4), np.uint8)
        cv2.rectangle(image, (15, 200), (565, 280), (240, 240, 240), -1)
        q = np.array([[0, 0], [599, 0], [599, 959], [0, 959]], np.float32)
        geometry = DisplayGeometry(q, q.copy(), (0, 0, 599, 959))
        result = analyze_right_display(image, geometry)
        self.assertEqual(result["state"], "unknown")
        self.assertIsNotNone(result["data_field"])
        self.assertIsNone(result["data_field"]["value"])


if __name__ == "__main__":
    unittest.main()
