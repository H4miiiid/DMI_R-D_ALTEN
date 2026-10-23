"""Evidence-driven OCR selection and obstruction pause/recovery contracts."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry
from dmi_computer_vision.src.dmi.detection.right_display import analyze_right_display
from dmi_computer_vision.src.dmi.temporal.smoothing import RightDisplayStabilizer
from dmi_computer_vision.src.dmi.detection.title_ocr import read_title, title_state
from dmi_computer_vision.src.dmi.detection import title_ocr
from dmi_computer_vision.src.dmi.detection.visibility import right_display_obstructed


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
        with patch('dmi.detection.right_display.read_title', return_value='Level'):
            result = analyze_right_display(self.image, self.geometry)
        self.assertEqual(result['state'], 'Level')
        self.assertIsNone(result['data_field'])
        self.assertEqual(result['buttons'], {})  # A title alone establishes no controls.

    def test_unreadable_title_does_not_infer_buttons_from_field(self):
        cv2.rectangle(self.image, (10, 190), (565, 290), (240, 240, 240), -1)
        with patch('dmi.detection.right_display.read_title', return_value=None):
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
        with patch('dmi.detection.right_display.read_title') as ocr:
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
        with patch('dmi.detection.title_ocr.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Tesseract'):
                read_title(self.image, (0, 70, 100, 140))


class BatchTitleTest(unittest.TestCase):
    @staticmethod
    def word(text, top, *, confidence=90, line='1', height=10):
        return {'text':text, 'top':str(top), 'left':'20', 'width':'40',
                'height':str(height), 'conf':str(confidence),
                'block_num':'1', 'par_num':'1', 'line_num':line}

    def setUp(self):
        self.crops = [np.zeros((40,100,3),np.uint8) for _ in range(2)]

    def test_words_map_to_current_crop_bounds_independent_of_output_order(self):
        words = [self.word('SCMT',120,line='2'), self.word('KVB',20)]
        with patch.object(title_ocr,'_recognize_words',return_value=words) as ocr:
            self.assertEqual(title_ocr.read_titles(self.crops),['KVB','SCMT'])
        self.assertEqual(ocr.call_count,1)

    def test_each_crop_requires_unchanged_confidence_for_every_word(self):
        for confidence in (64.9,float('nan'),float('inf')):
            with self.subTest(confidence=confidence), patch.object(
                    title_ocr,'_recognize_words',return_value=[
                        self.word('KVB',20), self.word('TBL1+',120,confidence=confidence,line='2')]):
                self.assertEqual(title_ocr.read_titles(self.crops),['KVB',None])
        with patch.object(title_ocr,'_recognize_words',return_value=[self.word('KVB',20,confidence=65)]):
            self.assertEqual(title_ocr.read_titles(self.crops),['KVB',None])

    def test_cross_crop_and_multiline_text_cannot_be_assigned_to_a_cell(self):
        for words in ([self.word('KVB',20),self.word('SCMT',95,height=10)],
                      [self.word('KVB',20),self.word('OTHER',40,line='2')]):
            with self.subTest(words=words), patch.object(title_ocr,'_recognize_words',return_value=words):
                self.assertEqual(title_ocr.read_titles(self.crops),[None,None])

    def test_empty_crops_do_not_invoke_ocr_or_shift_other_results(self):
        with patch.object(title_ocr,'_recognize_words',return_value=[self.word('KVB',20)]) as ocr:
            self.assertEqual(title_ocr.read_titles([]),[])
            self.assertEqual(title_ocr.read_titles([np.empty((0,0,3),np.uint8)]),[None])
            ocr.assert_not_called()
            self.assertEqual(title_ocr.read_titles([self.crops[0],np.empty((0,0,3),np.uint8)]),['KVB',None])
            self.assertEqual(ocr.call_count,1)

    def test_timeout_yields_unknown_and_dependency_failure_is_explicit(self):
        import subprocess
        with patch.object(title_ocr.subprocess,'run',side_effect=subprocess.TimeoutExpired('tesseract',5)):
            self.assertEqual(title_ocr.read_titles(self.crops),[None,None])
        with patch.object(title_ocr.shutil,'which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Tesseract'):
                title_ocr.read_titles(self.crops)

    def test_current_labels_are_read_after_change_loss_and_recovery(self):
        def crop(text):
            image = np.full((50,180,3),(45,15,4),np.uint8)
            cv2.putText(image,text,(15,35),cv2.FONT_HERSHEY_DUPLEX,.8,
                        (230,230,230),1,cv2.LINE_AA)
            return image
        initial = [crop('KVB'),crop('LZB')]
        self.assertEqual(title_ocr.read_titles(initial),['KVB','LZB'])
        self.assertEqual(title_ocr.read_titles([crop('SCMT'),crop('')]),['SCMT',None])
        self.assertEqual(title_ocr.read_titles(initial),['KVB','LZB'])


if __name__ == '__main__':
    unittest.main()
