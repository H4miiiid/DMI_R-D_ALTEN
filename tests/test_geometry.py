from __future__ import annotations

from pathlib import Path
import sys
from typing import cast
import unittest

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.geometry import (  # noqa: E402
    DisplayGeometry,
    detect_displays,
    rectify_display,
)
from dmi.temporal import GeometryStabilizer  # noqa: E402


class DisplayGeometryTest(unittest.TestCase):
    def test_detects_two_perspective_displays_without_fixed_coordinates(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        expected_left = np.array(
            [[110, 90], [500, 105], [480, 650], [90, 630]], dtype=np.int32
        )
        expected_right = np.array(
            [[730, 115], [1120, 95], [1140, 640], [750, 660]], dtype=np.int32
        )
        blue = (70, 25, 5)
        cv2.fillConvexPoly(frame, expected_left, blue)
        cv2.fillConvexPoly(frame, expected_right, blue)
        cv2.rectangle(frame, (730, 250), (1120, 315), (230, 255, 245), -1)

        displays = detect_displays(frame)

        self.assertIsNotNone(displays["left"])
        self.assertIsNotNone(displays["right"])
        left = cast(DisplayGeometry, displays["left"])
        right = cast(DisplayGeometry, displays["right"])
        np.testing.assert_allclose(
            left.corners, expected_left, atol=8
        )
        np.testing.assert_allclose(right.corners, expected_right, atol=8)
        np.testing.assert_allclose(left.bbox, (90, 90, 500, 640), atol=6)
        np.testing.assert_allclose(right.bbox, (730, 95, 1140, 650), atol=6)
        self._assert_rotated_rectangle(left.oriented_box)
        self._assert_rotated_rectangle(right.oriented_box)
        self.assertGreater(
            abs(left.oriented_box[1, 1] - left.oriented_box[0, 1]), 5
        )
        self.assertGreater(
            abs(right.oriented_box[1, 1] - right.oriented_box[0, 1]), 5
        )

    def _assert_rotated_rectangle(self, corners: np.ndarray) -> None:
        sides = np.roll(corners, -1, axis=0) - corners
        self.assertAlmostEqual(float(np.dot(sides[0], sides[1])), 0.0, delta=15.0)
        self.assertAlmostEqual(float(np.dot(sides[1], sides[2])), 0.0, delta=15.0)
        np.testing.assert_allclose(
            np.linalg.norm(sides[0]), np.linalg.norm(sides[2]), atol=1e-3
        )
        np.testing.assert_allclose(
            np.linalg.norm(sides[1]), np.linalg.norm(sides[3]), atol=1e-3
        )

    def test_returns_unknown_when_evidence_is_missing(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertEqual(detect_displays(frame), {"left": None, "right": None})

    def test_stabilizer_reduces_jitter_and_preserves_rectangles(self) -> None:
        stabilizer = GeometryStabilizer(smoothing=0.2)
        raw_centers = []
        stable_centers = []
        for offset in (0, 10, -10, 9, -9, 8, -8):
            geometry = self._translated_geometry(offset, 0)
            raw_centers.append(geometry.center[0])
            displays = stabilizer.update(
                {"left": geometry, "right": None}, (720, 1280)
            )
            stabilized = cast(DisplayGeometry, displays["left"])
            stable_centers.append(stabilized.center[0])
            self._assert_rotated_rectangle(stabilized.oriented_box)

        self.assertLess(np.ptp(stable_centers[1:]), np.ptp(raw_centers[1:]) / 2)

    def test_stabilizer_resets_after_genuine_geometry_jump(self) -> None:
        stabilizer = GeometryStabilizer(smoothing=0.2)
        initial = self._translated_geometry(0, 0)
        jumped = self._translated_geometry(300, 0)
        stabilizer.update({"left": initial, "right": None}, (720, 1280))

        result = stabilizer.update(
            {"left": jumped, "right": None}, (720, 1280)
        )

        stabilized = cast(DisplayGeometry, result["left"])
        np.testing.assert_allclose(stabilized.oriented_box, jumped.oriented_box)

    @staticmethod
    def _translated_geometry(x_offset: float, y_offset: float) -> DisplayGeometry:
        offset = np.array([x_offset, y_offset], dtype=np.float32)
        oriented_box = np.array(
            [[100, 100], [500, 110], [486.5, 650], [86.5, 640]],
            dtype=np.float32,
        )
        corners = np.array(
            [[105, 105], [495, 115], [480, 645], [90, 635]],
            dtype=np.float32,
        )
        return DisplayGeometry(
            corners=corners + offset,
            oriented_box=oriented_box + offset,
            bounding_box=(
                round(85 + x_offset),
                round(100 + y_offset),
                round(500 + x_offset),
                round(650 + y_offset),
            ),
        )

    def test_rectifies_to_requested_size(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        left = np.array(
            [[110, 90], [500, 105], [480, 650], [90, 630]], dtype=np.int32
        )
        right = np.array(
            [[730, 115], [1120, 95], [1140, 640], [750, 660]], dtype=np.int32
        )
        cv2.fillConvexPoly(frame, left, (70, 25, 5))
        cv2.fillConvexPoly(frame, right, (70, 25, 5))
        geometry = detect_displays(frame)["left"]
        self.assertIsNotNone(geometry)

        rectified = rectify_display(
            frame, cast(DisplayGeometry, geometry), (400, 600)
        )

        self.assertEqual(rectified.shape, (600, 400, 3))


if __name__ == "__main__":
    unittest.main()
