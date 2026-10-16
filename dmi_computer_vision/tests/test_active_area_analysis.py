"""Measured control borders with changed margins, titles and field illumination."""
from __future__ import annotations

import unittest
from pathlib import Path

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry, detect_displays
from dmi_computer_vision.src.dmi.detection.right_display import (
    analyze_right_display, _read_digits, _digits_from_mask,
)
from dmi_computer_vision.src.dmi.detection.right_layout import detect_button_quads
from dmi_computer_vision.src.dmi.detection.left_display import detect_left_regions
from dmi_computer_vision.tests.test_left_display import synthetic_display


def active_screen(title: str = "Driver ID", *, menu: bool = False):
    frame = np.full((960, 600, 3), (45, 15, 4), np.uint8)
    cv2.putText(frame, title, (8, 58), 0, 1.1, (240, 240, 240), 2, cv2.LINE_AA)
    rows = (135, 235, 335, 435, 535, 635) if menu else (430, 530, 630, 730, 830)
    columns = (2, 299, 597) if menu else (2, 199, 399, 597)
    for y in rows:
        cv2.line(frame, (2, y), (597, y), (90, 25, 5), 3)
    for x in columns:
        cv2.line(frame, (x, rows[0]), (x, rows[-1]), (90, 25, 5), 3)
    cv2.rectangle(frame, (2, 830), (156, 925), (90, 25, 5), 3)
    q = np.array([[0, 0], [599, 0], [599, 959], [0, 959]], np.float32)
    return frame, DisplayGeometry(q, q.copy(), (0, 0, 599, 959))


