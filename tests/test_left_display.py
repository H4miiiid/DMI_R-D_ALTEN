"""Known synthetic geometry checks; video predictions are not ground truth."""
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi.pipeline import annotate_frame, process_frame
from dmi.geometry import DisplayGeometry
from dmi.left_layout import valid_quad
from dmi.temporal import GeometryStabilizer, RightDisplayStabilizer
from dmi.left_display import (
    analyze_left_display,
    detect_left_regions,
    LeftDisplayStabilizer,
)


def synthetic_display():
    frame = np.full((1280, 800, 3), (45, 20, 5), np.uint8)
    expected = {}
    rows = [130, 250, 790, 850, 910, 970, 1030, 1090, 1150, 1210]

    def region(name, x1, y1, x2, y2):
        expected[name] = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (75, 32, 8), 3)

    for i in range(9):
        region(f"box_{i+1}", 0, rows[i], 145, rows[i + 1])
    for i, (x1, x2) in enumerate(
        ((170, 260), (350, 440), (440, 530), (530, 620), (705, 785))
    ):
        region(f"box_{i+10}", x1, 745, x2, 832)
    columns = [145, 410, 550, 640, 725, 799]
    for i in range(5):
        region(f"box_{i+15}", columns[i], 850, columns[i + 1], 970)
    region("box_20", 145, 970, 690, 1210)
    region("box_21", 690, 970, 799, 1090)
    region("box_22", 690, 1090, 799, 1210)
    cv2.line(frame, (145, 130), (799, 130), (75, 32, 8), 3)
    # Dial-like foreground ensures the border detector ignores bright marks.
    cv2.circle(frame, (465, 450), 55, (230, 230, 230), -1)
    for angle in np.linspace(-140, 140, 13):
        radians = np.deg2rad(angle)
        points = [
            (round(465 + r * np.sin(radians)), round(450 - r * np.cos(radians)))
            for r in (240, 270)
        ]
        cv2.line(frame, *points, (230, 230, 230), 6)
    return frame, expected


