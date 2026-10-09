"""Selective processing and publication behavior with synthetic clocks/frames."""
from copy import deepcopy
import io
import json
import tempfile
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import numpy as np

from dmi_computer_vision.src.dmi.io.camera import CapturedFrame
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_computer_vision.src.dmi.pipeline.live import process_live
from dmi_computer_vision.tests.test_validation import frame as detected_frame
from dmi_robot_master.integration.processing_policy import DetectionPolicy
from dmi_robot_master.integration.publication import ChangePublisher, StatusHeartbeat, meaningful_change, project_pixels
from dmi_robot_master.integration.calibration import ValidatedCalibration
from dmi_robot_master.integration import calibration as calibration_module
from test_calibration import fit, points, CAMERA, ORIGIN, SIZE


def packet(index, received, image=None):
    return CapturedFrame(np.zeros((120, 160, 3), np.uint8) if image is None else image, index, received)


def snapshot(x=100, **metadata):
    return {'screen': 'Driver ID', 'visibility': 'clear', 'calibration_id': 'simulation-id',
            'targets': {'KEY_1': {'label': 'KEY_1', 'pixel': [x, 200], 'usable': False}}, **metadata}


class ProcessingTests(unittest.TestCase):
    def test_static_frames_skip_but_refresh_is_bounded(self):
        policy = DetectionPolicy(max_detection_fps=10, refresh_seconds=.5, burst_seconds=0)
        decisions = [policy.should_process(packet(i, i*.1), i*.1) for i in range(11)]
        self.assertEqual(decisions, [True, False, False, False, False, True, False, False, False, False, True])
        self.assertEqual(policy.stats()['detection_calls'], 3)

    def test_same_title_image_change_obeys_rate_cap(self):
        policy = DetectionPolicy(max_detection_fps=4, burst_seconds=0)
        self.assertTrue(policy.should_process(packet(0, 0), 0))
        image = np.zeros((120, 160, 3), np.uint8)
        image[50:65, 70:90] = 255  # Button/field region, no title change.
        self.assertFalse(policy.should_process(packet(1, .1, image), .1))
        self.assertTrue(policy.should_process(packet(2, .25, image), .25))
        self.assertEqual(policy.last_reason, 'change')

    def test_post_action_requires_a_new_capture_and_forces_detection(self):
        policy = DetectionPolicy(burst_seconds=0)
        policy.should_process(packet(0, 0), 0)
        policy.request_refresh(after_received_at=.05)
        self.assertFalse(policy.should_process(packet(1, .04), .06))
        self.assertTrue(policy.should_process(packet(2, .07), .07))
        self.assertEqual(policy.last_reason, 'forced')

    def test_session_restart_discards_prior_baseline(self):
        policy = DetectionPolicy(burst_seconds=0)
        policy.should_process(packet(0, 0), 0)
        policy.start_session()
        self.assertTrue(policy.should_process(packet(0, .01), .01))
        self.assertEqual(policy.detection_calls, 1)

    def test_resolution_and_capture_gap_force_detection(self):
        policy = DetectionPolicy(burst_seconds=0)
        policy.should_process(packet(0, 0), 0)
        resized = np.zeros((100, 200, 3), np.uint8)
        self.assertTrue(policy.should_process(packet(1, .05, resized), .05))
        self.assertTrue(policy.should_process(packet(2, 1.2, resized), 1.2))

    def test_optional_policy_does_not_refresh_latest_state_on_skips(self):
        base = time.monotonic() - 1
        policy = DetectionPolicy(max_detection_fps=10, refresh_seconds=.5, burst_seconds=0)
        class Source:
            def __init__(self): self.index = 0
            def read(self):
                if self.index == 3: raise EOFError()
                result = packet(self.index, base+self.index*.01)
                self.index += 1
                return result
        # Scheduling uses local processing time; deterministic fast reads stay
        # within refresh. Real receipts remain increasing and not in the future.
        state = LatestState()
        observed = []
        def detect(image, index, timestamp, *args):
            result = detected_frame(); result.update(frame_index=index, timestamp=timestamp)
            return result
        def skipped():
            observed.append(state.get(max_age_seconds=2)['received_at'])
            return True
        with tempfile.TemporaryDirectory() as directory, patch(
            'dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame', side_effect=detect) as detector:
            run = process_live(Source(), directory, processing_policy=policy, annotate=False,
                               latest_state=state, on_skipped=skipped)
        self.assertEqual(detector.call_count, 1)
        self.assertEqual(run.policy_skipped_frames, 2)
        self.assertEqual(observed, [base, base])
        self.assertIsNone(state.get())
        self.assertEqual(run.annotation_seconds, 0)


