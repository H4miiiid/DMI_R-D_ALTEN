"""Picamera2 bridge source tests without Pi libraries or physical devices."""
from threading import Event, Thread
from types import SimpleNamespace
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import Mock, patch

import numpy as np

from dmi_robot_master.integration.picamera_source import PicameraSource


class PicameraSourceTests(unittest.TestCase):
    def setUp(self):
        self.camera = Mock()
        self.camera.camera_configuration.return_value = {
            'main': {'size': (2304, 1728), 'format': 'RGB888'},
            'sensor': {'output_size': (2304, 1296), 'bit_depth': 10},
        }
        self.factory = Mock(return_value=self.camera)
        self.transform = Mock(return_value='both-flips')
        self.module = patch.dict('sys.modules',
            picamera2=SimpleNamespace(Picamera2=self.factory),
            libcamera=SimpleNamespace(Transform=self.transform,
                controls=SimpleNamespace(AfModeEnum=SimpleNamespace(Continuous=2))))
        self.module.start()
        self.addCleanup(self.module.stop)

    def request(self, image):
        return SimpleNamespace(make_array=lambda name: image)

    def test_camera_selection_bgr_copy_and_latest_slot(self):
        image = np.zeros((2, 3, 3), np.uint8)
        image[0, 0] = [12, 34, 56]
        with PicameraSource(1, width=640, height=480) as source:
            self.factory.assert_called_once_with(camera_num=1)
            self.camera.create_video_configuration.assert_called_once_with(
                main={'size': (640, 480), 'format': 'RGB888'},
                sensor={'output_size': (2304, 1728), 'bit_depth': 10},
                transform='both-flips',
                controls={'AfMode': 2, 'ExposureValue': -2.0, 'FrameRate': 30.0}, queue=False)
            self.camera.start.assert_called_once_with(show_preview=False)
            self.camera.post_callback(self.request(image))
            image[0, 0] = [98, 76, 54]
            self.camera.post_callback(self.request(image))
            packet = source.read()
            self.assertEqual(packet.capture_index, 1)
            image[:] = 0
            self.assertEqual(packet.image[0, 0].tolist(), [98, 76, 54])
            self.assertTrue(packet.received_at_utc.endswith('Z'))
            self.assertEqual(source.stats(), {'captured_frames': 2, 'dequeued_frames': 1,
                                             'overwritten_frames': 1, 'pending_frames': 0})
        self.camera.stop.assert_called_once()
        self.camera.close.assert_called_once()

    def test_default_profile_and_actual_sensor_mode_report(self):
        with PicameraSource(1) as source:
            self.assertEqual(source.size, (2304, 1728))
            self.transform.assert_called_once_with(hflip=True, vflip=True)
            settings = source.capture_settings
            self.assertEqual(settings['rotation_clockwise'], 180)
            # Do not falsely report the requested size as an exact native mode.
            self.assertEqual(settings['sensor']['output_size'], (2304, 1296))
            self.assertEqual(settings['autofocus'], 'continuous')
            self.assertEqual(settings['exposure_ev'], -2.0)

    def test_bridge_defaults_choose_capture_profile_without_extra_flags(self):
        from dmi_robot_master.integration.frame_bridge import main
        with patch('dmi_robot_master.integration.frame_bridge.PicameraSource') as source, \
                patch('dmi_robot_master.integration.frame_bridge.FrameBridge') as bridge, \
                patch('dmi_robot_master.integration.frame_bridge.ThreadingHTTPServer') as server, \
                redirect_stdout(io.StringIO()):
            source.return_value.capture_settings = None
            server.return_value.__enter__.return_value.serve_forever.side_effect = KeyboardInterrupt
            self.assertEqual(main(['--bind', '0.0.0.0']), 0)
            source.assert_called_once_with(1, width=None, height=None)
            bridge.assert_called_once_with(source.return_value, 1.0, 10.0)

    def test_capture_error_discards_pending_frame(self):
        with PicameraSource(0) as source:
            source._capture(self.request(np.zeros((2, 3, 3), np.uint8)))
            source._capture(self.request(np.zeros((2, 3), np.uint8)))
            with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                source.read()
            self.assertEqual(source.stats()['pending_frames'], 0)

    def test_no_frame_timeout_and_stale_frame(self):
        with PicameraSource(0, timeout=.01) as source:
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                source.read()
            with patch('dmi_robot_master.integration.picamera_source.time.monotonic', return_value=0):
                source._capture(self.request(np.zeros((2, 3, 3), np.uint8)))
            with self.assertRaisesRegex(RuntimeError, 'stale'):
                source.read()

    def test_close_unblocks_reader_and_prevents_late_frames(self):
        source = PicameraSource(0)
        source.__enter__()
        started = Event()
        failures = []
        def read():
            started.set()
            try:
                source.read()
            except RuntimeError as exc:
                failures.append(str(exc))
        worker = Thread(target=read)
        worker.start()
        self.assertTrue(started.wait(1))
        source.close()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, ['Picamera2 source is closed'])
        source._capture(self.request(np.zeros((2, 3, 3), np.uint8)))
        self.assertEqual(source.stats()['pending_frames'], 0)
        source.close()
        self.camera.close.assert_called_once()

    def test_start_failure_releases_camera(self):
        self.camera.start.side_effect = RuntimeError('Camera busy')
        with self.assertRaisesRegex(RuntimeError, 'Camera busy'):
            PicameraSource(0).__enter__()
        self.camera.close.assert_called_once()

    def test_invalid_options_and_unopened_read(self):
        for options in ({'index': -1}, {'index': 0, 'width': 640},
                        {'index': 0, 'timeout': 0}):
            with self.assertRaises(ValueError):
                PicameraSource(**options)
        with self.assertRaisesRegex(RuntimeError, 'Open the camera'):
            PicameraSource(0).read()


if __name__ == '__main__':
    unittest.main()
