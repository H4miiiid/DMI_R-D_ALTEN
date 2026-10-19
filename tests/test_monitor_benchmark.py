"""Receipt pacing and invalid-input checks for observation-only measurements."""
import json
from pathlib import Path
from threading import Event
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from dmi_robot_master.integration.monitor_benchmark import (
    ReceiptCapture, TimelineCapture, controlled_phases,
)
from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor
from dmi_robot_master.integration.observe import AnnotationSink

MODULE = 'dmi_robot_master.integration.monitor_benchmark.'


class ReceiptReplayTests(unittest.TestCase):
    def metadata(self, directory, values):
        (Path(directory) / 'processed_frames.jsonl').write_text(''.join(
            json.dumps({'received_at_monotonic': value}) + '\n' for value in values))

    def test_invalid_receipts_are_rejected_before_opening_video(self):
        for values in ([], [float('nan')], [float('inf')], [1., 1.], [2., 1.]):
            with self.subTest(values=values), tempfile.TemporaryDirectory() as directory:
                self.metadata(directory, values)
                with patch(MODULE + 'cv2.VideoCapture') as capture:
                    with self.assertRaisesRegex(ValueError, 'finite and increasing'):
                        ReceiptCapture(Path(directory), Event())
                    capture.assert_not_called()

    def test_sidecar_offsets_pace_receipts_instead_of_playback_fps(self):
        image = np.ones((150, 1000, 3), np.uint8)
        capture = Mock()
        capture.read.side_effect = [(True, image), (True, image), (False, None)]
        capture.get.return_value = 5.
        stop = Mock()
        stop.wait.return_value = False
        with tempfile.TemporaryDirectory() as directory:
            self.metadata(directory, [50., 50.8])
            with patch(MODULE + 'cv2.VideoCapture', return_value=capture), patch(
                    MODULE + 'time.monotonic', return_value=100.):
                source = ReceiptCapture(Path(directory), stop)
                self.assertTrue(source.read()[0])
                self.assertTrue(source.read()[0])
                self.assertFalse(source.read()[0])
            self.assertEqual(stop.wait.call_args_list[0].args[0], 0.)
            self.assertAlmostEqual(stop.wait.call_args_list[1].args[0], .8)
            self.assertAlmostEqual(source.arrivals[1]['source_seconds'], .8)
            np.testing.assert_array_equal(image, 1)  # Source evidence is read-only.
            source.release()
            capture.release.assert_called_once()

    def test_sidecar_and_video_count_mismatches_fail(self):
        image = np.zeros((150, 1000, 3), np.uint8)
        for reads in ([(False, None)], [(True, image), (True, image)]):
            with self.subTest(reads=len(reads)), tempfile.TemporaryDirectory() as directory:
                self.metadata(directory, [50.])
                capture = Mock()
                capture.read.side_effect = reads
                with patch(MODULE + 'cv2.VideoCapture', return_value=capture):
                    source = ReceiptCapture(Path(directory), Event())
                    with self.assertRaisesRegex(ValueError, 'sidecar receipts'):
                        while source.read()[0]:
                            pass
                    source.release()
                capture.release.assert_called_once()


class PreviewAndFixtureTests(unittest.TestCase):
    def test_stopped_fixture_does_not_emit_more_receipts(self):
        stop = Event()
        stop.set()
        phases = [{'phase': 0, 'duration_seconds': 1., 'start_seconds': 0., 'image': 'frame'}]
        source = TimelineCapture(phases, {'frame': np.zeros((2, 2, 3), np.uint8)}, stop)
        self.assertEqual(source.read(), (False, None))
        self.assertEqual(source.arrivals, [])

    def test_reused_preview_ages_original_evidence_after_new_capture(self):
        source = Mock()
        source.last_packet.received_at = 19.
        preview = Mock()
        sink = AnnotationSink(Path('.'), source, preview)
        sink.last_image = np.zeros((160, 200, 3), np.uint8)
        sink.last_received = 10.
        with patch('dmi_robot_master.integration.observe.time.monotonic', return_value=20.), patch(
                'dmi_robot_master.integration.observe.cv2.putText') as text:
            sink.idle()
        self.assertIn('age 10.00s', text.call_args.args[1])
        self.assertEqual(sink.last_received, 10.)
        np.testing.assert_array_equal(sink.last_image, 0)
        preview.show.assert_called_once()


class RecordedMonitorChangeTests(unittest.TestCase):
    def test_same_title_values_are_observed_before_numeric_confirmation(self):
        for arrangement, initial in (('connected', '23'), ('separated', '12')):
            with self.subTest(arrangement=arrangement):
                _, images = controlled_phases(arrangement)
                processor = FrameProcessor(collect_target_evidence=True)
                processor.process(images['driver'], 0.)
                changed = processor.process(images['field'], .3)
                self.assertEqual(processor.target_evidence['right_state'], 'Driver ID')
                self.assertEqual(processor.target_evidence['right_field_value'], '47')
                self.assertEqual(changed['right_display']['data_field']['value'], initial)
                # A missing region must not keep either a confirmed label or
                # raw supports from the preceding actual detection.
                lost = processor.process(images['left_only'], .6)
                self.assertEqual(lost['right_display']['state'], 'unknown')
                self.assertFalse(processor.target_evidence['right_buttons'])
                self.assertIsNone(processor.target_evidence['right_field_value'])

    def test_connected_same_title_control_loss_is_seen_on_next_detection(self):
        _, images = controlled_phases('connected')
        processor = FrameProcessor(collect_target_evidence=True)
        baseline = processor.process(images['field'], 0.)
        changed = processor.process(images['button'], .3)
        self.assertIn('cancel', baseline['right_display']['buttons'])
        self.assertNotIn('cancel', changed['right_display']['buttons'])
        self.assertNotIn('cancel', processor.target_evidence['right_buttons'])
        self.assertEqual(processor.target_evidence['right_field_value'], '47')

    @unittest.expectedFailure
    def test_confirmed_driver_transition_has_current_image_key_geometry(self):
        """Known Step 5 finding: confirmation precedes geometry convergence.

        Keep this failure visible until the transition correction is reviewed.
        Three pixels is the existing diagnostic keypad recheck, not a changed
        runtime tolerance or a physical calibration claim.
        """
        _, images = controlled_phases('connected')
        reference = FrameProcessor(collect_target_evidence=True)
        reference.process(images['driver'], 0.)
        processor = FrameProcessor(collect_target_evidence=True)
        for index in range(6):
            processor.process(images['main'], index * .3)
        for index in range(6, 11):
            current = processor.process(images['driver'], index * .3)
        self.assertEqual(current['right_display']['state'], 'Driver ID')
        for digit in range(10):
            label = f'digit_{digit}'
            observed = processor.target_evidence['right_buttons'][label]
            expected = reference.target_evidence['right_buttons'][label]
            self.assertLessEqual(float(np.linalg.norm(np.array(observed) - expected)), 3.)


if __name__ == '__main__':
    unittest.main()
