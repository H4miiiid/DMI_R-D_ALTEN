"""Cross-phase acceptance with controlled observations; no devices or sockets."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
from queue import Queue
from threading import Event, Thread
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_robot_master.integration.action_transport import FakeTransport, RobotLink
from dmi_robot_master.integration.actions import LabelActions, SessionMode
from dmi_robot_master.integration.calibration import save_calibration
from dmi_robot_master.integration.camera import IntegrationFrame
from dmi_robot_master.integration.observe import observe
from dmi_robot_master.integration.targets import CurrentTargets, read_target, select_target
from test_calibration import CAMERA, ORIGIN, SIZE, fit, record
from test_targets import direct_evidence


class ControlledSource:
    """One pending frame; tests explicitly provide or fail the source."""
    def __init__(self):
        self.pending = Queue(maxsize=1)
        self.index = 0
        self.last_packet = None
        self.closed = False
        self.result = None
        self.evidence = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self):
        item = self.pending.get(timeout=3)
        if isinstance(item, BaseException):
            raise item
        self.result, self.evidence = item
        self.last_packet = IntegrationFrame(np.zeros((SIZE[1], SIZE[0], 3), np.uint8),
            self.index, time.monotonic(), datetime.now(timezone.utc).isoformat())
        self.index += 1
        return self.last_packet

    def stats(self):
        return {'captured_frames': self.index, 'dequeued_frames': self.index,
                'overwritten_frames': 0, 'pending_frames': self.pending.qsize()}


class OfflineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.calibration = fit()
        self.calibration_path = self.directory / 'calibration.json'
        save_calibration(self.calibration, self.calibration_path)
        self.context = {'camera': CAMERA, 'origin': ORIGIN}
        self.context_path = self.directory / 'context.json'
        self.context_path.write_text(json.dumps(self.context))
        self.source = ControlledSource()
        self.current, self.state = CurrentTargets(), LatestState()
        self.failures = []
        self.links = []
        self.actions = []
        def detector(image, index, timestamp, *args, target_evidence=None):
            result = deepcopy(self.source.result)
            result.update(frame_index=index, timestamp=timestamp)
            target_evidence.update(deepcopy(self.source.evidence))
            return result
        self.detector_patch = patch('dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame',
                                    side_effect=detector)
        self.detector_patch.start()
        def observe_source():
            try:
                observe(self.source, self.directory / 'live', source_info={'kind': 'synthetic', 'simulation': True},
                    debug=True, annotations=False, export_targets=True, target_history=True,
                    calibration_path=self.calibration_path, calibration_context=self.context,
                    evidence_tolerance_px=1, heartbeat_seconds=.02, max_evidence_age_seconds=.3,
                    current_targets=self.current, latest_state=self.state)
            except Exception as exc:
                self.failures.append(exc)
        self.worker = Thread(target=observe_source)
        self.worker.start()
        self.push()

    def tearDown(self):
        for action in self.actions:
            action.close()
        if self.worker.is_alive():
            self.source.pending.put(EOFError(), timeout=1)
        self.worker.join(timeout=4)
        self.detector_patch.stop()
        self.temporary.cleanup()
        self.assertFalse(self.worker.is_alive())

    def wait_for(self, predicate):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.005)
        self.fail('Controlled integration did not reach expected state')

    def push(self, *, screen='Driver ID', value='12', missing=None):
        index = self.source.index
        result = record(index)['result']
        result['right_display']['state'] = screen
        result['right_display']['data_field']['value'] = value
        evidence = direct_evidence()
        evidence.update(right_state=screen, right_field_value=value)
        if missing:
            result['right_display']['buttons'].pop('digit_' + missing[-1])
            evidence['right_buttons'].pop('digit_' + missing[-1])
        self.source.pending.put((result, evidence), timeout=1)
        self.wait_for(lambda: self.current.get() is not None and
                      self.current.get()['frame_index'] == index and
                      self.state.get() is not None and self.state.get()['frame_index'] == index)

    def action(self, *, response='DONE', on_done=None, limits=(380, 470)):
        transport = FakeTransport(limits, response=response, on_done=on_done)
        link = RobotLink(transport, limits_mm=limits, timeout_seconds=.03)
        finished = Event()
        log = io.StringIO()
        action = LabelActions(self.current, self.state, link,
            calibration_path=self.calibration_path, context_path=self.context_path,
            source_info={'kind': 'synthetic', 'simulation': True}, mode=SessionMode.SIMULATED_PRESS,
            verification_timeout_seconds=.2, on_result=lambda result: finished.set(), log_stream=log)
        self.actions.append(action)
        return action, transport, finished, log

    def test_three_selected_keys_convert_dispatch_and_controlled_ui_verification(self):
        # New observations are intentionally controlled, not recorded causation.
        value = ['12']
        label = ['KEY_5']
        def changed():
            value[0] += label[0][-1]
            # Push from a separate test worker after DONE has been returned.
            def newer():
                time.sleep(.02)
                self.source.pending.put((self.result_with_value(value[0]),
                    {**direct_evidence(), 'right_field_value': value[0]}), timeout=1)
            thread = Thread(target=newer)
            thread.start()
        action, transport, finished, log = self.action(on_done=changed)
        for key in ('KEY_4', 'KEY_5', 'KEY_6'):
            label[0] = key
            finished.clear()
            self.assertTrue(action.preview(key)['accepted'])
            self.assertTrue(action.request(key)['accepted'])
            self.assertTrue(finished.wait(1))
            self.assertEqual(action.last_result['response'], 'DONE')
            self.assertEqual(action.last_result['ui_outcome'], 'expected_change_observed_in_simulation')
        self.assertEqual(transport.sent, [[1,100,250,200], [1,150,250,200], [1,200,250,200]])
        self.assertEqual(len(log.getvalue().splitlines()), 3)
        self.assertEqual(read_target(self.directory / 'live', 'KEY_5')['kind'], 'button')

    def result_with_value(self, value):
        result = record(self.source.index)['result']
        result['right_display']['data_field']['value'] = value
        return result

    def test_wrong_screen_removal_invalid_calibration_and_bounds_never_dispatch(self):
        action, transport, _, _ = self.action()
        self.push(screen='Level')
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.push(missing='KEY_5')
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.push()
        bounded, _, _, _ = self.action(limits=(149,470))
        self.assertFalse(bounded.request('KEY_5')['accepted'])
        broken = deepcopy(self.calibration)
        broken['homography'][0][2] += 100
        self.calibration_path.write_text(json.dumps(broken))
        self.push()
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.assertIsNone(next(t for t in self.current.get()['targets'] if t['label']=='KEY_5')['mm'])
        self.assertEqual(transport.sent, [])

    def test_stale_files_evidence_and_camera_failure_invalidate_actions(self):
        action, transport, _, _ = self.action()
        self.wait_for(lambda: json.loads((self.directory / 'live/target_status.json').read_text())['source_status']=='observed')
        snapshot = json.loads((self.directory / 'live/targets.json').read_text())
        status = json.loads((self.directory / 'live/target_status.json').read_text())
        with self.assertRaisesRegex(ValueError, 'stale'):
            select_target(snapshot, status, 'KEY_5', now_utc=datetime.now(timezone.utc)+timedelta(seconds=2))
        self.wait_for(lambda: self.current.get() is None)
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.wait_for(lambda: json.loads((self.directory / 'live/targets.json').read_text())['targets']==[])
        self.push()
        self.source.pending.put(RuntimeError('controlled camera loss'), timeout=1)
        self.worker.join(timeout=2)
        self.assertFalse(self.worker.is_alive())
        self.assertEqual(len(self.failures), 1)
        self.assertTrue(self.source.closed)
        self.assertIsNone(self.current.get())
        self.assertIsNone(self.state.get())
        self.assertEqual(json.loads((self.directory / 'live/targets.json').read_text())['targets'], [])
        self.assertEqual(json.loads((self.directory / 'live/target_status.json').read_text())['source_status'], 'error')
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.assertEqual(transport.sent, [])

    def test_error_timeout_disconnect_latch_while_observation_continues(self):
        for response in ('ERROR', 'TIMEOUT', 'DISCONNECT'):
            with self.subTest(response=response):
                self.push()
                action, transport, finished, log = self.action(response=response)
                self.assertTrue(action.request('KEY_5')['accepted'])
                self.assertTrue(finished.wait(1))
                self.assertEqual(action.last_result['response'], response)
                self.push()
                self.assertFalse(action.request('KEY_6')['accepted'])
                self.assertEqual(transport.sent, [[1,150,250,200]])
                self.assertEqual(len(log.getvalue().splitlines()), 1)
                self.assertIsNotNone(self.current.get())


if __name__ == '__main__':
    unittest.main()
