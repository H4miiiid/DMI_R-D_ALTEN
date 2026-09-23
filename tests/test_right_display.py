from __future__ import annotations

from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.geometry import DisplayGeometry  # noqa: E402
from dmi.pipeline import annotate_frame  # noqa: E402
from dmi.right_display import analyze_right_display  # noqa: E402
from dmi.right_layout import detect_button_quads, detect_title_quad  # noqa: E402
from dmi.temporal import RightDisplayStabilizer  # noqa: E402


class RightDisplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.geometry = DisplayGeometry(
            corners=np.array(
                [[0, 0], [599, 0], [599, 959], [0, 959]], dtype=np.float32
            ),
            oriented_box=np.array(
                [[0, 0], [599, 0], [599, 959], [0, 959]], dtype=np.float32
            ),
            bounding_box=(0, 0, 599, 959),
        )

    def test_recognizes_driver_id_structure_and_digits(self) -> None:
        frame = self._base_screen("Driver ID")
        cv2.rectangle(frame, (0, 190), (560, 290), (240, 245, 235), -1)
        cv2.putText(
            frame, "12", (8, 255), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
            (100, 100, 100), 2, cv2.LINE_AA,
        )

        result = analyze_right_display(frame, self.geometry)

        self.assertEqual(result["state"], "Driver ID")
        self.assertEqual(result["title"]["text"], "Driver ID")
        self.assertEqual(result["data_field"]["value"], "12")
        self.assertEqual(len(result["buttons"]), 16)
        self.assertIn("empty_action", result["buttons"])
        self.assertEqual(len(result["buttons"]["trn"]["corners"]), 4)

        frame_result = {
            "frame_index": 0,
            "timestamp": 0.0,
            "right_display": {"geometry": self.geometry.as_result(), **result},
            "left_display": {"geometry": None, "boxes": {}, "speed_indicator": None},
        }
        annotated = annotate_frame(frame, frame_result)
        self.assertEqual(annotated.shape, frame.shape)

    def test_recognizes_main_structure_without_data_field(self) -> None:
        frame = self._base_screen("Main")

        result = analyze_right_display(frame, self.geometry)

        self.assertEqual(result["state"], "Main")
        self.assertIsNone(result["data_field"])
        self.assertEqual(len(result["buttons"]), 11)
        self.assertIn("empty_driver_id", result["buttons"])

    def test_debounces_single_frame_ocr_noise(self) -> None:
        stabilizer = RightDisplayStabilizer(confirmation_frames=3)

        first = stabilizer.update(self._content("235"))
        noisy = stabilizer.update(self._content("275"))

        self.assertEqual(first["data_field"]["value"], "235")
        self.assertEqual(noisy["data_field"]["value"], "235")

    def test_debounces_short_unknown_state_occlusion(self) -> None:
        stabilizer = RightDisplayStabilizer(state_confirmation_frames=3)
        stabilizer.update(self._content("12"))
        unknown = {
            "state": "unknown",
            "title": None,
            "buttons": {},
            "data_field": None,
        }

        first = stabilizer.update(unknown)
        second = stabilizer.update(unknown)
        confirmed = stabilizer.update(unknown)

        self.assertEqual(first["state"], "Driver ID")
        self.assertEqual(second["state"], "Driver ID")
        self.assertEqual(confirmed["state"], "unknown")

    def test_stabilizes_detected_region_corners(self) -> None:
        stabilizer = RightDisplayStabilizer(confirmation_frames=3)
        first = self._content("12")
        first["buttons"] = {"digit_1": self._region(0)}
        shifted = self._content("12")
        shifted["buttons"] = {"digit_1": self._region(40)}

        stabilizer.update(first)
        result = stabilizer.update(shifted)

        self.assertEqual(result["buttons"]["digit_1"]["center"], [8, 5])

    def test_region_smoothing_follows_display_motion_without_center_jitter(self) -> None:
        stabilizer = RightDisplayStabilizer()
        first = self._content("12")
        first["buttons"] = {"digit_1": self._region(0)}
        stabilizer.update(first, self.geometry)
        moved_geometry = DisplayGeometry(
            corners=self.geometry.corners + np.array([100, 50], dtype=np.float32),
            oriented_box=self.geometry.oriented_box
            + np.array([100, 50], dtype=np.float32),
            bounding_box=(100, 50, 699, 1009),
        )
        moved = self._content("12")
        moved["buttons"] = {"digit_1": self._region(104)}
        moved["buttons"]["digit_1"]["corners"] = [
            [104, 50], [114, 50], [114, 60], [104, 60]
        ]

        result = stabilizer.update(moved, moved_geometry)

        self.assertEqual(result["buttons"]["digit_1"]["center"], [105, 55])

    def test_relative_outlier_cannot_drag_button_from_fixed_layout(self) -> None:
        stabilizer = RightDisplayStabilizer()
        first = self._content("12")
        first["buttons"] = {"digit_1": self._region(0)}
        shifted = self._content("12")
        shifted["buttons"] = {"digit_1": self._region(100)}

        stabilizer.update(first, self.geometry)
        result = stabilizer.update(shifted, self.geometry)

        self.assertEqual(result["buttons"]["digit_1"]["center"], [5, 5])

    def test_corrupt_perspective_falls_back_to_stable_display_motion(self) -> None:
        stabilizer = RightDisplayStabilizer()
        first = self._content("12")
        first["buttons"] = {"digit_1": self._region(0)}
        stabilizer.update(first, self.geometry)
        shifted_box = self.geometry.oriented_box + np.array(
            [100, 50], dtype=np.float32
        )
        corrupt_corners = self.geometry.corners + np.array(
            [100, 50], dtype=np.float32
        )
        corrupt_corners[2, 0] -= 250
        corrupt_geometry = DisplayGeometry(
            corners=corrupt_corners,
            oriented_box=shifted_box,
            bounding_box=(100, 50, 699, 1009),
        )
        corrupt = self._content("12")
        corrupt["buttons"] = {"digit_1": self._region(100)}

        result = stabilizer.update(corrupt, corrupt_geometry)

        self.assertEqual(result["buttons"]["digit_1"]["center"], [105, 55])

    def test_button_grid_follows_dominant_rotated_borders(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        slope = 0.18
        for expected_y in (480, 571, 662, 754, 845, 946):
            cv2.line(
                frame,
                (0, round(expected_y - slope * 300)),
                (599, round(expected_y + slope * 299)),
                (110, 50, 8),
                3,
            )
        for expected_x in (0, 186, 282, 372, 444, 558):
            cv2.line(frame, (expected_x, 440), (expected_x, 959), (110, 50, 8), 3)
        cv2.line(frame, (0, 900), (599, 700), (30, 80, 130), 8)

        buttons = detect_button_quads(frame, "Driver ID")
        top = buttons["digit_1"][1] - buttons["digit_1"][0]

        self.assertGreater(float(top[1] / top[0]), 0.12)
        self.assertLess(float(top[1] / top[0]), 0.24)

    def test_main_grid_prefers_full_border_over_nearby_short_edge(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        for y in (185, 272, 366, 453, 542, 633):
            cv2.line(frame, (0, y), (550, y), (110, 50, 8), 3)
        for x in (0, 286, 550):
            cv2.line(frame, (x, 185), (x, 633), (110, 50, 8), 3)
        # A shorter blue edge lies closer to the nominal bottom-row prior,
        # but it is not the border spanning the full Main grid.
        cv2.line(frame, (120, 603), (330, 603), (110, 50, 8), 3)

        buttons = detect_button_quads(frame, "Main")
        bottom = buttons["radio_data"][2:]

        self.assertGreater(float(bottom[:, 1].mean()), 625)

    def test_main_grid_preserves_each_detected_border_slope(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        row_edges = (
            ((0, 190), (550, 180)),
            ((0, 280), (550, 260)),
            ((0, 380), (550, 350)),
            ((0, 480), (550, 440)),
            ((0, 580), (550, 530)),
            ((0, 680), (550, 620)),
        )
        for start, end in row_edges:
            cv2.line(frame, start, end, (110, 50, 8), 3)
        for x in (0, 275, 550):
            cv2.line(frame, (x, 175), (x, 690), (110, 50, 8), 3)

        buttons = detect_button_quads(frame, "Main")
        start = buttons["start"]
        top_slope = float(
            (start[1, 1] - start[0, 1]) / (start[1, 0] - start[0, 0])
        )
        bottom_slope = float(
            (start[2, 1] - start[3, 1]) / (start[2, 0] - start[3, 0])
        )

        self.assertAlmostEqual(top_slope, -10 / 550, delta=0.015)
        self.assertAlmostEqual(bottom_slope, -20 / 550, delta=0.015)
        self.assertGreater(abs(bottom_slope - top_slope), 0.01)

    def test_main_close_uses_button_bottom_not_display_bottom(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        # The standalone X button ends at y=905, while a longer display border
        # below it must not be mistaken for the button's lower edge.
        cv2.rectangle(frame, (0, 816), (155, 905), (110, 50, 8), 3)
        cv2.line(frame, (0, 934), (550, 934), (110, 50, 8), 3)

        close = detect_button_quads(frame, "Main")["close"]

        self.assertLess(float(close[2:, 1].mean()), 915)
        self.assertGreater(float(close[2:, 1].mean()), 895)

    def test_driver_grid_infers_occluded_borders_from_visible_topology(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        for y in (450, 542, 634):
            cv2.line(frame, (5, y), (585, y), (110, 50, 8), 3)
        for x in (5, 205, 585):
            cv2.line(frame, (x, 450), (x, 910), (110, 50, 8), 3)

        buttons = detect_button_quads(frame, "Driver ID")

        self.assertAlmostEqual(float(buttons["digit_1"][:2, 1].mean()), 450, delta=6)
        self.assertAlmostEqual(float(buttons["digit_1"][2:, 1].mean()), 542, delta=6)
        self.assertGreater(float(buttons["cancel"][2:, 1].mean()), 895)
        self.assertGreater(float(buttons["digit_2"][:, 0].max()), 385)

    def test_driver_action_row_uses_its_own_button_boundaries(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        for y in (480, 570, 660, 750, 840, 958):
            cv2.line(frame, (0, y), (550, y), (110, 50, 8), 3)
        for x in (0, 183, 366, 550):
            cv2.line(frame, (x, 480), (x, 840), (110, 50, 8), 3)
        for x in (0, 145, 254, 399, 550):
            cv2.line(frame, (x, 840), (x, 958), (110, 50, 8), 3)

        buttons = detect_button_quads(frame, "Driver ID")

        self.assertAlmostEqual(float(buttons["cancel"][:, 0].max()), 145, delta=7)
        self.assertAlmostEqual(float(buttons["trn"][:, 0].min()), 254, delta=7)
        self.assertAlmostEqual(float(buttons["settings"][:, 0].min()), 399, delta=7)
        self.assertAlmostEqual(float(buttons["cancel"][:, 1].max()), 930, delta=7)

    def test_level_close_uses_its_separate_visible_button_edges(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        for y in (470, 560, 650, 745, 838, 958):
            cv2.line(frame, (0, y), (565, y), (110, 50, 8), 3)
        for x in (0, 182, 368, 565):
            cv2.line(frame, (x, 470), (x, 838), (110, 50, 8), 3)
        cv2.line(frame, (145, 838), (145, 958), (110, 50, 8), 3)

        buttons = detect_button_quads(frame, "Level")
        close = buttons["close"]
        more = buttons["more"]

        self.assertAlmostEqual(float(close[:2, 1].mean()), 838, delta=7)
        self.assertAlmostEqual(float(close[2:, 1].mean()), 928, delta=7)
        self.assertAlmostEqual(
            float(close[:2, 1].mean()), float(more[2:, 1].mean()), delta=3
        )
        self.assertAlmostEqual(float(close[:, 0].max()), 145, delta=7)

    def test_known_layout_relocks_to_common_zoom_from_multiple_buttons(self) -> None:
        stabilizer = RightDisplayStabilizer()
        first = self._content("12")
        first["buttons"] = {
            "digit_1": self._box_region(60, 400, 160, 480),
            "digit_2": self._box_region(240, 400, 340, 480),
            "digit_4": self._box_region(60, 520, 160, 600),
        }
        stabilizer.update(first, self.geometry)
        zoomed = self._content("12")
        zoomed["buttons"] = {
            name: self._transform_region(region, 1.04, -12, -15)
            for name, region in first["buttons"].items()
        }

        result = stabilizer.update(zoomed, self.geometry)

        self.assertLess(result["buttons"]["digit_1"]["center"][0], 108)
        self.assertGreater(result["buttons"]["digit_1"]["center"][1], 440)

    def test_large_coherent_occlusion_outlier_does_not_move_layout(self) -> None:
        stabilizer = RightDisplayStabilizer()
        first = self._content("12")
        first["buttons"] = {
            "digit_1": self._box_region(60, 400, 160, 480),
            "digit_2": self._box_region(240, 400, 340, 480),
            "digit_4": self._box_region(60, 520, 160, 600),
        }
        stabilizer.update(first, self.geometry)
        occluded = self._content("12")
        occluded["buttons"] = {
            name: self._transform_region(region, 0.82, 70, 90)
            for name, region in first["buttons"].items()
        }

        result = stabilizer.update(occluded, self.geometry)

        self.assertEqual(result["buttons"]["digit_1"]["center"], [110, 440])

    def test_title_tracks_local_field_motion_more_smoothly_than_raw_detection(self) -> None:
        stabilizer = RightDisplayStabilizer()
        first = self._content("12")
        first["title"] = {**self._box_region(20, 80, 520, 130), "text": "Driver ID"}
        first["data_field"] = {
            **self._box_region(20, 180, 520, 270),
            "value": "12",
        }
        stabilizer.update(first, self.geometry)
        shifted = self._content("12")
        shifted["title"] = {
            **self._box_region(32, 92, 532, 142),
            "text": "Driver ID",
        }
        shifted["data_field"] = {
            **self._box_region(32, 192, 532, 282),
            "value": "12",
        }

        result = stabilizer.update(shifted, self.geometry)

        self.assertGreater(result["title"]["center"][0], 270)
        self.assertLess(result["title"]["center"][0], 282)
        self.assertGreater(result["title"]["center"][1], 105)
        self.assertLess(result["title"]["center"][1], 117)

    def test_title_uses_its_local_sloped_band_edges_at_the_right_side(self) -> None:
        frame = np.full((960, 600, 3), (7, 5, 2), dtype=np.uint8)
        border_color = (45, 18, 4)
        cv2.fillConvexPoly(
            frame,
            np.array([[0, 50], [550, 70], [550, 100], [0, 80]]),
            border_color,
        )
        cv2.fillConvexPoly(
            frame,
            np.array([[0, 125], [550, 145], [550, 185], [0, 165]]),
            border_color,
        )

        title = detect_title_quad(frame, (5, 85, 120, 120))

        self.assertAlmostEqual(float(title[1, 0]), 550, delta=7)
        self.assertAlmostEqual(float(title[2, 0]), 550, delta=7)
        self.assertAlmostEqual(float(title[1, 1]), 100, delta=4)
        self.assertAlmostEqual(float(title[2, 1]), 145, delta=4)

    def test_unknown_screen_keeps_supported_bordered_buttons(self) -> None:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        cv2.putText(
            frame, "Other", (8, 145), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
            (255, 255, 255), 2, cv2.LINE_AA,
        )
        cv2.rectangle(frame, (20, 400), (200, 500), (110, 50, 8), 3)
        cv2.rectangle(frame, (200, 400), (380, 500), (110, 50, 8), 3)

        result = analyze_right_display(frame, self.geometry)
        buttons = result["buttons"]

        self.assertEqual(result["state"], "unknown")
        self.assertIsNotNone(result["title"])
        self.assertIsNone(result["title"]["text"])
        self.assertEqual(set(buttons), {"button_1", "button_2"})
        self.assertLess(buttons["button_1"]["center"][0], 200)
        self.assertGreater(buttons["button_2"]["center"][0], 200)

    @staticmethod
    def _base_screen(title: str) -> np.ndarray:
        frame = np.full((960, 600, 3), (45, 18, 4), dtype=np.uint8)
        cv2.putText(
            frame, title, (8, 145), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
            (255, 255, 255), 2, cv2.LINE_AA,
        )
        if title == "Main":
            for y in (181, 263, 354, 436, 522, 609):
                cv2.line(frame, (0, y), (550, y), (110, 50, 8), 3)
            for x in (0, 272, 550):
                cv2.line(frame, (x, 181), (x, 609), (110, 50, 8), 3)
        elif title == "Driver ID":
            for y in (480, 571, 662, 754, 845, 946):
                cv2.line(frame, (0, y), (558, y), (110, 50, 8), 3)
            for x in (0, 186, 282, 372, 444, 558):
                cv2.line(frame, (x, 480), (x, 946), (110, 50, 8), 3)
        return frame

    @staticmethod
    def _content(value: str) -> dict:
        return {
            "state": "Driver ID",
            "title": None,
            "buttons": {},
            "data_field": {
                **RightDisplayTest._region(0),
                "value": value,
            },
        }

    @staticmethod
    def _region(x_offset: int) -> dict:
        return {
            "corners": [
                [x_offset, 0],
                [x_offset + 10, 0],
                [x_offset + 10, 10],
                [x_offset, 10],
            ],
            "bbox": [x_offset, 0, x_offset + 10, 10],
            "center": [x_offset + 5, 5],
        }

    @staticmethod
    def _box_region(x1: int, y1: int, x2: int, y2: int) -> dict:
        return {
            "corners": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            "bbox": [x1, y1, x2, y2],
            "center": [(x1 + x2) // 2, (y1 + y2) // 2],
        }

    @staticmethod
    def _transform_region(
        region: dict, scale: float, x_offset: float, y_offset: float
    ) -> dict:
        corners = np.asarray(region["corners"], dtype=np.float32)
        corners = corners * scale + np.array([x_offset, y_offset])
        x1, y1 = np.floor(corners.min(axis=0)).astype(int)
        x2, y2 = np.ceil(corners.max(axis=0)).astype(int)
        return {
            "corners": np.rint(corners).astype(int).tolist(),
            "bbox": [x1, y1, x2, y2],
            "center": np.rint(corners.mean(axis=0)).astype(int).tolist(),
        }


if __name__ == "__main__":
    unittest.main()
