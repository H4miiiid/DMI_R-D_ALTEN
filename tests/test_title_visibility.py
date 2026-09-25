"""Evidence-driven OCR selection and obstruction pause/recovery contracts."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dmi.geometry import DisplayGeometry
from dmi.right_display import analyze_right_display
from dmi.temporal import RightDisplayStabilizer
from dmi.title_ocr import read_title, title_state
from dmi.visibility import right_display_obstructed


class TitleVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.image = np.full((960, 600, 3), (45, 18, 4), np.uint8)
        q = np.array([[0, 0], [599, 0], [599, 959], [0, 959]], np.float32)
        self.geometry = DisplayGeometry(q, q.copy(), (0, 0, 599, 959))

    def test_supported_title_mapping_requires_actual_exact_text(self):
        self.assertEqual(title_state(' DRIVER   ID '), 'Driver ID')
        for text in [None, 'Drive', 'Driver 10', 'Other', 'Main menu']:
            self.assertEqual(title_state(text), 'unknown')

    def test_title_ocr_drives_state_without_field_shape_guess(self):
        cv2.putText(self.image, "Level", (10, 140), 0, 1, (240, 240, 240), 2)
        with patch('dmi.right_display.read_title', return_value='Level'):
            result = analyze_right_display(self.image, self.geometry)
        self.assertEqual(result['state'], 'Level')
        self.assertIsNone(result['data_field'])
        self.assertIn('level_1', result['buttons'])

    def test_unreadable_title_does_not_infer_buttons_from_field(self):
        cv2.rectangle(self.image, (10, 190), (565, 290), (240, 240, 240), -1)
        with patch('dmi.right_display.read_title', return_value=None):
            result = analyze_right_display(self.image, self.geometry)
        self.assertEqual(result['state'], 'unknown')
        self.assertEqual(result['buttons'], {})
        self.assertIsNone(result['data_field']['value'])

    def test_normal_field_and_glyphs_do_not_pause(self):
        cv2.rectangle(self.image, (10, 190), (565, 290), (240, 240, 240), -1)
        for y in [490, 580, 670, 760]:
            cv2.putText(self.image, '1  2abc  3def', (20, y), 0, 1,
                        (230, 230, 230), 2)
        self.assertFalse(right_display_obstructed(self.image))

    def test_dark_warm_and_neutral_tools_pause_without_skin_model(self):
        for color in [(5, 8, 15), (35, 35, 35), (170, 170, 170)]:
            with self.subTest(color=color):
                image = self.image.copy()
                cv2.rectangle(image, (300, 500), (599, 630), color, -1)
                self.assertTrue(right_display_obstructed(image))

    def test_pause_skips_ocr_and_content_then_restarts_on_clear_frame(self):
        obstructed = self.image.copy()
        cv2.rectangle(obstructed, (350, 490), (599, 630), (5, 8, 15), -1)
        tracker = RightDisplayStabilizer()
        tracker.update({"state": "Driver ID", "title": None, "buttons": {},
                        "data_field": None, "visibility": "clear"})
        with patch('dmi.right_display.read_title') as ocr:
            paused = analyze_right_display(obstructed, self.geometry)
            ocr.assert_not_called()
        self.assertEqual(tracker.update(paused)['visibility'], 'occluded')
        self.assertEqual(paused['buttons'], {})
        self.assertIsNone(paused['title'])
        clear = {'state': 'Main', 'title': None, 'buttons': {},
                 'data_field': None, 'visibility': 'clear'}
        self.assertEqual(tracker.update(clear)['state'], 'Main')

    def test_title_crop_recovers_letter_outside_estimated_display_edge(self):
        image = np.full((960, 640, 3), (45, 18, 4), np.uint8)
        cv2.putText(image, 'Driver ID', (10, 140), 0, 1.2,
                    (245, 245, 245), 2, cv2.LINE_AA)
        q = np.array([[22, 0], [621, 0], [621, 959], [22, 959]], np.float32)
        geometry = DisplayGeometry(q, q.copy(), (22, 0, 621, 959))
        result = analyze_right_display(image, geometry)
        self.assertEqual(result['state'], 'Driver ID')
        self.assertEqual(result['title']['text'], 'Driver ID')

    def test_missing_ocr_dependency_reports_actionable_error(self):
        with patch('dmi.title_ocr.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Tesseract'):
                read_title(self.image, (0, 70, 100, 140))


if __name__ == '__main__':
    unittest.main()
