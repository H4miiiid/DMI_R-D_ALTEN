"""Live acquisition and shared-pipeline checks without requiring camera hardware."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi.io.camera import CapturedFrame, LatestCamera
from dmi.pipeline.live import process_live
from dmi.pipeline.frame_processor import FrameProcessor, process_frame
from dmi.temporal.smoothing import GeometryStabilizer, RightDisplayStabilizer
from dmi.temporal.left_tracking import LeftDisplayStabilizer
from dmi.evaluation.validation import validate_results
from dmi.output.json_writer import compact_state
from dmi.output.latest_state import LatestState
from test_validation import frame as detected_frame

spec = importlib.util.spec_from_file_location(
    'run_webcam', Path(__file__).resolve().parents[1] / 'scripts/run_webcam.py')
run_webcam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_webcam)


class FakeSource:
    def __init__(self, packets):
        self.packets = iter(packets)

    def read(self):
        value = next(self.packets)
        if isinstance(value, BaseException):
            raise value
        return value


class ControlledCapture:
    """Worker reads block until the test explicitly supplies a frame/failure."""
    def __init__(self):
        from queue import Queue
        self.queue = Queue()
        self.released = Event()
        self.read_count = 0
        self.next_read = Event()

    def isOpened(self):
        return True

    def read(self):
        self.read_count += 1
        self.next_read.set()
        return self.queue.get(timeout=3)

    def release(self):
        self.released.set()


class FrameSessionTest(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((160, 640, 3), np.uint8)

    def test_matches_existing_stabilizer_sequence(self):
        # Existing real-video geometry fixture includes both displays.
        source = Path(__file__).resolve().parents[1] / 'data/videos/dev/driver_id_12.mp4'
        capture = cv2.VideoCapture(str(source))
        ok, frame = capture.read()
        capture.release()
        self.assertTrue(ok)
        processor = FrameProcessor(max_gap_seconds=1.)
        old_states = GeometryStabilizer(), RightDisplayStabilizer(), LeftDisplayStabilizer()
        for i in range(6):
            expected = process_frame(frame, i, i / 30, *old_states)
            self.assertEqual(processor.process(frame, i / 30), expected)
        self.assertEqual(expected['right_display']['state'], 'Driver ID')
        capture = cv2.VideoCapture(str(source.with_name('level_0.mp4')))
        ok, changed_frame = capture.read()
        capture.release()
        self.assertTrue(ok)
        fresh = FrameProcessor().process(changed_frame, 2.)
        after_gap = processor.process(changed_frame, 2.)
        self.assertEqual(after_gap['right_display'], fresh['right_display'])
        self.assertEqual(after_gap['left_display'], fresh['left_display'])
        self.assertEqual(after_gap['right_display']['state'], 'Level')

    def test_gap_resolution_and_explicit_reset_forget_history(self):
        seen = []
        def observe(frame, index, timestamp, *states):
            seen.append(states)
            return {'frame_index': index, 'timestamp': timestamp}
        processor = FrameProcessor(max_gap_seconds=1.)
        with patch('dmi.pipeline.frame_processor.process_frame', side_effect=observe):
            processor.process(self.frame, 0.)
            processor.process(self.frame, .5)
            self.assertIs(seen[0][0], seen[1][0])
            processor.process(self.frame, 2.)
            self.assertEqual(processor.last_reset_reason, 'capture_gap')
            self.assertTrue(all(a is not b for a, b in zip(seen[1], seen[2])))
            processor.process(np.zeros((180, 640, 3), np.uint8), 2.1)
            self.assertEqual(processor.last_reset_reason, 'frame_size_changed')
            self.assertTrue(all(a is not b for a, b in zip(seen[2], seen[3])))
            processor.reset()
            self.assertEqual(processor.process(self.frame, 0.)['frame_index'], 0)

    def test_invalid_timestamps_do_not_advance_session(self):
        processor = FrameProcessor()
        processor.process(self.frame, 1.)
        for timestamp in [0., 1., -1., float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                processor.process(self.frame, timestamp)
        self.assertEqual(processor.process(self.frame, 2.)['frame_index'], 1)
        for gap in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                FrameProcessor(max_gap_seconds=gap)


class LiveProcessingTest(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((160, 640, 3), np.uint8)
        self.epoch = time.monotonic() - 10

    def packet(self, index, elapsed):
        return CapturedFrame(self.frame, index, self.epoch + elapsed)

    def records(self, directory):
        return [json.loads(line) for line in (directory / 'results.jsonl').read_text().splitlines()]

    def test_streamed_timestamps_drops_annotations_and_bounded_stop(self):
        source = FakeSource([self.packet(2, 0.), self.packet(5, .2), self.packet(6, 2.)])
        shown = []
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'session'
            def preview(image):
                # The latest result is already on disk, before preview/UI code.
                shown.append(image.copy())
                debug_records = [json.loads(line) for line in (directory / 'results_debug.jsonl').read_text().splitlines()]
                self.assertEqual(debug_records[-1]['result']['frame_index'], len(shown) - 1)
                return True
            run = process_live(source, directory, max_frames=3, preview=preview, debug=True)
            records = self.records(directory)
            self.assertEqual([r['type'] for r in records], ['session_start', 'snapshot', 'snapshot', 'session_end'])
            frames = [json.loads(line) for line in run.debug_path.read_text().splitlines()]
            results = [f['result'] for f in frames]
            self.assertEqual(validate_results(results, None)['frames'], 3)
            for invalid in (-1., float('nan'), float('inf'), .1):
                changed = deepcopy(results)
                changed[-1]['timestamp'] = invalid
                with self.assertRaises(ValueError):
                    validate_results(changed, None)
            self.assertEqual([f['result']['timestamp'] for f in frames], [0., .2, 2.])
            self.assertEqual([f['result']['frame_index'] for f in frames], [0, 1, 2])
            self.assertEqual([f['skipped_frames'] for f in frames], [2, 2, 0])
            self.assertEqual(frames[-1]['temporal_reset'], 'capture_gap')
            self.assertEqual(run.skipped_frames, 4)
            self.assertTrue(np.array_equal(cv2.imread(str(run.preview_path)), shown[-1]))
            self.assertEqual(run.stop_reason, 'max_frames')
            before = run.jsonl_path.read_bytes()
            with self.assertRaises(FileExistsError):
                process_live(source, directory, max_frames=1)
            self.assertEqual(run.jsonl_path.read_bytes(), before)

    def test_preview_stop_and_ctrl_c_finalize_results(self):
        for interrupt in (False, True):
            with self.subTest(interrupt=interrupt), tempfile.TemporaryDirectory() as temporary:
                source = FakeSource([self.packet(0, 0.), KeyboardInterrupt()])
                run = process_live(source, temporary, preview=None if interrupt else lambda _: False)
                self.assertEqual(run.processed_frames, 1)
                self.assertEqual(run.stop_reason, 'interrupted' if interrupt else 'preview_closed')
                self.assertEqual(self.records(Path(temporary))[-1]['stop_reason'], run.stop_reason)

    def test_failures_are_explicit_and_keep_completed_records(self):
        failures = [RuntimeError('disconnected'), self.packet(0, .5),
                    self.packet(1, -.1), self.packet(1, float('nan'))]
        for failure in failures:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                source = FakeSource([self.packet(0, 0.), failure])
                with self.assertRaises((RuntimeError, ValueError)):
                    process_live(source, temporary)
                records = self.records(Path(temporary))
                self.assertEqual(records[-1]['processed_frames'], 1)
                self.assertEqual(records[-1]['stop_reason'], 'error')
                self.assertTrue(records[-1]['error'])
                self.assertTrue((Path(temporary) / 'last_annotated.png').exists())

    def test_failed_first_read_creates_error_summary_without_fake_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'no camera'):
                process_live(FakeSource([RuntimeError('no camera')]), temporary)
            records = self.records(Path(temporary))
            self.assertEqual([r['type'] for r in records], ['session_start', 'session_end'])
            self.assertEqual(records[-1]['processed_frames'], 0)
            self.assertFalse((Path(temporary) / 'last_annotated.png').exists())

    def test_invalid_options_do_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            for limit in [0, -1, True, 1.5]:
                directory = Path(temporary) / 'invalid'
                with self.assertRaises(ValueError):
                    process_live(FakeSource([]), directory, max_frames=limit)
                self.assertFalse(directory.exists())

    def test_headless_cli_closes_source_and_refuses_existing_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = ['run_webcam.py', '--camera', '2', '--no-preview', '--max-frames', '2',
                    '--output-dir', temporary]
            source = FakeSource([self.packet(0, 0.), self.packet(1, .1)])
            with patch.object(sys, 'argv', args), patch.object(run_webcam, 'LatestCamera') as factory:
                factory.return_value.__enter__.return_value = source
                self.assertEqual(run_webcam.main(), 0)
                factory.return_value.__exit__.assert_called_once()
                self.assertEqual(self.records(Path(temporary))[0]['source'],
                                 {'kind': 'camera', 'index': 2})
                factory.reset_mock()
                self.assertEqual(run_webcam.main(), 1)
                factory.assert_not_called()

    def test_processing_failure_keeps_prior_frame_and_error_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = FakeSource([self.packet(0, 0.), self.packet(1, .1)])
            with patch('dmi.pipeline.frame_processor.process_frame', side_effect=[
                process_frame(self.frame, 0, 0.), RuntimeError('inference failed')]):
                with self.assertRaisesRegex(RuntimeError, 'inference failed'):
                    process_live(source, temporary)
            records = self.records(Path(temporary))
            self.assertEqual(records[-1]['processed_frames'], 1)
            self.assertEqual(records[-1]['stop_reason'], 'error')

    def test_latest_state_is_published_after_log_and_cleared_on_stop_or_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                store = LatestState()
                packets = [self.packet(0, 0.)]
                if failure:
                    packets.append(RuntimeError('disconnected'))
                observed = []
                def preview(_):
                    snapshot = store.get(max_age_seconds=60)
                    observed.append(snapshot)
                    self.assertEqual(snapshot['frame_index'], 0)
                    self.assertEqual(self.records(Path(temporary))[-1]['frame'], 0)
                    return True
                if failure:
                    with self.assertRaisesRegex(RuntimeError, 'disconnected'):
                        process_live(FakeSource(packets), temporary, latest_state=store,
                                     preview=preview)
                else:
                    run = process_live(FakeSource(packets), temporary, latest_state=store,
                                       preview=preview, max_frames=1)
                    self.assertGreaterEqual(run.max_receipt_to_result_seconds,
                                            run.max_capture_age_seconds)
                    self.assertGreaterEqual(run.max_capture_age_seconds, 10)
                    self.assertEqual(run.mean_receipt_to_result_seconds,
                                     run.max_receipt_to_result_seconds)
                self.assertEqual(len(observed), 1)
                self.assertIsNone(store.get())


class LatestStateTest(unittest.TestCase):
    def test_concurrent_reader_observes_one_complete_generation(self):
        store = LatestState()
        ready, done = Event(), Event()
        failures = []
        def publish():
            try:
                result = detected_frame()
                for index in range(100):
                    result['frame_index'] = index
                    result['right_display']['data_field']['value'] = str(index)
                    store.publish(result, capture_index=index,
                                  received_at=time.monotonic(), processed_at=time.monotonic(),
                                  frame_size=(640, 480))
                    ready.set()
                    time.sleep(.001)
            except Exception as exc:
                failures.append(exc)
            finally:
                done.set()
        with store:
            writer = Thread(target=publish)
            writer.start()
            self.assertTrue(ready.wait(1))
            checked = 0
            try:
                while not done.is_set():
                    snapshot = store.get()
                    self.assertIsNotNone(snapshot)
                    self.assertEqual(snapshot['state']['right_display']['fields']['driver_id']['value'],
                                     str(snapshot['frame_index']))
                    checked += 1
                    time.sleep(.001)
            finally:
                writer.join(timeout=2)
            self.assertFalse(writer.is_alive())
            self.assertFalse(failures)
            self.assertGreater(checked, 0)

    def test_freshness_unknown_replacement_and_copy_isolation(self):
        store = LatestState()
        self.assertIsNone(store.get())
        result = detected_frame()
        with store, patch('dmi.output.latest_state.time.monotonic', return_value=100.):
            store.publish(result, capture_index=4, received_at=99.5,
                          processed_at=100., frame_size=(640, 480))
            snapshot = store.get()
            self.assertEqual(snapshot['state'], compact_state(result))
            snapshot['state']['right_display']['buttons'].clear()
            result['right_display']['buttons'].clear()
            self.assertTrue(store.get()['state']['right_display']['buttons'])
            with patch('dmi.output.latest_state.time.monotonic', return_value=101.):
                self.assertIsNone(store.get())
            result['right_display'].update(state='unknown', title=None,
                                          data_field=None, visibility='occluded')
            store.publish(result, capture_index=5, received_at=99.9,
                          processed_at=100., frame_size=(640, 480),
                          temporal_reset='capture_gap')
            current = store.get()
            self.assertEqual(current['state']['right_display']['state'], 'unknown')
            self.assertEqual(current['state']['right_display']['fields'], {})
            self.assertEqual(current['state']['right_display']['buttons'], {})
            self.assertEqual(current['temporal_reset'], 'capture_gap')
        self.assertIsNone(store.get())
        with store:
            self.assertIsNone(store.get())

    def test_invalid_freshness_and_concurrent_session_rejected(self):
        store = LatestState()
        for age in (0, -1, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                store.get(max_age_seconds=age)
        with store:
            with self.assertRaisesRegex(RuntimeError, 'already belongs'):
                store.__enter__()


class CameraTest(unittest.TestCase):
    def test_close_discards_frame_returned_after_stop(self):
        capture = ControlledCapture()
        with patch('dmi.io.camera.cv2.VideoCapture', return_value=capture):
            camera = LatestCamera(timeout=.5)
            camera.__enter__()
            self.assertTrue(capture.next_read.wait(1))
            closer = Thread(target=camera.close)
            closer.start()
            self.assertTrue(camera._stop.wait(1))
            capture.queue.put((True, np.zeros((16, 16, 3), np.uint8)))
            closer.join(timeout=2)
            self.assertFalse(closer.is_alive())
            self.assertTrue(capture.released.is_set())
            self.assertFalse(camera._thread.is_alive())
            self.assertEqual(camera.stats()['pending_frames'], 0)
            self.assertIsNone(camera._pending)

    def test_latest_only_no_duplicate_delivery_and_release(self):
        capture = ControlledCapture()
        frame = np.zeros((16, 16, 3), np.uint8)
        with patch('dmi.io.camera.cv2.VideoCapture', return_value=capture):
            camera = LatestCamera(timeout=.5)
            with camera:
                capture.queue.put((True, frame.copy()))
                first = camera.read()
                self.assertEqual(first.capture_index, 0)
                # Sending two before consuming keeps only the newest.
                capture.queue.put((True, frame + 1))
                capture.queue.put((True, frame + 2))
                deadline = time.monotonic() + 1
                while capture.read_count < 4 and time.monotonic() < deadline:
                    time.sleep(.001)
                packet = camera.read()
                self.assertEqual(packet.capture_index, 2)
                self.assertTrue((packet.image == 2).all())
                self.assertGreater(packet.received_at, first.received_at)
                self.assertEqual(camera.stats(), {'captured_frames': 3,
                    'dequeued_frames': 2, 'overwritten_frames': 1, 'pending_frames': 0})
                with self.assertRaisesRegex(RuntimeError, 'timed out'):
                    camera.read()
                capture.queue.put((False, None))
                self.assertTrue(capture.released.wait(1))
                with self.assertRaisesRegex(RuntimeError, 'stopped delivering'):
                    camera.read()
            self.assertFalse(camera._thread.is_alive())

    def test_unavailable_camera_and_release(self):
        capture = ControlledCapture()
        capture.isOpened = lambda: False
        with patch('dmi.io.camera.cv2.VideoCapture', return_value=capture):
            with LatestCamera(timeout=.1) as camera:
                with self.assertRaisesRegex(RuntimeError, 'could not open camera'):
                    camera.read()
        self.assertTrue(capture.released.is_set())

    def test_read_stall_times_out_then_worker_releases_when_backend_returns(self):
        capture = ControlledCapture()
        with patch('dmi.io.camera.cv2.VideoCapture', return_value=capture):
            with LatestCamera(timeout=.02) as camera:
                with self.assertRaisesRegex(RuntimeError, 'timed out'):
                    camera.read()
                capture.queue.put((False, None))
                self.assertTrue(capture.released.wait(1))
            self.assertFalse(camera._thread.is_alive())

    def test_invalid_camera_options(self):
        for kwargs in [{'camera_index': -1}, {'camera_index': True}, {'width': 640},
                       {'width': 0, 'height': 480}, {'timeout': 0}, {'timeout': float('nan')}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LatestCamera(**kwargs)


if __name__ == '__main__':
    unittest.main()
