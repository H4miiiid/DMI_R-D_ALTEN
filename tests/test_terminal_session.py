"""Whole one-command terminal lifecycle with synthetic observations and fake robot."""
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from dmi_robot_master.integration.action_transport import FakeTransport, RobotLink
from dmi_robot_master.integration.actions import SessionMode
from dmi_robot_master.integration.calibration import save_calibration
from dmi_robot_master.integration.camera import IntegrationFrame
from dmi_robot_master.integration.press_label import run_terminal
from test_calibration import fit, CAMERA, ORIGIN, SIZE, record
from test_targets import direct_evidence


class SyntheticSource:
    def __init__(self):
        self.index=0
        self.closed=False
        self.last_packet=None
        self.value='12'
        self.ready=Event()
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def read(self):
        time.sleep(.01)
        self.last_packet=IntegrationFrame(np.zeros((SIZE[1],SIZE[0],3),np.uint8),self.index,
            time.monotonic(),datetime.now(timezone.utc).isoformat())
        self.index+=1
        return self.last_packet
    def stats(self):
        return {'captured_frames':self.index,'dequeued_frames':self.index,'overwritten_frames':0,'pending_frames':0}


class SessionTests(unittest.TestCase):
    def run_session(self, input_stream, *, mode=SessionMode.DRY_RUN, output_stream=None, source=None,preview=None):
        source=source or SyntheticSource()
        self.source=source
        directory=Path(self.temporary.name)
        calibration=directory/'calibration.json';save_calibration(fit(),calibration)
        context=directory/'context.json';context.write_text(json.dumps({'camera':CAMERA,'origin':ORIGIN}))
        transport=FakeTransport((380,470),delay_seconds=.1,on_done=lambda:setattr(source,'value','125'))
        self.transport=transport
        link=RobotLink(transport,limits_mm=(380,470),timeout_seconds=.3)
        def detector(image,index,timestamp,*args,target_evidence=None):
            result=record(index)['result']
            result.update(frame_index=index,timestamp=timestamp)
            result['right_display']['data_field']['value']=source.value
            for button in result['right_display']['buttons'].values():
                x,y=button['center']
                button.update(corners=[[x-2,y-2],[x+2,y-2],[x+2,y+2],[x-2,y+2]],
                              bbox=[x-2,y-2,x+2,y+2])
            if target_evidence is not None:
                target_evidence.update(direct_evidence())
                target_evidence['right_field_value']=source.value
            if index>=3:source.ready.set()
            return result
        with patch('dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame',side_effect=detector):
            return run_terminal(source,directory/'session',source_info={'kind':'synthetic','simulation':True},
                link=link,calibration_path=calibration,context_path=context,evidence_tolerance_px=1,
                mode=mode,input_stream=input_stream,output_stream=output_stream or io.StringIO(),
                verification_timeout_seconds=.2,preview=preview)

    def setUp(self):self.temporary=tempfile.TemporaryDirectory()
    def tearDown(self):self.temporary.cleanup()

    def test_detection_continues_during_command_and_busy_input_is_not_queued(self):
        source=SyntheticSource()
        completed=Event()
        class Output(io.StringIO):
            def write(self,text):
                result=super().write(text)
                if 'expected_change_observed_in_simulation' in text:completed.set()
                return result
        output=Output()
        class Input:
            count=0
            def readline(self):
                self.count+=1
                if self.count==1:
                    if not source.ready.wait(timeout=2):raise RuntimeError('No detector readiness')
                    return 'KEY_5\n'
                if self.count==2:return 'KEY_1\n'
                if not completed.wait(timeout=2):raise RuntimeError('Action failed to complete')
                return 'quit\n'
        report=self.run_session(Input(),mode=SessionMode.SIMULATED_PRESS,output_stream=output,source=source)
        self.assertEqual(self.transport.sent,[[1,150,250,200]])
        self.assertGreater(source.index,8)  # Camera/detection ran during the .1 s response wait.
        self.assertIn('not queued',output.getvalue())
        self.assertEqual(report['last_action']['response'],'DONE')
        self.assertEqual(report['last_action']['ui_outcome'],'expected_change_observed_in_simulation')
        self.assertTrue(source.closed)
        self.assertEqual(json.loads((Path(self.temporary.name)/'session/targets.json').read_text())['targets'],[])
        records=Path(report['action_log_path']).read_text().splitlines()
        self.assertEqual(len(records),1)

    def test_eof_and_quit_shutdown_without_packets(self):
        # Each subcase gets its own fresh directory/calibration files.
        for command in ['', 'quit\n']:
            with self.subTest(command=command):
                self.temporary.cleanup();self.temporary=tempfile.TemporaryDirectory()
                report=self.run_session(io.StringIO(command))
                self.assertEqual(self.transport.sent,[])
                self.assertTrue(self.source.closed)
                self.assertEqual(report['observation']['run']['stop_reason'],'stopped')

    def test_preview_and_cleanup_stay_on_main_thread(self):
        from threading import current_thread, main_thread
        shown=Event()
        calls=[]
        class Preview:
            def show(self,image):
                calls.append(current_thread())
                shown.set()
                return True
            def close(self):calls.append(current_thread())
        class Input:
            def readline(self):
                if not shown.wait(timeout=2):raise RuntimeError('No preview')
                return 'quit\n'
        self.run_session(Input(),preview=Preview())
        self.assertTrue(calls)
        self.assertTrue(all(thread is main_thread() for thread in calls))

    def test_udp_is_not_opened_without_explicit_readiness(self):
        from dmi_robot_master.integration.press_label import main
        with patch('dmi_robot_master.integration.press_label.ComProtocol') as protocol:
            status=main(['--camera','0','--transport','udp','--mode','physical-press',
                '--output-dir','unused','--calibration','unused','--calibration-context','unused',
                '--evidence-tolerance-px','1','--max-x-mm','380','--max-y-mm','470'])
        self.assertEqual(status,1)
        protocol.assert_not_called()

    def test_ctrl_c_coordinates_shutdown(self):
        class InterruptedInput:
            def readline(self):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_session(InterruptedInput())
        self.assertTrue(self.source.closed)
        self.assertEqual(self.transport.sent,[])


if __name__=='__main__':unittest.main()
