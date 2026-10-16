"""Evidence-based division, perspective mapping and conservative rejection."""
from __future__ import annotations

import unittest

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.display_geometry import (
    _connected_division, detect_displays, rectify_display,
)


def monitor(split: float = .54, *, field: bool = True, grid: bool = True) -> np.ndarray:
    image = np.full((660, 900, 3), (90, 45, 10), np.uint8)
    x = round(split * 900)
    cv2.circle(image, (180, 200), 90, (190, 200, 190), 3)
    if field:
        cv2.rectangle(image, (x, 80), (885, 145), (235, 225, 180), -1)
    if grid:
        for column in range(4):
            boundary = round(x + (885 - x) * column / 3)
            cv2.line(image, (boundary, 330), (boundary, 625), (180, 45, 5), 3)
        for row in range(6):
            y = round(330 + 295 * row / 5)
            cv2.line(image, (x, y), (885, y), (180, 45, 5), 3)
    return image


def perspective(image: np.ndarray, quad: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    if quad is None:
        quad = np.array([[140, 80], [1090, 130], [1060, 830], [100, 790]], np.float32)
    source = np.array([[0, 0], [899, 0], [899, 659], [0, 659]], np.float32)
    transform = cv2.getPerspectiveTransform(source, quad)
    frame = cv2.warpPerspective(image, transform, (1280, 900))
    return frame, transform


def menu(split: float = .54, *, rows: int = 5) -> np.ndarray:
    image = monitor(split, field=False, grid=False)
    left, right = round(split * 900), 885
    for column in range(3):
        x = round(left + (right - left) * column / 2)
        cv2.line(image, (x, 100), (x, 450), (180, 45, 5), 3)
    for row in range(rows + 1):
        y = round(100 + row * 350 / rows)
        cv2.line(image, (left, y), (right, y), (180, 45, 5), 3)
    return image


class ConnectedGeometryTest(unittest.TestCase):
    def test_menu_localization_requires_no_field_or_ocr_title(self):
        for fraction in (.44, .54):
            with self.subTest(fraction=fraction):
                frame, transform = perspective(menu(fraction))
                geometry = detect_displays(frame)["right"]
                self.assertIsNotNone(geometry)
                expected = cv2.perspectiveTransform(np.array([[[round(900 * fraction), 0],
                                                               [round(900 * fraction), 659]]], np.float32), transform)[0]
                np.testing.assert_allclose(geometry.corners[[0, 3]], expected, atol=8)

    def test_menu_needs_repeated_row_borders_and_a_supported_internal_column(self):
        image = menu()
        x = round((.54 * 900 + 885) / 2)
        image[95:455, x - 6:x + 7] = (90, 45, 10)
        for unsupported in (menu(rows=2), image):
            with self.subTest():
                frame, _ = perspective(unsupported)
                self.assertEqual(detect_displays(frame), {"left": None, "right": None})

    def test_conflicting_menu_divisions_are_rejected(self):
        image = menu(.44)
        alternate = menu(.54)
        colored = np.all(alternate == (180, 45, 5), axis=2)
        image[colored] = alternate[colored]
        frame, _ = perspective(image)
        self.assertEqual(detect_displays(frame), {"left": None, "right": None})

    def test_high_resolution_keeps_original_pixel_centers(self):
        frame, _ = perspective(menu())
        original = detect_displays(frame)
        large = detect_displays(cv2.resize(frame, (2560, 1800)))
        for side in ("left", "right"):
            self.assertIsNotNone(large[side])
            np.testing.assert_allclose(large[side].corners, original[side].corners * 2 + .5, atol=5)
            self.assertGreater(large[side].corners[:, 1].max(), 1500)

    def test_dark_upper_margin_is_fitted_from_local_contrast(self):
        image = menu()
        image[:75] = (25, 13, 7)
        frame, transform = perspective(image)
        frame = cv2.GaussianBlur(frame, (5, 5), 1.2)
        geometry = detect_displays(frame)["right"]
        self.assertIsNotNone(geometry)
        expected = cv2.perspectiveTransform(np.array([[[486, 0], [899, 0], [899, 659], [486, 659]]], np.float32), transform)[0]
        np.testing.assert_allclose(geometry.corners, expected, atol=8)

    def test_division_follows_observed_edges_on_both_sides_of_midpoint(self):
        for fraction in (.44, .54):
            with self.subTest(fraction=fraction):
                frame, transform = perspective(monitor(fraction))
                diagnostics = {}
                detected = detect_displays(frame, diagnostics=diagnostics)
                self.assertEqual(diagnostics, {"path": "connected", "reason": ""})
                split = round(fraction * 900)
                for side, expected in (
                    ("left", [[0, 0], [split, 0], [split, 659], [0, 659]]),
                    ("right", [[split, 0], [899, 0], [899, 659], [split, 659]]),
                ):
                    geometry = detected[side]
                    self.assertIsNotNone(geometry)
                    expected_original = cv2.perspectiveTransform(np.array([expected], np.float32), transform)[0]
                    np.testing.assert_allclose(geometry.corners, expected_original, atol=10)
                    self.assertEqual(rectify_display(frame, geometry, (200, 320)).shape, (320, 200, 3))
                # The shared boundary is identical, not two unrelated fits.
                np.testing.assert_array_equal(detected["left"].corners[[1, 2]], detected["right"].corners[[0, 3]])

    def test_no_division_is_invented_from_blue_or_field_alone(self):
        for field, grid in ((False, False), (True, False), (False, True)):
            with self.subTest(field=field, grid=grid):
                frame, _ = perspective(monitor(field=field, grid=grid))
                diagnostics = {}
                self.assertEqual(detect_displays(frame, diagnostics=diagnostics), {"left": None, "right": None})
                self.assertEqual(diagnostics["reason"], "ambiguous_division")

    def test_field_must_agree_with_the_lower_grid(self):
        image = monitor(.54, field=False)
        cv2.rectangle(image, (350, 80), (885, 145), (235, 225, 180), -1)
        frame, _ = perspective(image)
        self.assertEqual(detect_displays(frame), {"left": None, "right": None})

    def test_two_independently_supported_divisions_are_ambiguous(self):
        image = monitor(.54, field=False, grid=False)
        for x, y in ((350, 50), (500, 150)):
            cv2.rectangle(image, (x, y), (885, y + 50), (235, 225, 180), -1)
            for column in range(4):
                boundary = round(x + (885 - x) * column / 3)
                cv2.line(image, (boundary, 330), (boundary, 625), (180, 45, 5), 3)
        self.assertIsNone(_connected_division(image))

    def test_blue_distractor_does_not_move_the_real_monitor(self):
        frame, _ = perspective(monitor())
        before = detect_displays(frame)
        cv2.rectangle(frame, (1140, 150), (1260, 450), (90, 45, 10), -1)
        after = detect_displays(frame)
        self.assertIsNotNone(after["right"])
        for side in ("left", "right"):
            np.testing.assert_array_equal(before[side].corners, after[side].corners)

    def test_two_valid_monitor_surfaces_are_not_arbitrarily_selected(self):
        tile = cv2.resize(monitor(), (540, 396))
        frame = np.zeros((600, 1280, 3), np.uint8)
        frame[100:496, 30:570] = tile
        frame[100:496, 700:1240] = tile
        diagnostics = {}
        self.assertEqual(detect_displays(frame, diagnostics=diagnostics), {"left": None, "right": None})
        self.assertEqual(diagnostics["reason"], "ambiguous_surface")

    def test_a_clipped_surface_does_not_use_an_internal_row_as_outer_edge(self):
        frame, _ = perspective(monitor())
        for clipped in (frame[:740], frame[:, :1000]):
            with self.subTest(shape=clipped.shape):
                self.assertEqual(detect_displays(clipped), {"left": None, "right": None})

    def test_off_center_scale_and_modest_image_degradation(self):
        quad = np.array([[450, 160], [1130, 180], [1110, 690], [430, 670]], np.float32)
        frame, transform = perspective(monitor(.44), quad)
        frame = cv2.GaussianBlur((frame.astype(np.float32) * .8).astype(np.uint8), (3, 3), .7)
        detected = detect_displays(frame)
        self.assertIsNotNone(detected["right"])
        expected = cv2.perspectiveTransform(np.array([[[396, 0], [396, 659]]], np.float32), transform)[0]
        np.testing.assert_allclose(detected["right"].corners[[0, 3]], expected, atol=10)

    def test_diagnostics_do_not_retain_a_previous_success(self):
        diagnostics = {"path": "separated", "reason": "", "old": "value"}
        detect_displays(np.zeros((480, 640, 3), np.uint8), diagnostics=diagnostics)
        self.assertEqual(diagnostics, {"path": "connected", "reason": "no_surface"})


if __name__ == "__main__":
    unittest.main()
