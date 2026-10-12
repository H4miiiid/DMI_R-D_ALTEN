"""Single-label action semantics; all robot/transport/camera objects are fake."""
from copy import deepcopy
import io
import json
from pathlib import Path
from threading import Event, Lock
import tempfile
import time
import unittest
from unittest.mock import patch

from dmi_robot_master.integration.actions import LabelActions, SessionMode, rounded_mm
from dmi_robot_master.integration.action_transport import FakeTransport, RobotLink
from dmi_robot_master.integration.calibration import save_calibration
from test_calibration import CAMERA, ORIGIN, SIZE, fit, points


class MemoryTargets:
    def __init__(self, calibration):
        self.lock=Lock()
        self.value='12'
        self.observation={'session_id':'fake-session','frame_index':0,'capture_index':0,
            'screen':'Driver ID','simulation':True,'calibration_provenance':'simulation',
            'calibration_id':calibration['calibration_id'],'frame_size':list(SIZE),
            'received_at_monotonic':time.monotonic(),'upstream_age_seconds':0,
            'support_centers':points(),'support_tolerance_px':1,'direct_driver_value':'12',
            'targets':{key:{'label':key,'kind':'button','display':'right','pixel':xy,
                            'mm':next(m['mm'] for m in calibration['matched_points'] if m['label']==key),
                            'usable':True} for key,xy in points().items()}}

    def action_observation(self):
        with self.lock:
            if time.monotonic()-self.observation['received_at_monotonic']+self.observation['upstream_age_seconds']>1.5:
                return None
            return deepcopy(self.observation)

    def update_value(self,value,*,receipt=None):
        with self.lock:
            self.value=value
            self.observation['direct_driver_value']=value
            self.observation['frame_index']+=1
            self.observation['capture_index']+=1
            self.observation['received_at_monotonic']=time.monotonic() if receipt is None else receipt


class MemoryState:
    def __init__(self,targets):self.targets=targets
    def get(self,**kwargs):
        observation=self.targets.action_observation()
        if observation is None:return None
        return {'frame_index':observation['frame_index'],'received_at':observation['received_at_monotonic'],
                'state':{'right_display':{'state':observation['screen'],
                         'fields':{'driver_id':{'value':self.targets.value}}}}}


class LabelActionTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.directory=Path(self.temporary.name)
        self.calibration=fit()
        self.path=self.directory/'calibration.json';save_calibration(self.calibration,self.path)
        self.context=self.directory/'context.json'
        self.context.write_text(json.dumps({'camera':CAMERA,'origin':ORIGIN}))
        self.targets=MemoryTargets(self.calibration)
        self.state=MemoryState(self.targets)
        self.actions=[]

    def tearDown(self):
        for action in self.actions:action.close()
        self.temporary.cleanup()

    def action(self,mode='simulated-press',response='DONE',delay=0,on_done=None,**kwargs):
        transport=FakeTransport((380,470),response=response,delay_seconds=delay,on_done=on_done)
        link=RobotLink(transport,limits_mm=(380,470),timeout_seconds=.03)
        action=LabelActions(self.targets,self.state,link,calibration_path=self.path,
            context_path=self.context,source_info={'kind':'synthetic','simulation':True},
            mode=SessionMode(mode),verification_timeout_seconds=.05,**kwargs)
        self.actions.append(action)
        return action,transport

    def complete(self,action):
        if action._thread is not None:
            action._thread.join(timeout=2)
            self.assertFalse(action._thread.is_alive())
        return action.last_result

    def test_default_dry_run_printable_preview_sends_nothing(self):
        action,transport=self.action(mode='dry-run')
        result=action.request('KEY_5')
        self.assertTrue(result['accepted'])
        self.assertAlmostEqual(result['mm'][0],150,places=3)
        self.assertEqual(result['commanded_mm'],[150,250])
        self.assertEqual(result['response'],'NOT_SENT')
        self.assertFalse(transport.sent)
        self.assertFalse(transport.robot.calls)

    def test_all_command_modes_use_existing_correct_payloads(self):
        for mode in ['simulated-press','physical-press','move-only']:
            with self.subTest(mode=mode):
                action,transport=self.action(mode=mode)
                action.request('KEY_5');result=self.complete(action)
                expected=[3,150,250,0] if mode=='move-only' else [1,150,250,200]
                self.assertEqual(transport.sent,[expected])
                self.assertEqual(result['response'],'DONE')
                self.assertTrue(result['simulation_transport'])
                self.assertEqual(transport.robot.calls,[('move',150,250,0)] if mode=='move-only' else [('press',150,250,200)])

    def test_done_without_ui_input_is_unconfirmed_and_logged_once(self):
        stream=io.StringIO()
        action,transport=self.action(log_stream=stream)
        action.request('KEY_1');result=self.complete(action)
        self.assertEqual(result['response'],'DONE')
        self.assertEqual(result['ui_outcome'],'unconfirmed')
        records=[json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['source_frame'],0)
        self.assertEqual(records[0]['calibration_id'],self.calibration['calibration_id'])
        self.assertEqual(len(transport.sent),1)

    def test_error_timeout_disconnect_disable_further_commands_without_retry(self):
        for response in ['ERROR','TIMEOUT','DISCONNECT']:
            with self.subTest(response=response):
                action,transport=self.action(response=response)
                action.request('KEY_5');result=self.complete(action)
                self.assertEqual(result['response'],response)
                self.assertFalse(result['accepted'])
                self.assertFalse(action.request('KEY_1')['accepted'])
                self.assertEqual(len(transport.sent),1)

    def test_busy_requests_are_rejected_not_queued(self):
        action,transport=self.action(delay=.02)
        self.assertTrue(action.request('KEY_5')['accepted'])
        second=action.request('KEY_1')
        self.assertFalse(second['accepted'])
        self.assertIn('not queued',second['reason'])
        self.complete(action)
        self.assertEqual(len(transport.sent),1)

    def test_wrong_screen_stale_missing_unusable_and_bounds(self):
        for mutation in [
            lambda o:o.update(screen='Main'),
            lambda o:o.update(received_at_monotonic=time.monotonic()-2),
            lambda o:o['targets'].pop('KEY_5'),
            lambda o:o['targets']['KEY_5'].update(usable=False),
            lambda o:o['targets']['KEY_5'].update(mm=[999,999]),
            lambda o:o['targets']['KEY_1'].update(label='KEY_5'),
        ]:
            with self.subTest(mutation=mutation):
                before=deepcopy(self.targets.observation)
                mutation(self.targets.observation)
                action,transport=self.action()
                self.assertFalse(action.request('KEY_5')['accepted'])
                self.assertFalse(transport.sent)
                self.targets.observation=before
        action,transport=self.action()
        action.link.commands.xy_limits_mm=(149,470)
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.assertFalse(transport.sent)

    def test_target_outside_validated_keypad_cannot_be_forced_usable(self):
        from dmi_robot_master.integration.calibration import transform_point
        target=self.targets.observation['targets']['KEY_5']
        target.update(pixel=[10,10],mm=transform_point(self.calibration['homography'],[10,10]),usable=True)
        self.targets.observation['support_tolerance_px']=10000
        self.targets.observation['support_centers']['KEY_5']=[10,10]
        action,transport=self.action()
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.assertFalse(transport.sent)

    def test_target_removed_between_selection_and_dispatch_sends_nothing(self):
        action,transport=self.action()
        original=action._validate
        calls=[0]
        def validate(observation,target):
            result=original(observation,target)
            calls[0]+=1
            if calls[0]==1:self.targets.observation['targets'].pop('KEY_5')
            return result
        with patch.object(action,'_validate',side_effect=validate):
            action.request('KEY_5');result=self.complete(action)
        self.assertFalse(result['accepted'])
        self.assertFalse(transport.sent)

    def test_dispatch_log_timestamp_matches_frame_advanced_during_validation(self):
        from dmi_robot_master.integration.calibration import transform_point
        old_time='2026-10-12T10:00:00.000Z'
        new_time='2026-10-12T10:00:00.100Z'
        self.targets.observation['observed_at']=old_time
        stream=io.StringIO()
        action,transport=self.action(log_stream=stream)
        original=action._validate
        calls=[0]
        def validate(observation,target):
            result=original(observation,target)
            calls[0]+=1
            # Preview has completed; advance detection during dispatch validation.
            if calls[0]==2:
                with self.targets.lock:
                    current=self.targets.observation
                    current.update(frame_index=1,capture_index=1,observed_at=new_time,
                                   received_at_monotonic=time.monotonic())
                    moved=current['targets']['KEY_5']
                    moved['pixel']=[moved['pixel'][0]+.25,moved['pixel'][1]]
                    moved['mm']=transform_point(self.calibration['homography'],moved['pixel'])
                    current['support_centers']['KEY_5']=list(moved['pixel'])
            return result
        with patch.object(action,'_validate',side_effect=validate):
            action.request('KEY_5')
            result=self.complete(action)
        self.assertEqual(result['response'],'DONE')
        logged=json.loads(stream.getvalue())
        self.assertEqual(logged['source_frame'],1)
        self.assertEqual(logged['pixel'],self.targets.observation['targets']['KEY_5']['pixel'])
        self.assertEqual(logged['source_observed_at'],new_time)
        self.assertEqual(len(transport.sent),1)

    def test_changed_context_or_calibration_after_observation_is_rejected(self):
        context={'camera':deepcopy(CAMERA),'origin':deepcopy(ORIGIN)}
        context['camera']['mount_id']='moved'
        self.context.write_text(json.dumps(context))
        action,transport=self.action()
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.assertFalse(transport.sent)

    def test_post_action_verification_requires_new_capture_and_direct_value(self):
        action,transport=self.action()
        chosen=deepcopy(self.targets.observation)
        completed=time.monotonic()
        self.targets.update_value('125',receipt=completed-.01)
        self.assertEqual(action._verify(chosen,completed,'125')['ui_outcome'],'unconfirmed')
        self.targets.update_value('125')
        result=action._verify(chosen,completed,'125')
        self.assertEqual(result['ui_outcome'],'expected_change_observed_in_simulation')
        self.targets.observation['direct_driver_value']=None
        self.assertEqual(action._verify(chosen,completed,'125')['ui_outcome'],'unconfirmed')

    def test_shutdown_during_preview_cannot_launch_late_action(self):
        from threading import Thread
        action,transport=self.action()
        entered,release=Event(),Event()
        original=action.preview
        def blocked(label):
            result=original(label)
            entered.set()
            release.wait(timeout=1)
            return result
        returned=[]
        with patch.object(action,'preview',side_effect=blocked):
            thread=Thread(target=lambda:returned.append(action.request('KEY_5')))
            thread.start()
            self.assertTrue(entered.wait(timeout=1))
            action.close()
            release.set();thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertFalse(returned[0]['accepted'])
        self.assertFalse(transport.sent)

    def test_integer_rounding_is_explicit_half_up(self):
        self.assertEqual([rounded_mm(v) for v in [100.49,100.5,100.51]],[100,101,101])
        for value in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):rounded_mm(value)

    def test_hardware_readiness_gate_and_valid_hardware_fixture_with_fake_transport(self):
        from dmi_robot_master.integration.calibration import fit_calibration, _identifier
        camera=deepcopy(CAMERA)
        camera.update(source_kind='local_camera',identity='offline-hardware-policy-fixture')
        camera['settings'].update(camera_index=0,requested_size=[None,None])
        document=fit_calibration(points(),frame_size=SIZE,camera=camera,origin=ORIGIN,
            ransac_threshold_mm=.5,tolerance_mm=.1,tolerance_basis='Offline hardware policy fixture',provenance='hardware')
        document['validation']['hardware_verified']=True  # Test assertion only; never a physical calibration.
        document['calibration_id']=_identifier(document)
        path=self.directory/'hardware-fixture.json';save_calibration(document,path)
        context=self.directory/'hardware-context.json';context.write_text(json.dumps({'camera':camera,'origin':ORIGIN}))
        targets=MemoryTargets(document)
        targets.observation.update(simulation=False,calibration_provenance='hardware')
        transport=FakeTransport((380,470))
        link=RobotLink(transport,limits_mm=(380,470),timeout_seconds=.03,hardware=True)
        options=dict(calibration_path=path,context_path=context,
            source_info={'kind':'local_camera','index':0,'requested_size':[None,None]},
            mode=SessionMode.PHYSICAL_PRESS,verification_timeout_seconds=.03,source_check=lambda:None)
        with self.assertRaisesRegex(ValueError,'readiness'):
            LabelActions(targets,MemoryState(targets),link,**options)
        checks={name:True for name in ['homed','xy_limits_verified','z_retracted','contact_sensing_checked',
            'stop_mechanism_available','origin_and_mount_verified','contact_routine_reviewed','move_only_alignment_reviewed']}
        action=LabelActions(targets,MemoryState(targets),link,hardware_checks=checks,**options)
        self.actions.append(action)
        action.request('KEY_5');result=self.complete(action)
        self.assertEqual(transport.sent,[[1,150,250,200]])
        self.assertEqual(result['response'],'DONE')
        self.assertEqual(result['ui_outcome'],'unconfirmed')

    def test_hardware_mode_rejects_simulation_even_with_ready_check_flags(self):
        action,transport=self.action(mode='physical-press')
        action.link.hardware=True
        action.source_check=lambda:None
        action.hardware_checks={name:True for name in ['homed','xy_limits_verified','z_retracted',
            'contact_sensing_checked','stop_mechanism_available','origin_and_mount_verified',
            'contact_routine_reviewed','move_only_alignment_reviewed']}
        self.assertFalse(action.request('KEY_5')['accepted'])
        self.assertFalse(transport.sent)


if __name__=='__main__':unittest.main()
