"""Bounded replay and observation checks with fake capture; no hardware."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.io.camera import CapturedFrame
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_computer_vision.src.dmi.pipeline.live import process_live
from dmi_computer_vision.tests.test_validation import frame as detected_frame
from dmi_robot_master.integration.camera import ReplayCamera, RobotCamera, orient_image
from dmi_robot_master.integration.observe import observe


class FakeCapture:
    def __init__(self, count=8, fps=30):
        self.count, self.fps, self.index = count, fps, 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return self.fps

    def read(self):
        if self.index >= self.count:
            return False, None
        image = np.full((64, 96, 3), self.index, np.uint8)
        self.index += 1
        return True, image

    def release(self):
        self.released = True


def fake_detection(image, index, timestamp, *args):
    result = detected_frame()
    result.update(frame_index=index, timestamp=timestamp)
    return result


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / 'replay.mp4'
        self.path.touch()

    def tearDown(self):
        self.temporary.cleanup()

    def test_latest_slot_skips_and_preserves_final_frame_at_eof(self):
        capture = FakeCapture()
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture):
            with ReplayCamera(self.path, replay_fps=1000) as source:
                source._thread.join(timeout=2)
                self.assertFalse(source._thread.is_alive())
                self.assertEqual(source.stats(), {'captured_frames': 8, 'dequeued_frames': 0,
                                  'overwritten_frames': 7, 'pending_frames': 1})
                packet = source.read()
                self.assertEqual(packet.capture_index, 7)
                self.assertAlmostEqual(packet.source_video_seconds, 7 / 30)
                self.assertLessEqual(packet.received_at, time.monotonic())
                self.assertTrue(packet.received_at_utc.endswith('Z'))
                self.assertEqual(int(packet.image[0, 0, 0]), 7)
                with self.assertRaises(EOFError):
                    source.read()
            self.assertEqual(source.stats()['pending_frames'], 0)
            self.assertTrue(capture.released)

    def test_start_time_and_orientation_are_source_coordinates(self):
        capture = FakeCapture(count=5, fps=10)
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture):
            with ReplayCamera(self.path, replay_fps=1000, start_seconds=0.2, rotation=90) as source:
                source._thread.join(timeout=2)
                packet = source.read()
                self.assertEqual(packet.image.shape, (96, 64, 3))
                self.assertEqual(packet.capture_index, 2)
                self.assertEqual(packet.source_video_seconds, 0.4)

    def test_open_failure_and_shutdown_release_capture(self):
        capture = FakeCapture(fps=0)
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture):
            with ReplayCamera(self.path) as source:
                with self.assertRaisesRegex(RuntimeError, 'source FPS'):
                    source.read()
        self.assertTrue(capture.released)
        capture = FakeCapture(count=1000)
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture):
            with ReplayCamera(self.path, replay_fps=0.1) as source:
                source.read()
            self.assertFalse(source._thread.is_alive())
            self.assertTrue(capture.released)

    def test_stale_final_frame_is_rejected(self):
        capture = FakeCapture(count=1)
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture):
            with ReplayCamera(self.path, replay_fps=1000, timeout=0.005) as source:
                source._thread.join(timeout=2)
                time.sleep(0.01)
                with self.assertRaisesRegex(RuntimeError, 'stale'):
                    source.read()

    def test_live_eof_finishes_cleanly_and_clears_current_state(self):
        capture = FakeCapture(count=2)
        state = LatestState()
        output = Path(self.temporary.name) / 'output'
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture), \
             patch('dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame', side_effect=fake_detection):
            with ReplayCamera(self.path, replay_fps=5) as source:
                run = process_live(source, output, latest_state=state)
        self.assertEqual(run.stop_reason, 'eof')
        self.assertEqual(run.processed_frames, 2)
        self.assertIsNone(state.get())
        end = json.loads(run.jsonl_path.read_text().splitlines()[-1])
        self.assertEqual(end['stop_reason'], 'eof')
        self.assertIsNone(end['error'])

    def test_annotation_count_metadata_and_compact_log_match_processed_frames(self):
        capture = FakeCapture(count=5)
        output = Path(self.temporary.name) / 'observation'
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture), \
             patch('dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame', side_effect=fake_detection):
            report = observe(ReplayCamera(self.path, replay_fps=10), output,
                             source_info={'kind': 'recorded_replay'}, debug=True)
        self.assertTrue(report['simulation'])
        self.assertEqual(report['run']['stop_reason'], 'eof')
        metadata = [json.loads(line) for line in (output / 'processed_frames.jsonl').read_text().splitlines()]
        self.assertEqual(len(metadata), report['run']['processed_frames'])
        # Unpatched decoder verifies actual saved video frame count.
        video = cv2.VideoCapture(str(output / 'annotated.mp4'))
        decoded = 0
        while video.read()[0]:
            decoded += 1
        video.release()
        self.assertEqual(decoded, len(metadata))
        self.assertEqual([record['processed_frame_index'] for record in metadata], list(range(decoded)))
        with self.assertRaises(FileExistsError):
            observe(ReplayCamera(self.path), output, source_info={'kind': 'recorded_replay'})

    def test_detection_eoferror_is_failure_not_source_eof(self):
        capture = FakeCapture(count=1)
        state = LatestState()
        with patch('dmi_robot_master.integration.camera.cv2.VideoCapture', return_value=capture), \
             patch('dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame', side_effect=EOFError('detector bug')):
            with ReplayCamera(self.path, replay_fps=1) as source:
                with self.assertRaisesRegex(EOFError, 'detector bug'):
                    process_live(source, Path(self.temporary.name) / 'error', latest_state=state)
        self.assertIsNone(state.get())
        records = (Path(self.temporary.name) / 'error/results.jsonl').read_text().splitlines()
        self.assertEqual(json.loads(records[-1])['stop_reason'], 'error')


class CameraTests(unittest.TestCase):
    def test_reuses_one_camera_and_retains_original_receipt(self):
        image = np.zeros((4, 6, 3), np.uint8)
        received = time.monotonic() - 0.01
        with patch('dmi_robot_master.integration.camera.LatestCamera') as factory:
            camera = factory.return_value
            camera.read.return_value = CapturedFrame(image, 42, received)
            with RobotCamera(3, width=640, height=480, rotation=90) as source:
                packet = source.read()
            factory.assert_called_once_with(3, width=640, height=480, timeout=5.0)
            camera.__enter__.assert_called_once()
            camera.close.assert_called_once()
        self.assertEqual(packet.received_at, received)
        self.assertEqual(packet.capture_index, 42)
        self.assertEqual(packet.image.shape, (6, 4, 3))
        self.assertIsNone(packet.source_video_seconds)
        self.assertTrue(packet.received_at_utc.endswith('Z'))

    def test_bgr_contract_orientation_and_invalid_url(self):
        image = np.arange(18, dtype=np.uint8).reshape(2, 3, 3)
        self.assertTrue(np.array_equal(orient_image(image, 90, True), cv2.flip(cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), 1)))
        for invalid in [image.astype(float), image[:, :, 0]]:
            with self.assertRaises(ValueError):
                orient_image(invalid, 0, False)
        with self.assertRaises(ValueError):
            RobotCamera('http://example.invalid/stream')


class RemoteSourceTests(unittest.TestCase):
    def response(self, index=100, age=0.0, image=None):
        from unittest.mock import Mock
        if image is None:
            image = np.zeros((64, 96, 3), np.uint8)
        response = Mock()
        response.headers = {'Content-Type': 'image/jpeg', 'X-Camera-Session': 'fake-camera-session', 'X-Capture-Index': str(index),
                            'X-Capture-Age-Seconds': str(age)}
        response.read.return_value = cv2.imencode('.jpg', image)[1].tobytes()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_remote_unique_captures_normalized_indices_and_cleanup(self):
        from dmi_robot_master.integration.camera import RemoteCamera
        first = self.response(100)
        duplicate = self.response(100)
        next_capture = self.response(103)
        with patch('urllib.request.urlopen', side_effect=[first, duplicate, next_capture]) as request:
            with RemoteCamera('http://pi:8080/frame.jpg') as source:
                a = source.read()
                b = source.read()
                self.assertEqual((a.capture_index, b.capture_index), (0, 3))
                self.assertEqual(source.stats()['overwritten_frames'], 2)
                self.assertEqual(source.stats()['pending_frames'], 0)
                self.assertGreater(b.received_at, a.received_at)
                self.assertGreaterEqual(b.transport_round_trip_seconds, 0)
            self.assertIsNone(source.last_packet)
            self.assertEqual(request.call_count, 3)
            first.__exit__.assert_called_once()

    def test_repeated_frames_timeout_without_freshening_observation(self):
        from dmi_robot_master.integration.camera import RemoteCamera
        with patch('urllib.request.urlopen', side_effect=lambda *a, **k: self.response(1)):
            with RemoteCamera('http://pi:8080/frame.jpg', timeout=0.04) as source:
                packet = source.read()
                with self.assertRaisesRegex(RuntimeError, 'new captures'):
                    source.read()
                self.assertIs(source.last_packet, packet)
                self.assertEqual(source.stats()['dequeued_frames'], 1)

    def test_age_restart_malformed_jpeg_and_disconnect_fail(self):
        from dmi_robot_master.integration.camera import RemoteCamera
        invalid = self.response()
        invalid.read.return_value = b'not jpeg'
        for response in [self.response(age=2), self.response(age=float('nan')), invalid]:
            with self.subTest(response=response), patch('urllib.request.urlopen', return_value=response):
                with RemoteCamera('http://pi:8080/frame.jpg') as source:
                    with self.assertRaises((ValueError, RuntimeError, TypeError)):
                        source.read()
        with patch('urllib.request.urlopen', side_effect=[self.response(10), self.response(9)]):
            with RemoteCamera('http://pi:8080/frame.jpg') as source:
                source.read()
                with self.assertRaisesRegex(RuntimeError, 'restarted'):
                    source.read()
        changed = self.response(20)
        changed.headers['X-Camera-Session'] = 'new-session'
        with patch('urllib.request.urlopen', side_effect=[self.response(10), changed]):
            with RemoteCamera('http://pi:8080/frame.jpg') as source:
                source.read()
                with self.assertRaisesRegex(RuntimeError, 'session changed'):
                    source.read()
        with patch('urllib.request.urlopen', side_effect=OSError('disconnected')):
            with RemoteCamera('http://pi:8080/frame.jpg') as source:
                with self.assertRaises(OSError):
                    source.read()

    def test_bridge_freshness_loss_and_single_slot(self):
        from unittest.mock import Mock
        from dmi_robot_master.integration.frame_bridge import FrameBridge
        source = Mock()
        bridge = FrameBridge(source)
        self.assertIsNone(bridge.get())
        bridge._latest = (42, time.monotonic(), b'jpeg')
        index, age, data = bridge.get()
        self.assertEqual(index, 42)
        self.assertEqual(data, b'jpeg')
        self.assertLess(age, 1)
        bridge._latest = (43, time.monotonic() - 2, b'old')
        self.assertIsNone(bridge.get())
        bridge.error = 'camera disconnected'
        with self.assertRaisesRegex(RuntimeError, 'disconnected'):
            bridge.get()

    def test_transport_round_trip_is_included_in_remote_age_limit(self):
        from dmi_robot_master.integration.camera import RemoteCamera
        response = self.response(age=0.9)
        with patch('urllib.request.urlopen', return_value=response), \
             patch('dmi_robot_master.integration.camera.time.monotonic', side_effect=[0, 0, 0.2]):
            with RemoteCamera('http://pi:8080/frame.jpg', max_age_seconds=1) as source:
                with self.assertRaisesRegex(RuntimeError, 'transport delay'):
                    source.read()
        response.read.assert_called_once_with(RemoteCamera.MAX_JPEG_BYTES + 1)

    def test_bridge_handler_supplies_session_metadata_and_fails_on_loss(self):
        import io
        from unittest.mock import Mock
        from dmi_robot_master.integration.frame_bridge import FrameBridge, handler_for
        bridge = FrameBridge(Mock())
        bridge._latest = (42, time.monotonic(), b'jpeg')
        handler = handler_for(bridge).__new__(handler_for(bridge))
        handler.path = '/frame.jpg'
        handler.wfile = io.BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.send_error = Mock()
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)
        self.assertEqual(handler.wfile.getvalue(), b'jpeg')
        handler.send_header.assert_any_call('X-Camera-Session', bridge.session_id)
        bridge._latest = None
        handler.do_GET()
        handler.send_error.assert_called_with(503, 'No fresh camera frame')
        bridge.error = 'failed'
        handler.do_GET()
        handler.send_error.assert_called_with(503, 'Camera failed')
        handler.path = '/unknown'
        handler.do_GET()
        handler.send_error.assert_called_with(404)


if __name__ == '__main__':
    unittest.main()