class LeftDisplayTest(unittest.TestCase):
    def test_rejects_crossed_and_collapsed_regions(self):
        for points in (
            [[0, 0], [80, 8], [80, 7], [0, 6]],
            [[0, 0], [80, 0], [80, 2], [0, 2]],
            [[0, 0], [80, 0], [float("nan"), 60], [0, 60]],
        ):
            self.assertFalse(valid_quad(np.array(points, np.float32)))

    def test_blurred_video_sequence_never_emits_collapsed_regions(self):
        path = Path(__file__).resolve().parents[1] / "data/videos/dev/level_0.mp4"
        if not path.exists():
            self.skipTest("development video is unavailable")
        capture = cv2.VideoCapture(str(path))
        geometry = GeometryStabilizer()
        right = RightDisplayStabilizer()
        left = LeftDisplayStabilizer()
        try:
            for index in range(40):
                ok, frame = capture.read()
                self.assertTrue(ok)
                result = process_frame(frame, index, index / 30, geometry, right, left)
                regions = list(result["left_display"]["boxes"].values())
                if result["left_display"]["speed_indicator"] is not None:
                    regions.append(result["left_display"]["speed_indicator"])
                for region in regions:
                    self.assertTrue(
                        valid_quad(np.array(region["corners"], np.float32)),
                        f"invalid region at frame {index}",
                    )
        finally:
            capture.release()

    def test_all_logical_regions_match_independent_synthetic_borders(self):
        frame, expected = synthetic_display()
        boxes, speed = detect_left_regions(frame)
        self.assertEqual(set(boxes), set(expected))
        self.assertIsNotNone(speed)
        for name, corners in expected.items():
            np.testing.assert_allclose(boxes[name], corners, atol=5, err_msg=name)

    def test_perspective_and_exposure_follow_image_evidence(self):
        frame, expected = synthetic_display()
        src = np.array([[0, 0], [799, 0], [799, 1279], [0, 1279]], np.float32)
        dst = np.array([[0, 25], [799, 5], [799, 1270], [0, 1175]], np.float32)
        transform = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(frame, transform, (800, 1280))
        warped = np.clip(warped.astype(float) * 0.55, 0, 255).astype(np.uint8)
        boxes, speed = detect_left_regions(warped)
        self.assertEqual(set(boxes), set(expected))
        self.assertIsNotNone(speed)
        for name, corners in expected.items():
            target = cv2.perspectiveTransform(corners[None], transform)[0]
            np.testing.assert_allclose(boxes[name], target, atol=6, err_msg=name)

    def test_missing_evidence_does_not_create_a_layout(self):
        for frame in (
            np.zeros((1280, 800, 3), np.uint8),
            np.full((1280, 800, 3), (45, 20, 5), np.uint8),
            np.random.default_rng(4).integers(0, 60, (1280, 800, 3), dtype=np.uint8),
        ):
            boxes, speed = detect_left_regions(frame)
            self.assertEqual(boxes, {})
            self.assertIsNone(speed)

    def test_original_frame_mapping_and_unknown_icons(self):
        screen, expected = synthetic_display()
        src = np.array([[0, 0], [799, 0], [799, 1279], [0, 1279]], np.float32)
        dst = np.array([[100, 80], [940, 105], [915, 1410], [70, 1360]], np.float32)
        transform = cv2.getPerspectiveTransform(src, dst)
        frame = cv2.warpPerspective(screen, transform, (1100, 1500))
        geometry = DisplayGeometry(dst, dst, (70, 80, 940, 1410))
        result = analyze_left_display(frame, geometry)
        self.assertEqual(len(result["boxes"]), 22)
        for name, region in result["boxes"].items():
            self.assertIsNone(region["icon"])
            target = cv2.perspectiveTransform(expected[name][None], transform)[0]
            np.testing.assert_allclose(region["corners"], target, atol=6, err_msg=name)
            corners = np.array(region["corners"])
            x1, y1, x2, y2 = region["bbox"]
            self.assertTrue((corners[:, 0] >= x1).all() and (corners[:, 0] <= x2).all())
            self.assertTrue((corners[:, 1] >= y1).all() and (corners[:, 1] <= y2).all())

    def test_temporal_smoothing_resets_on_loss_and_tracks_motion(self):
        stabilizer = LeftDisplayStabilizer()
        q = np.array([[10, 10], [100, 10], [100, 80], [10, 80]], np.float32)
        stabilizer.update({"box_1": q}, None)
        smoothed, _ = stabilizer.update({"box_1": q + 1}, None)
        np.testing.assert_allclose(smoothed["box_1"], q + 0.3, atol=1e-5)
        moved, _ = stabilizer.update({"box_1": q + 25}, None)
        np.testing.assert_allclose(moved["box_1"], q + 25)
        self.assertEqual(stabilizer.update({}, None), ({}, None))
        reset, _ = stabilizer.update({"box_1": q}, None)
        np.testing.assert_array_equal(reset["box_1"], q)

    def test_image_motion_bridges_only_three_missing_measurements(self):
        frame, boxes = synthetic_display()
        tracker = LeftDisplayStabilizer()
        tracker.update(boxes, None, frame)
        for shift in (2, 4, 6):
            moved = cv2.warpAffine(
                frame, np.float32([[1, 0, shift], [0, 1, 0]]), (800, 1280)
            )
            tracked, _ = tracker.update({}, None, moved)
            self.assertEqual(len(tracked), 22)
            np.testing.assert_allclose(
                tracked["box_20"], boxes["box_20"] + [shift, 0], atol=1.5
            )
        expired, _ = tracker.update({}, None, moved)
        self.assertEqual(expired, {})

    def test_annotations_use_reported_left_region_centers(self):
        frame = np.zeros((450, 500, 3), np.uint8)
        result = process_frame(frame, 0, 0)
        result["left_display"].update(
            {
                "boxes": {
                    "box_1": {
                        "corners": [[20, 170], [100, 170], [100, 260], [20, 260]],
                        "center": [60, 215],
                        "icon": None,
                    }
                },
                "speed_indicator": {
                    "corners": [[180, 170], [420, 180], [400, 400], [180, 400]],
                    "center": [295, 282],
                },
            }
        )
        annotated = annotate_frame(frame, result)
        np.testing.assert_array_equal(annotated[215, 60], [0, 80, 255])
        np.testing.assert_array_equal(annotated[282, 295], [0, 220, 255])
        self.assertFalse(frame.any())

    def test_unrelated_image_cannot_preserve_missing_regions(self):
        frame, boxes = synthetic_display()
        tracker = LeftDisplayStabilizer()
        tracker.update(boxes, None, frame)
        tracked, speed = tracker.update({}, None, np.zeros_like(frame))
        self.assertEqual(tracked, {})
        self.assertIsNone(speed)


if __name__ == "__main__":
    unittest.main()
