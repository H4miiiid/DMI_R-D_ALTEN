"""Partial observations, geometry changes and current-image OCR evidence."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.display_geometry import (
    DisplayGeometry, detect_displays, rectify_display,
)
from dmi_computer_vision.src.dmi.detection.left_display import analyze_train_left_display
from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor
from dmi_computer_vision.src.dmi.temporal.smoothing import GeometryStabilizer

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = 'dmi_computer_vision.src.dmi.pipeline.frame_processor.'


def geometry(offset: float = 0) -> DisplayGeometry:
    points = np.array([[500, 70], [700, 70], [700, 570], [500, 570]], np.float32)
    points[:, 0] += offset
    return DisplayGeometry(points, points.copy(), (500, 70, 700, 570))


def content(value: str) -> dict:
    points = [[520, 200], [680, 200], [680, 240], [520, 240]]
    field = {'corners': points, 'bbox': [520, 200, 680, 240], 'center': [600, 220]}
    return {'visibility': 'clear', 'state': 'Driver ID', 'title': None,
            'buttons': {}, 'data_field': {**field, 'value': value}}


class LocalizationBasisTest(unittest.TestCase):
    def test_compatible_connected_measurements_keep_normal_smoothing(self):
        tracker = GeometryStabilizer()
        first = {"left": None, "right": geometry()}
        tracker.update(first, (650, 900), layout="connected:spanning_borders")
        shifted = {"left": None, "right": geometry(1)}
        actual = tracker.update(shifted, (650, 900), layout="connected:field_grid")
        self.assertIsNone(tracker.last_reset_reason)
        self.assertNotIn("right", tracker.reset_regions)
        self.assertLess(actual["right"].corners[0, 0], shifted["right"].corners[0, 0])
        self.assertGreater(actual["right"].corners[0, 0], first["right"].corners[0, 0])

    def test_changed_border_basis_discards_crop_and_content_history(self):
        processor = FrameProcessor(collect_target_evidence=True)
        frame = np.zeros((650, 900, 3), np.uint8)
        detected = {"left": None, "right": geometry()}
        basis = ["spanning_borders"]

        def detect(_frame, *, diagnostics):
            diagnostics.update(path="connected", division_basis=basis[0])
            return detected

        with patch(PIPELINE + "detect_displays", side_effect=detect), patch(
                PIPELINE + "analyze_right_display", return_value=content("12")) as analyze:
            processor.process(frame, 0.)
            detected["right"] = geometry(10)
            basis[0] = "field_grid"
            analyze.return_value = content("47")
            current = processor.process(frame, 0.3)
            self.assertEqual(processor.last_reset_reason, "display_layout_changed")
            self.assertEqual(current["right_display"]["geometry"], detected["right"].as_result())
            self.assertEqual(current["right_display"]["data_field"]["value"], "47")
            self.assertEqual(processor.target_evidence["right_field_value"], "47")
            # Stable evidence keeps the existing debounce; this is not a way
            # to bypass same-title value confirmation on ordinary frames.
            analyze.return_value = content("51")
            current = processor.process(frame, 0.6)
            self.assertIsNone(processor.last_reset_reason)
            self.assertEqual(current["right_display"]["data_field"]["value"], "47")
            self.assertEqual(processor.target_evidence["right_field_value"], "51")


class PartialMonitorTest(unittest.TestCase):
    def sample(self) -> np.ndarray:
        capture = cv2.VideoCapture(str(ROOT / 'data/videos/dev/driver_id_12.mp4'))
        try:
            ok, frame = capture.read()
            self.assertTrue(ok)
            return frame
        finally:
            capture.release()

    def test_independent_regions_keep_their_role_even_across_the_image_midpoint(self):
        frame = self.sample()
        original = detect_displays(frame)
        for side, shift in (('left', 0), ('right', 0), ('left', 550), ('right', -550)):
            with self.subTest(side=side, shift=shift):
                mask = np.zeros(frame.shape[:2], np.uint8)
                cv2.fillConvexPoly(mask, np.rint(original[side].corners).astype(np.int32), 255)
                # Preserve the complete source border, including mask-fit
                # residuals outside the fitted quadrilateral.
                mask = cv2.dilate(mask, np.ones((61, 61), np.uint8))
                isolated = cv2.bitwise_and(frame, frame, mask=mask)
                isolated = cv2.warpAffine(isolated, np.float32([[1, 0, shift], [0, 1, 0]]),
                                          (frame.shape[1], frame.shape[0]))
                detected = detect_displays(isolated)
                self.assertIsNotNone(detected[side])
                self.assertIsNone(detected['right' if side == 'left' else 'left'])
                np.testing.assert_allclose(detected[side].corners,
                                           original[side].corners + [shift, 0], atol=5)

    def test_plain_portrait_blue_and_two_duplicate_roles_are_rejected(self):
        frame = self.sample()
        plain = np.zeros_like(frame)
        cv2.rectangle(plain, (100, 80), (480, 650), (70, 25, 5), -1)
        self.assertEqual(detect_displays(plain), {'left': None, 'right': None})
        left = detect_displays(frame)['left']
        mask = np.zeros(frame.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, np.rint(left.corners).astype(np.int32), 255)
        isolated = cv2.bitwise_and(frame, frame, mask=mask)
        duplicate = cv2.warpAffine(isolated, np.float32([[1, 0, 650], [0, 1, 0]]),
                                   (frame.shape[1], frame.shape[0]))
        # Exercise ambiguity in the partial fallback independently of the
        # accepted successful two-display path.
        from dmi_computer_vision.src.dmi.detection.display_geometry import (
            _display_color_masks, _retain_partial_displays,
        )
        image = cv2.max(isolated, duplicate)
        mask, strong = _display_color_masks(image)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.assertEqual(_retain_partial_displays(image, [[c] for c in contours], strong, {}),
                         {'left': None, 'right': None})

    def test_connected_logical_regions_can_survive_partner_removal(self):
        source = ROOT / 'data/videos/dev/dmi_capture_quality_02/last_annotated.png'
        frame = cv2.imread(str(source))
        self.assertIsNotNone(frame)
        original = detect_displays(frame)
        for side in ('left', 'right'):
            with self.subTest(side=side):
                mask = np.zeros(frame.shape[:2], np.uint8)
                cv2.fillConvexPoly(mask, np.rint(original[side].corners).astype(np.int32), 255)
                isolated = cv2.bitwise_and(frame, frame, mask=mask)
                actual = detect_displays(isolated)
                self.assertIsNotNone(actual[side])
                self.assertIsNone(actual['right' if side == 'left' else 'left'])
                result = FrameProcessor().process(isolated, 0.)
                if side == 'right':
                    self.assertEqual(result['right_display']['state'], 'Driver ID')
                    self.assertEqual(len(result['right_display']['buttons']), 13)
                    self.assertEqual(result['right_display']['visibility'], 'clear')
                else:
                    self.assertEqual(result['right_display']['state'], 'unknown')
                    self.assertGreater(len(result['left_display']['boxes']), 0)

    def test_gauge_arc_does_not_trigger_train_title_ocr(self):
        frame = cv2.imread(str(ROOT / 'data/videos/dev/dmi_capture_quality_01/last_annotated.png'))
        left = detect_displays(frame)['left']
        rectified = rectify_display(frame, left, (800, 1280))
        with patch('dmi_computer_vision.src.dmi.detection.left_display.read_title') as read:
            self.assertIsNone(analyze_train_left_display(rectified, left))
            read.assert_not_called()

    def test_current_train_title_is_read_again_and_changed_button_is_not_cached(self):
        frame = np.full((1280, 800, 3), (50, 20, 5), np.uint8)
        cv2.putText(frame, 'Train data', (500, 170), cv2.FONT_HERSHEY_SIMPLEX,
                    1.3, (240, 240, 240), 2)
        with patch('dmi_computer_vision.src.dmi.detection.left_display.read_title',
                   return_value='Train data') as read:
            first = analyze_train_left_display(frame, geometry())
            cv2.rectangle(frame, (5, 1100), (795, 1200), (190, 190, 190), -1)
            second = analyze_train_left_display(frame, geometry())
        self.assertEqual(read.call_count, 2)
        self.assertEqual(first[0], 'Train Data')
        self.assertNotIn('yes', first[1]['buttons'])
        self.assertIn('yes', second[1]['buttons'])


class MonitorHistoryTest(unittest.TestCase):
    def test_perspective_jump_cannot_blend_with_a_stationary_enclosure(self):
        first = geometry()
        corners = first.corners.copy()
        corners[0, 0] += 40
        changed = DisplayGeometry(corners, first.oriented_box.copy(), first.bbox)
        smoother = GeometryStabilizer()
        smoother.update({'left': None, 'right': first}, (720, 1280))
        actual = smoother.update({'left': None, 'right': changed}, (720, 1280))
        np.testing.assert_array_equal(actual['right'].corners, corners)
        self.assertIn('right', smoother.reset_regions)
        self.assertEqual(smoother.last_reset_reason, 'display_geometry_changed')

    def test_loss_and_recovery_do_not_replay_geometry_or_reset_the_partner(self):
        smoother = GeometryStabilizer()
        both = {'left': geometry(-400), 'right': geometry()}
        smoother.update(both, (720, 1280), layout='connected')
        missing = smoother.update({'left': None, 'right': geometry()}, (720, 1280))
        self.assertIsNone(missing['left'])
        self.assertEqual(smoother.reset_regions, {'left'})
        smoother.update(both, (720, 1280), layout='connected')
        self.assertEqual(smoother.reset_regions, {'left'})

    def run_change(self, *, layout_change=False, jump=False, partial=False):
        frame = np.zeros((720, 1280, 3), np.uint8)
        call = 0
        def detect(image, *, diagnostics):
            nonlocal call
            diagnostics['path'] = ('partial' if partial and call else
                                   'connected' if layout_change and call else 'separated')
            current = geometry(120 if jump and call else 0)
            call += 1
            return {'left': None, 'right': current}
        processor = FrameProcessor(collect_target_evidence=True)
        with patch(PIPELINE + 'detect_displays', side_effect=detect), \
                patch(PIPELINE + 'analyze_right_display', side_effect=[content('12'), content('23')]):
            processor.process(frame, 0.)
            second = processor.process(frame, 0.1)
        return processor, second

    def test_geometry_jump_clears_field_confirmation_and_region_history(self):
        processor, result = self.run_change(jump=True)
        self.assertEqual(result['right_display']['data_field']['value'], '23')
        self.assertEqual(processor.target_evidence['right_field_value'], '23')
        self.assertEqual(processor.last_reset_reason, 'display_geometry_changed')

    def test_arrangement_change_resets_even_when_enclosures_coincide(self):
        processor, result = self.run_change(layout_change=True)
        self.assertEqual(result['right_display']['data_field']['value'], '23')
        self.assertEqual(processor.last_reset_reason, 'display_layout_changed')

    def test_orphan_crop_basis_does_not_blend_with_a_previous_partition(self):
        processor, result = self.run_change(partial=True)
        self.assertEqual(result['right_display']['data_field']['value'], '23')
        self.assertEqual(processor.last_reset_reason, 'display_layout_changed')

    def test_unchanged_geometry_still_requires_real_value_confirmation(self):
        processor, result = self.run_change()
        self.assertEqual(result['right_display']['data_field']['value'], '12')
        self.assertEqual(processor.target_evidence['right_field_value'], '23')
        self.assertIsNone(processor.last_reset_reason)

    def test_new_session_and_explicit_reset_have_no_old_field_or_geometry(self):
        first, _ = self.run_change()
        frame = np.zeros((720, 1280, 3), np.uint8)
        first.reset()
        with patch(PIPELINE + 'detect_displays', return_value={'left': None, 'right': geometry()}), \
                patch(PIPELINE + 'analyze_right_display', return_value=content('7')):
            after_reset = first.process(frame, 0.)
            independent = FrameProcessor(collect_target_evidence=True).process(frame, 0.)
        self.assertEqual(after_reset, independent)
        self.assertEqual(after_reset['right_display']['data_field']['value'], '7')

    def test_lost_left_region_cannot_hint_a_right_train_identity(self):
        frame = np.zeros((720, 1280, 3), np.uint8)
        left_content = {'boxes': {}, 'speed_indicator': None, 'title': None, 'buttons': {}}
        observations = [{'left': geometry(-400), 'right': geometry()},
                        {'left': None, 'right': geometry()}]
        processor = FrameProcessor()
        with patch(PIPELINE + 'detect_displays', side_effect=observations), \
                patch(PIPELINE + 'analyze_train_left_display', return_value=('Train Data', left_content)), \
                patch(PIPELINE + 'analyze_right_display', return_value=content('12')) as analyze:
            processor.process(frame, 0.)
            processor.process(frame, 0.1)
        self.assertEqual(analyze.call_args_list[0].args[2], 'Train Data')
        self.assertIsNone(analyze.call_args_list[1].args[2])


if __name__ == '__main__':
    unittest.main()
