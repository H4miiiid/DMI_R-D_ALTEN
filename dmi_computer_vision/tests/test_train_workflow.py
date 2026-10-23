"""End-to-end checks on representative train workflow screens."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dmi_computer_vision.src.dmi.pipeline.frame_processor import process_frame  # noqa: E402
from dmi_computer_vision.src.dmi.detection.right_layout import detect_button_quads  # noqa: E402
from dmi_computer_vision.src.dmi.detection.right_display import _recognize_train_buttons  # noqa: E402
from dmi_computer_vision.src.dmi.detection.left_display import _read_train_completion, _read_train_summary  # noqa: E402
from dmi_computer_vision.src.dmi.detection.display_geometry import detect_displays, rectify_display  # noqa: E402


class TrainWorkflowTest(unittest.TestCase):
    def test_completion_rejects_tall_or_collapsed_contours(self):
        frame = np.zeros((1280, 800, 3), np.uint8)
        for points in (np.float32([[0, 0], [20, 0], [20, 800], [0, 800]]),
                       np.zeros((4, 2), np.float32)):
            self.assertIsNone(_read_train_completion(frame, points))

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
        slanted = self.sample("validate_train_data.mp4", 0)
        self.assertIn("yes", slanted["left_display"]["buttons"])

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


@unittest.skipUnless((ROOT.parent / "runs/observation_08/annotated.mp4").exists(),
                     "Local SENSE recording is not shipped with the source")
class SenseTrainEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        capture = cv2.VideoCapture(str(ROOT.parent / "runs/observation_08/annotated.mp4"))
        ok, cls.frame = capture.read()
        capture.release()
        if not ok:
            raise RuntimeError("Cannot read the SENSE Train Data fixture")
        geometry = detect_displays(cls.frame)["right"]
        cls.right = rectify_display(cls.frame, geometry, (600, 960))
        cls.left = rectify_display(cls.frame, detect_displays(cls.frame)["left"], (800, 1280))

    def test_cold_start_reads_field_and_visible_navigation(self):
        result = process_frame(self.frame, 0, 0.)
        self.assertEqual(result["right_display"]["state"], "Train Data")
        self.assertEqual(result["right_display"]["data_field"]["value"], "Gamma")
        self.assertEqual(set(result["right_display"]["buttons"]),
                         {"gamma", "lambda", "close", "enter_data", "left_arrow", "right_arrow"})
        self.assertIn("yes", result["left_display"]["buttons"])
        self.assertEqual(result["left_display"]["summary"]["train_type"]["value"], "Gamma")
        # Visibility/recognition supplies no enabled-state assertion.
        self.assertNotIn("active", result["right_display"]["buttons"]["left_arrow"])

    def test_split_border_is_not_read_as_a_title_letter(self):
        capture = cv2.VideoCapture(str(ROOT.parent / "runs/observation_08/annotated.mp4"))
        capture.set(cv2.CAP_PROP_POS_FRAMES, 3)
        ok, frame = capture.read()
        capture.release()
        self.assertTrue(ok)
        result = process_frame(frame, 0, 0.)
        self.assertEqual(result["right_display"]["state"], "Train Data")
        self.assertEqual(result["left_display"]["title"]["text"], "Train data")

    def test_summary_changes_independently_and_omits_missing_or_duplicates(self):
        transform = np.eye(3, dtype=np.float64)
        original = _read_train_summary(self.left, transform)
        self.assertEqual(original["train_type"]["value"], "Gamma")
        changed = self.left.copy()
        changed[285:375, 480:735] = self.left[400, 500]
        cv2.putText(changed, "Lambda", (490, 345), cv2.FONT_HERSHEY_SIMPLEX,
                    1., (230, 230, 230), 2, cv2.LINE_AA)
        self.assertEqual(_read_train_summary(changed, transform)["train_type"]["value"], "Lambda")
        blank = self.left.copy()
        blank[280:390, 250:750] = self.left[400, 500]
        self.assertEqual(_read_train_summary(blank, transform), {})
        duplicate = self.left.copy()
        duplicate[480:590] = self.left[280:390]
        self.assertEqual(_read_train_summary(duplicate, transform), {})

    def test_choices_follow_glyphs_when_swapped(self):
        changed = self.right.copy()
        changed[450:515, 20:180] = self.right[450:515, 220:380]
        changed[450:515, 220:380] = self.right[450:515, 20:180]
        buttons = _recognize_train_buttons(changed)
        self.assertGreater(buttons["gamma"][:, 0].mean(), buttons["lambda"][:, 0].mean())

    def test_duplicate_or_blank_choices_are_omitted(self):
        duplicate = self.right.copy()
        duplicate[450:515, 220:380] = self.right[450:515, 20:180]
        self.assertNotIn("gamma", _recognize_train_buttons(duplicate))
        blank = self.right.copy()
        blank[450:515, 20:380] = self.right[400, 100]
        buttons = _recognize_train_buttons(blank)
        self.assertNotIn("gamma", buttons)
        self.assertNotIn("lambda", buttons)

    def test_missing_choice_border_does_not_use_monitor_border(self):
        changed = self.right.copy()
        erased = np.zeros(changed.shape[:2], np.uint8)
        erased[520:545, :420] = 255
        changed = cv2.inpaint(changed, erased, 7, cv2.INPAINT_TELEA)
        buttons = _recognize_train_buttons(changed)
        self.assertNotIn("gamma", buttons)
        self.assertNotIn("lambda", buttons)


if __name__ == "__main__":
    unittest.main()