class ActiveAreaAnalysisTest(unittest.TestCase):
    def test_upper_title_cyan_field_and_only_visible_action(self):
        frame, geometry = active_screen()
        cv2.rectangle(frame, (1, 130), (598, 230), (235, 110, 80), -1)
        cv2.putText(frame, "47", (15, 190), 0, 1, (70, 40, 10), 2, cv2.LINE_AA)
        result = analyze_right_display(frame, geometry)
        self.assertEqual(result['state'], 'Driver ID')
        self.assertEqual(result['title']['text'], 'Driver ID')
        self.assertLess(result['title']['bbox'][3], 90)
        self.assertEqual(result['data_field']['value'], '47')
        self.assertEqual(len(result['buttons']), 13)
        self.assertIn('cancel', result['buttons'])
        for absent in ('empty_action', 'trn', 'settings'):
            self.assertNotIn(absent, result['buttons'])
        np.testing.assert_allclose(result['buttons']['digit_1']['center'], [100, 480], atol=4)
        np.testing.assert_allclose(result['buttons']['digit_0']['center'], [299, 780], atol=4)

    def test_main_grid_follows_observed_full_width_borders(self):
        frame, geometry = active_screen('Main', menu=True)
        result = analyze_right_display(frame, geometry)
        self.assertEqual(result['state'], 'Main')
        self.assertIsNone(result['data_field'])
        self.assertEqual(len(result['buttons']), 11)
        np.testing.assert_allclose(result['buttons']['driver_id']['center'], [448, 185], atol=4)
        np.testing.assert_allclose(result['buttons']['radio_data']['center'], [448, 585], atol=4)

    def test_missing_action_border_omits_action_instead_of_inventing_slots(self):
        frame, _ = active_screen()
        frame[827:929, 151:161] = (45, 15, 4)
        buttons = detect_button_quads(frame, 'Driver ID')
        self.assertEqual(len(buttons), 12)
        self.assertNotIn('cancel', buttons)

    def test_incomplete_active_grid_does_not_fall_back_to_nominal_rows(self):
        frame, _ = active_screen()
        frame[525:536, 6:594] = (45, 15, 4)
        self.assertEqual(detect_button_quads(frame, 'Driver ID'), {})

    def test_moving_only_title_does_not_change_control_identities_or_geometry(self):
        for menu in (False, True):
            baseline = None
            for offset in (0, 27, 41):
                with self.subTest(menu=menu, title_offset=offset):
                    title = 'Main' if menu else 'Driver ID'
                    frame, geometry = active_screen(title, menu=menu)
                    frame[:115, :250] = (45, 15, 4)
                    cv2.putText(frame, title, (8, 58 + offset), 0, 1.1,
                                (240, 240, 240), 2, cv2.LINE_AA)
                    result = analyze_right_display(frame, geometry)
                    self.assertEqual(result['state'], title)
                    self.assertEqual(len(result['buttons']), 11 if menu else 13)
                    if baseline is None:
                        baseline = result['buttons']
                    else:
                        self.assertEqual(result['buttons'], baseline)

    def test_missing_active_column_cannot_produce_nominal_controls(self):
        for menu in (False, True):
            frame, geometry = active_screen('Main' if menu else 'Driver ID', menu=menu)
            x = 299 if menu else 199
            frame[130:835, x - 5:x + 6] = (45, 15, 4)
            result = analyze_right_display(frame, geometry)
            self.assertNotEqual(result['state'], 'unknown')
            self.assertEqual(result['buttons'], {})

    def test_grid_does_not_assign_identity_without_a_supported_title(self):
        frame, geometry = active_screen('Other')
        result = analyze_right_display(frame, geometry)
        self.assertEqual(result['state'], 'unknown')
        self.assertFalse({'digit_1', 'cancel', 'driver_id'} & result['buttons'].keys())

    def test_title_without_any_grid_cannot_invent_legacy_controls(self):
        for menu in (False, True):
            frame, geometry = active_screen('Main' if menu else 'Driver ID', menu=menu)
            frame[115:] = (45, 15, 4)
            result = analyze_right_display(frame, geometry)
            self.assertEqual(result['state'], 'Main' if menu else 'Driver ID')
            self.assertEqual(result['buttons'], {})

    def test_dim_field_digits_survive_illumination_gradient(self):
        for value in ('23', '81', '47'):
            with self.subTest(value=value):
                field = np.full((95, 590, 3), (235, 110, 80), np.uint8)
                cv2.putText(field, value, (10, 60), 0, 1, (70, 40, 10), 2, cv2.LINE_AA)
                factor = np.linspace(.65, 1, 590)[None, :, None]
                field = (field * factor).astype(np.uint8)
                self.assertEqual(_read_digits(field, last_only=False), value)
        self.assertIsNone(_read_digits(np.full((95, 590, 3), (235, 110, 80), np.uint8), last_only=False))

    def test_unreadable_component_cannot_be_dropped_from_a_field_value(self):
        mask = np.zeros((95, 590), np.uint8)
        cv2.rectangle(mask, (10, 30), (70, 53), 255, -1)
        cv2.putText(mask, '3', (80, 53), 0, 1, 255, 2, cv2.LINE_AA)
        self.assertIsNone(_digits_from_mask(mask, last_only=False))

    def test_all_clear_digits_and_dim_font_variants_are_correct_or_rejected(self):
        for font in (cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX, cv2.FONT_HERSHEY_TRIPLEX):
            for color in ((240, 245, 235), (235, 110, 80)):
                for digit in '0123456789':
                    with self.subTest(font=font, color=color, digit=digit):
                        field = np.full((95, 590, 3), color, np.uint8)
                        cv2.putText(field, digit, (15, 60), font, 1,
                                    (70, 40, 10), 2, cv2.LINE_AA)
                        value = _read_digits(field, last_only=False)
                        if color == (240, 245, 235):
                            self.assertEqual(value, digit)
                        else:
                            self.assertIn(value, (None, digit))

    def test_driver03_frame78_ambiguous_reading_is_not_published_as_73(self):
        source = Path(__file__).resolve().parents[1] / 'data/videos/dev/dmi_capture_quality_03/annotated.mp4'
        if not source.exists():
            self.skipTest('development recording is unavailable')
        capture = cv2.VideoCapture(str(source))
        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 78)
            ok, frame = capture.read()
            self.assertTrue(ok)
        finally:
            capture.release()
        geometry = detect_displays(frame)['right']
        self.assertIsNotNone(geometry)
        result = analyze_right_display(frame, geometry)
        self.assertEqual(result['state'], 'Driver ID')
        self.assertIsNotNone(result['data_field'])
        self.assertIn(result['data_field']['value'], (None, '23'))

    def test_left_sidebar_search_accepts_reduced_upper_margin(self):
        frame, expected = synthetic_display()
        transform = np.array([[1, 0, 0], [0, 1.1, -103]], np.float32)
        changed = cv2.warpAffine(frame, transform, (800, 1280), borderValue=(45, 20, 5))
        boxes, speed = detect_left_regions(changed)
        self.assertEqual(set(boxes), set(expected))
        self.assertIsNotNone(speed)
        for name, points in expected.items():
            mapped = cv2.transform(points[None], transform)[0]
            np.testing.assert_allclose(boxes[name], mapped, atol=5, err_msg=name)

    def test_missing_upper_border_keeps_independently_supported_lower_boxes(self):
        frame, expected = synthetic_display()
        transform = np.array([[1, 0, 0], [0, 1.1, -103]], np.float32)
        changed = cv2.warpAffine(frame, transform, (800, 1280), borderValue=(45, 20, 5))
        changed[34:48] = (45, 20, 5)
        boxes, speed = detect_left_regions(changed)
        self.assertEqual(set(boxes), set(expected) - {'box_1'})
        self.assertIsNone(speed)
        for name, points in expected.items():
            if name == 'box_1':
                continue
            np.testing.assert_allclose(boxes[name], cv2.transform(points[None], transform)[0],
                                       atol=5, err_msg=name)

    def test_missing_upper_and_lower_sidebar_evidence_is_not_a_complete_layout(self):
        frame, _ = synthetic_display()
        frame[115:150] = (45, 20, 5)
        frame[1015:1045] = (45, 20, 5)
        boxes, speed = detect_left_regions(frame)
        self.assertNotIn('box_1', boxes)
        self.assertLess(len(boxes), 22)
        self.assertIsNone(speed)


if __name__ == '__main__':
    unittest.main()