class ObservationFailureTests(unittest.TestCase):
    def test_source_failure_clears_published_targets_and_current_observation(self):
        from dmi_robot_master.integration.camera import IntegrationFrame
        from dmi_robot_master.integration.observe import observe
        class Source:
            def __init__(self):
                self.last_packet = None
                self.closed = False
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.closed = True
            def read(self):
                if self.last_packet is not None:
                    raise RuntimeError('camera lost')
                self.last_packet = IntegrationFrame(np.zeros((120,160,3),np.uint8),0,
                                                     time.monotonic(),'2026-10-08T00:00:00.000Z')
                return self.last_packet
            def stats(self):
                return {'captured_frames':1,'dequeued_frames':1,'overwritten_frames':0,'pending_frames':0}
        source = Source()
        state = LatestState()
        def detect(image,index,timestamp,*args):
            result=detected_frame()
            result.update(frame_index=index,timestamp=timestamp)
            return result
        with tempfile.TemporaryDirectory() as temporary, patch(
            'dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame',side_effect=detect):
            directory=Path(temporary)/'observation'
            with self.assertRaisesRegex(RuntimeError,'camera lost'):
                observe(source,directory,source_info={'kind':'recorded_replay'},
                        annotations=False,publication=True,latest_state=state)
            events=[json.loads(line) for line in (directory/'publication_review.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['source_status'],'error')
            self.assertEqual(events[-2]['targets'],{})
            self.assertTrue(source.closed)
            self.assertIsNone(state.get())


class PublicationTests(unittest.TestCase):
    def test_three_four_pixel_jitter_and_cumulative_drift(self):
        events = []
        publisher = ChangePublisher(events.append)
        publisher.update(snapshot(100), received_at=0, detected_at=0)
        publisher.update(snapshot(103), received_at=.1, detected_at=.1)
        publisher.update(snapshot(104), received_at=.2, detected_at=.2)
        self.assertEqual(publisher.updates, 1)
        self.assertEqual(publisher.current(.2)['targets']['KEY_1']['pixel'][0], 104)
        publisher.update(snapshot(105), received_at=.3, detected_at=.3)
        self.assertEqual(publisher.updates, 2)
        self.assertEqual(events[-1]['targets']['KEY_1']['pixel'], [105, 200])

    def test_semantics_removal_usable_calibration_and_titles_bypass_tolerance(self):
        baseline = snapshot()
        for key, value in [('screen','Main'), ('visibility','occluded'),
                           ('calibration_id','new'), ('titles',{'right':'New title'})]:
            changed = deepcopy(baseline); changed[key] = value
            self.assertTrue(meaningful_change(baseline, changed))
        removed = deepcopy(baseline); removed['targets'].clear()
        self.assertTrue(meaningful_change(baseline, removed))
        usable = deepcopy(baseline); usable['targets']['KEY_1']['usable'] = True
        self.assertTrue(meaningful_change(baseline, usable))
        renamed = deepcopy(baseline); renamed['targets']['KEY_2'] = renamed['targets'].pop('KEY_1')
        self.assertTrue(meaningful_change(baseline, renamed))

    def test_same_title_field_value_and_button_changes(self):
        result = detected_frame()
        a = project_pixels(result, frame_size=(640,160), include_field_values=True)
        result['right_display']['data_field']['value'] = '13'
        b = project_pixels(result, frame_size=(640,160), include_field_values=True)
        self.assertTrue(meaningful_change(a,b))
        result['right_display']['buttons'].clear()
        c = project_pixels(result, frame_size=(640,160), include_field_values=True)
        self.assertTrue(meaningful_change(b,c))

    def test_heartbeat_contains_evidence_without_resending_coordinates_and_expires(self):
        events=[]
        publisher=ChangePublisher(events.append, heartbeat_seconds=.5, max_evidence_age_seconds=1)
        publisher.update(snapshot(),received_at=0,detected_at=.1)
        publisher.tick(.5)
        status=events[-1]
        self.assertNotIn('targets',status)
        self.assertEqual(status['last_detection_at_monotonic'],.1)
        self.assertEqual(status['evidence_age_seconds'],.5)
        publisher.tick(1.1)
        self.assertEqual(events[-2]['targets'],{})
        self.assertEqual(events[-1]['source_status'],'stale')
        self.assertIsNone(publisher.current(1.1))
        publisher.update(snapshot(),received_at=1.2,detected_at=1.2)
        self.assertEqual(events[-1]['reason'],'recovered')
        publisher.close('error')
        self.assertEqual(events[-2]['targets'],{})
        self.assertIsNone(publisher.current(1.2))

    def test_background_heartbeat_expires_while_processing_is_blocked(self):
        events=[]
        publisher=ChangePublisher(events.append,heartbeat_seconds=.01,max_evidence_age_seconds=.03)
        now=time.monotonic()
        publisher.update(snapshot(),received_at=now,detected_at=now)
        with StatusHeartbeat(publisher):
            # No new source/detector calls occur during this stall.
            time.sleep(.07)
            self.assertTrue(any(e.get('reason')=='stale' and not e['targets'] for e in events))
            self.assertIsNone(publisher.current())

    def test_slow_detection_and_upstream_age_cannot_refresh_stale_targets(self):
        events=[]
        publisher=ChangePublisher(events.append,max_evidence_age_seconds=1)
        publisher.update(snapshot(),received_at=0,detected_at=.8,upstream_age_seconds=.3)
        self.assertEqual(events[-1]['reason'],'stale')
        self.assertEqual(events[-1]['targets'],{})
        self.assertIsNone(publisher.current(.8))


class TransportRateTests(unittest.TestCase):
    def test_remote_request_rate_cap_preserves_real_receipt_time(self):
        from dmi_robot_master.integration.camera import RemoteCamera
        from test_camera_integration import RemoteSourceTests
        replies=[RemoteSourceTests().response(100),RemoteSourceTests().response(103)]
        with RemoteCamera('http://pi:8080/frame.jpg',request_fps=10) as source, \
             patch('urllib.request.urlopen',side_effect=replies), \
             patch('dmi_robot_master.integration.camera.time.monotonic',side_effect=[0,0,.001,.001,.001,.1,.101]), \
             patch.object(source._stop,'wait') as wait:
            first=source.read()
            second=source.read()
            self.assertEqual(first.received_at,.001)
            self.assertEqual(second.received_at,.101)
            self.assertAlmostEqual(wait.call_args.args[0],.099)

    def test_bridge_encodes_selected_recent_frames_without_renewing_skipped_evidence(self):
        from unittest.mock import Mock
        import cv2
        from dmi_robot_master.integration.frame_bridge import FrameBridge
        source = Mock()
        bridge = FrameBridge(source, max_publish_fps=10)
        receipts = [0, .02, .06, .1, .2]
        def receive():
            index = source.read.call_count - 1
            if index == 4:
                bridge._stop.set()
            return packet(index, receipts[index])
        source.read.side_effect = receive
        with patch('dmi_robot_master.integration.frame_bridge.time.monotonic', side_effect=receipts), \
             patch('dmi_robot_master.integration.frame_bridge.cv2.imencode', wraps=cv2.imencode) as encode:
            bridge._publish()
        self.assertEqual(encode.call_count, 3)
        self.assertEqual(bridge._latest[:2], (4, .2))


class CalibrationCacheTests(unittest.TestCase):
    def test_unchanged_coordinates_do_not_refit_or_convert_and_actions_still_validate(self):
        calibration=fit()
        with patch('dmi_robot_master.integration.calibration.validate_calibration', wraps=calibration_module.validate_calibration) as validate:
            cache=ValidatedCalibration(calibration,frame_size=SIZE,camera=CAMERA,origin=ORIGIN)
            with patch('dmi_robot_master.integration.calibration.transform_point', wraps=calibration_module.transform_point) as transform:
                cache.convert_centers(points(),frame_size=SIZE,camera=CAMERA,origin=ORIGIN)
                first_calls=transform.call_count
                cache.convert_centers(points(),frame_size=SIZE,camera=CAMERA,origin=ORIGIN)
                self.assertEqual(transform.call_count,first_calls)
            self.assertEqual(validate.call_count,1)
            with self.assertRaises(ValueError):
                cache.revalidate_for_action(frame_size=SIZE,camera=CAMERA,origin=ORIGIN,hardware=True)
            self.assertEqual(validate.call_count,2)
            moved=deepcopy(CAMERA);moved['mount_id']='changed'
            with self.assertRaises(ValueError):
                cache.convert_centers(points(),frame_size=SIZE,camera=moved,origin=ORIGIN)


if __name__ == '__main__': unittest.main()
