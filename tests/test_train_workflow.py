"""End-to-end checks on representative train workflow screens."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dmi.pipeline.frame_processor import process_frame  # noqa: E402
from dmi.detection.right_layout import detect_button_quads  # noqa: E402


class TrainWorkflowTest(unittest.TestCase):
    def test_shifted_train_grids_keep_complete_rows(self):
        frame = np.zeros((960, 600, 3), np.uint8)
        for state, rows, bottom_name in (
            ("Train Data (1/2)", (.485, .578, .671, .765, .859), "digit_0"),
            ("Train Data (2/2)", (.459, .548, .637), "out_of_gc"),
        ):
            for shift in (35, 60):
                with self.subTest(state=state, shift=shift):
                    vertical = [(0., x * 600 + 8, 250.)
                                for x in (0., .305, .61, .92)]
                    horizontal = [(0., y * 960 + shift, 400.) for y in rows]
                    buttons = detect_button_quads(frame, state, (horizontal, vertical))
                    bottom = buttons[bottom_name]
                    self.assertAlmostEqual(float(bottom[2, 1]), rows[-1] * 960 + shift, delta=2)
                    self.assertAlmostEqual(float(bottom[0, 1]), rows[-2] * 960 + shift, delta=2)
                    self.assertGreater(float(bottom[2, 1] - bottom[0, 1]), 80)
                    if state == "Train Data (1/2)":
                        self.assertAlmostEqual(float(buttons["close"][0, 1]),
                                               float(bottom[2, 1]), delta=2)

    def test_validation_controls_follow_moving_borders(self):
        frame = np.zeros((960, 600, 3), np.uint8)
        vertical = [(0.0, x, length) for x, length in
                    ((0, 90), (182, 90), (365, 90), (153, 90), (552, 900))]
        for offset in (0, -60):
            horizontal = [(0.0, y + offset, length) for y, length in
                          ((650, 365), (740, 365), (830, 153), (920, 153))]
            buttons = detect_button_quads(frame, "Validate Train Data",
                                          (horizontal, vertical))
            for name, center in (("no", (91, 695 + offset)),
                                 ("yes", (273.5, 695 + offset)),
                                 ("close", (76.5, 875 + offset))):
                np.testing.assert_allclose(buttons[name].mean(axis=0), center, atol=2)

    def sample(self, video: str, index: int):
        capture = cv2.VideoCapture(str(ROOT / "data/videos/dev" / video))
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            for _ in range(index + 1):
                ok, frame = capture.read()
                if not ok:
                    break
        fps = capture.get(cv2.CAP_PROP_FPS)
        capture.release()
        self.assertTrue(ok)
        return process_frame(frame, index, index / fps)

    def test_train_type_and_confirmation_values(self):
        selected = self.sample("train_data_gamma.mp4", 0)
        self.assertEqual(selected["right_display"]["state"], "Train Data")
        self.assertEqual(selected["right_display"]["data_field"]["value"], "Gamma")
        self.assertEqual(set(selected["right_display"]["buttons"]),
                         {"gamma", "lambda", "close", "enter_data"})
        self.assertEqual(selected["left_display"]["title"]["text"], "Train data")
        self.assertIn("yes", selected["left_display"]["buttons"])

        confirmed = self.sample("validate_train_data.mp4", 438)
        self.assertEqual(confirmed["right_display"]["state"], "Validate Train Data")
        self.assertEqual(confirmed["right_display"]["data_field"]["value"], "Yes")
        self.assertEqual(set(confirmed["right_display"]["buttons"]),
                         {"no", "yes", "close"})

        final = self.sample("validate_train_data.mp4", 572)
        self.assertEqual(final["right_display"]["state"], "Validate Train Data")
        self.assertEqual(final["right_display"]["data_field"]["value"], "Yes")
        self.assertEqual(set(final["right_display"]["buttons"]),
                         {"no", "yes", "close"})

    def test_train_data_pages_keep_navigation_separate(self):
        first = self.sample("train_data_gamma.mp4", 511)
        second = self.sample("train_data_gamma.mp4", 767)
        self.assertEqual(first["right_display"]["state"], "Train Data (1/2)")
        self.assertEqual(second["right_display"]["state"], "Train Data (2/2)")
        self.assertIsNone(first["right_display"]["title"])
        self.assertIsNone(first["right_display"]["data_field"])
        self.assertIsNone(second["right_display"]["title"])
        self.assertIsNone(second["right_display"]["data_field"])
        self.assertIn("digit_1", first["right_display"]["buttons"])
        self.assertTrue({"g1", "ga", "gb", "gc", "out_of_gc"} <=
                        second["right_display"]["buttons"].keys())
        for result in (first, second):
            buttons = result["right_display"]["buttons"]
            self.assertTrue({"close", "left_arrow", "right_arrow", "select_type"}
                            <= buttons.keys())
            self.assertGreater(buttons["close"]["center"][1],
                               buttons.get("digit_1", buttons.get("g1"))["center"][1])
            self.assertIn("yes", result["left_display"]["buttons"])

    def test_running_number_reads_dynamic_input_and_keypad(self):
        result = self.sample("train_numbers.mp4", 755)["right_display"]
        self.assertEqual(result["state"], "Train Running Number")
        self.assertEqual(result["title"]["text"], "Train running number")
        self.assertEqual(result["data_field"]["value"], "128")
        self.assertEqual(len(result["buttons"]), 13)
        self.assertIn("close", result["buttons"])


if __name__ == "__main__":
    unittest.main()
