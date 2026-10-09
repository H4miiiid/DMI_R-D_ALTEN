"""Phase 4 atomic/current target checks; no hardware or network."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from dmi_computer_vision.src.dmi.pipeline.frame_processor import FrameProcessor
from dmi_robot_master.integration.calibration import save_calibration
from dmi_robot_master.integration.publication import ChangePublisher
from dmi_robot_master.integration.targets import (
    CurrentTargets, TargetFiles, TargetProjector, atomic_json, read_target, select_target,
)
from test_calibration import CAMERA, ORIGIN, SIZE, fit, points, record


def direct_evidence(centers=None):
    return {'right_state': 'Driver ID', 'right_visibility': 'clear',
            'right_buttons': {f'digit_{key[-1]}': value for key, value in (centers or points()).items()},
            'right_field': [30, 30]}


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name)/'calibration.json'
        save_calibration(fit(), self.path)
        self.projector = TargetProjector(source_info={'kind':'synthetic','simulation':True},
            calibration_path=self.path, context={'camera':CAMERA,'origin':ORIGIN}, geometry_tolerance_px=1)

    def tearDown(self):
        self.temporary.cleanup()

    def test_identity_pixels_mm_and_outside_area_targets(self):
        snapshot, support = self.projector.project(record(0)['result'],direct_evidence(),frame_size=SIZE)
        self.assertTrue(snapshot['simulation'])
        self.assertEqual(set(support),{f'KEY_{i}' for i in range(10)})
        self.assertAlmostEqual(snapshot['targets']['KEY_1']['mm'][0],100,places=3)
        self.assertTrue(snapshot['targets']['KEY_1']['usable'])
        self.assertIsNone(snapshot['targets']['left/box/box_1']['mm'])
        self.assertIsNone(snapshot['targets']['right/field/input']['mm'])

    def test_fresh_frame_missing_direct_key_evidence_does_not_bless_retained_target(self):
        observed = direct_evidence()
        del observed['right_buttons']['digit_1']
        snapshot, support = self.projector.project(record(0)['result'],observed,frame_size=SIZE)
        self.assertFalse(snapshot['targets']['KEY_1']['usable'])
        self.assertIsNone(snapshot['targets']['KEY_1']['mm'])
        self.assertFalse(support)
        snapshot, support = self.projector.project(record(1)['result'],{},frame_size=SIZE)
        self.assertFalse(snapshot['targets']['KEY_1']['usable'])
        self.assertFalse(support)

    def test_wrong_screen_invalid_context_and_reference_calibration_have_null_mm(self):
        result=record(0)['result']
        result['right_display']['state']='Main'
        snapshot,_=self.projector.project(result,direct_evidence(),frame_size=SIZE)
        self.assertTrue(all(t['mm'] is None for t in snapshot['targets'].values()))
        self.projector.context['camera']['mount_id']='moved'
        snapshot,_=self.projector.project(record(1)['result'],direct_evidence(),frame_size=SIZE)
        self.assertFalse(snapshot['calibration_valid'])
        self.assertTrue(all(t['mm'] is None for t in snapshot['targets'].values()))

    def test_invalid_unchanged_calibration_is_not_refitted_each_frame(self):
        self.projector.context['origin']['identity']='changed'
        with patch('dmi_robot_master.integration.targets.ValidatedCalibration',side_effect=ValueError('invalid')) as cache:
            self.projector.project(record(0)['result'],direct_evidence(),frame_size=SIZE)
            self.projector.project(record(1)['result'],direct_evidence(),frame_size=SIZE)
            self.assertEqual(cache.call_count,1)

    def test_simulation_calibration_is_not_usable_on_real_source(self):
        projector=TargetProjector(source_info={'kind':'local_camera','simulation':False},
            calibration_path=self.path,context={'camera':CAMERA,'origin':ORIGIN},geometry_tolerance_px=1)
        snapshot,_=projector.project(record(0)['result'],direct_evidence(),frame_size=SIZE)
        self.assertFalse(snapshot['calibration_valid'])
        self.assertTrue(all(not t['usable'] and t['mm'] is None for t in snapshot['targets'].values()))

    def test_live_sources_are_bound_to_kind_and_connection_settings(self):
        from dmi_robot_master.integration.calibration import fit_calibration
        def document(camera):
            return fit_calibration(points(), frame_size=SIZE, camera=camera, origin=ORIGIN,
                ransac_threshold_mm=.5, tolerance_mm=.1, tolerance_basis='Offline fixture only')
        local_camera = deepcopy(CAMERA)
        local_camera.update(source_kind='local_camera', identity='fixture-local-camera')
        local_camera['settings'].update(camera_index=0, requested_size=[640, 480])
        remote_camera = deepcopy(CAMERA)
        remote_camera.update(source_kind='remote_bridge', identity='fixture-pi-camera')
        remote_camera['settings'].update(bridge_url='http://pi-a:8080/frame.jpg')
        scenarios = [
            (local_camera, {'kind':'local_camera','index':0,'requested_size':[640,480]}, True),
            (remote_camera, {'kind':'remote_bridge','url':'http://pi-a:8080/frame.jpg'}, True),
            (local_camera, {'kind':'remote_bridge','url':'http://pi-a:8080/frame.jpg'}, False),
            (remote_camera, {'kind':'local_camera','index':0,'requested_size':[640,480]}, False),
            (local_camera, {'kind':'local_camera','index':1,'requested_size':[640,480]}, False),
            (local_camera, {'kind':'local_camera','index':0,'requested_size':[1280,720]}, False),
            (remote_camera, {'kind':'remote_bridge','url':'http://pi-b:8080/frame.jpg'}, False),
            (local_camera, {'kind':'local_camera','index':0}, False),
            (remote_camera, {'kind':'remote_bridge'}, False),
            (local_camera, {'kind':'unsupported'}, False),
        ]
        for index, (camera, source, expected) in enumerate(scenarios):
            with self.subTest(source=source, camera=camera):
                path = Path(self.temporary.name)/f'live-{index}.json'
                save_calibration(document(camera), path)
                # Explicit simulation fixtures exercise identity checks without
                # implying that a hardware calibration has been physically verified.
                projector = TargetProjector(source_info={**source,'simulation':True},
                    calibration_path=path, context={'camera':camera,'origin':ORIGIN}, geometry_tolerance_px=1)
                snapshot, support = projector.project(record(0)['result'],direct_evidence(),frame_size=SIZE)
                self.assertEqual(snapshot['calibration_valid'], expected)
                self.assertEqual(snapshot['targets']['KEY_5']['usable'], expected)
                if not expected:
                    self.assertFalse(support)
                    self.assertTrue(all(t['mm'] is None for t in snapshot['targets'].values()))

    def test_source_changes_invalidate_and_recovery_rechecks_negative_cache(self):
        camera = deepcopy(CAMERA)
        camera.update(source_kind='local_camera', identity='fixture-local')
        camera['settings'].update(camera_index=0, requested_size=[None,None])
        from dmi_robot_master.integration.calibration import fit_calibration
        document = fit_calibration(points(), frame_size=SIZE, camera=camera, origin=ORIGIN,
            ransac_threshold_mm=.5, tolerance_mm=.1, tolerance_basis='Offline fixture')
        path = Path(self.temporary.name)/'source-change.json'
        save_calibration(document,path)
        projector=TargetProjector(source_info={'kind':'local_camera','index':0,
            'requested_size':[None,None],'simulation':True},calibration_path=path,
            context={'camera':camera,'origin':ORIGIN},geometry_tolerance_px=1)
        self.assertTrue(projector.project(record(0)['result'],direct_evidence(),frame_size=SIZE)[0]['calibration_valid'])
        projector.source_info['index']=1
        self.assertFalse(projector.project(record(1)['result'],direct_evidence(),frame_size=SIZE)[0]['calibration_valid'])
        projector.source_info['index']=0
        self.assertTrue(projector.project(record(2)['result'],direct_evidence(),frame_size=SIZE)[0]['calibration_valid'])

    def test_observations_are_not_mutated_and_missing_calibration_exports_pixels(self):
        result=record(0)['result']
        before=deepcopy(result)
        projector=TargetProjector(source_info={'kind':'synthetic','simulation':True})
        snapshot,_=projector.project(result,direct_evidence(),frame_size=SIZE)
        self.assertEqual(result,before)
        self.assertTrue(snapshot['targets'])
        self.assertTrue(all(t['mm'] is None and not t['usable'] for t in snapshot['targets'].values()))


class FreshnessLockTests(unittest.TestCase):
    def test_current_and_heartbeat_sample_time_after_blocked_publication(self):
        from threading import Event, Lock, Thread, current_thread
        for operation in ('current', 'tick'):
            with self.subTest(operation=operation):
                publishing = Event()
                release_publication = Event()
                attempting_read = Event()
                clock = [0.5]
                events, returned, errors = [], [], []
                def emit(event):
                    events.append(event)
                    if event['type'] == 'targets' and event['revision'] == 1:
                        publishing.set()
                        if not release_publication.wait(timeout=3):
                            raise RuntimeError('Test publication release timed out')
                publisher = ChangePublisher(emit, max_evidence_age_seconds=1)
                class ObservedLock:
                    def __init__(self):
                        self.lock = Lock()
                    def __enter__(self):
                        if current_thread().name == 'target-reader':
                            attempting_read.set()
                        self.lock.acquire()
                        return self
                    def __exit__(self, *args):
                        self.lock.release()
                publisher._lock = ObservedLock()
                def publish():
                    try:
                        publisher.update({'targets': {}}, received_at=0, detected_at=0)
                    except BaseException as exc:
                        errors.append(exc)
                def read():
                    try:
                        returned.append(publisher.current() if operation == 'current' else publisher.tick())
                    except BaseException as exc:
                        errors.append(exc)
                writer = Thread(target=publish)
                reader = Thread(target=read, name='target-reader')
                with patch('dmi_robot_master.integration.publication.time.monotonic', side_effect=lambda: clock[0]):
                    try:
                        writer.start()
                        self.assertTrue(publishing.wait(timeout=1))
                        reader.start()
                        self.assertTrue(attempting_read.wait(timeout=1))
                        clock[0] = 2.0  # Evidence expires while the reader waits for the lock.
                    finally:
                        release_publication.set()
                        writer.join(timeout=3)
                        if reader.ident is not None:
                            reader.join(timeout=3)
                self.assertFalse(writer.is_alive())
                self.assertFalse(reader.is_alive())
                self.assertFalse(errors)
                if operation == 'current':
                    self.assertEqual(returned, [None])
                else:
                    self.assertEqual(events[-1]['source_status'], 'stale')
                    self.assertEqual(events[-1]['evidence_age_seconds'], 2.0)


class CurrentFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.directory=Path(self.temporary.name)
        self.files=TargetFiles(self.directory,'session',simulation=True,history=True)
        self.publisher=ChangePublisher(self.files.emit,session_id='session',max_evidence_age_seconds=1.5)
        self.now=datetime.now(timezone.utc)
        self.snapshot={'screen':'Driver ID','simulation':True,'calibration_id':'cal-id',
                       'calibration_provenance':'simulation','frame_size':[640,480],
                       'targets':{'KEY_1':{'label':'KEY_1','kind':'button','display':'right',
                                           'pixel':[100,200],'mm':[100.,300.],'usable':True}}}

    def tearDown(self):
        self.files.close()
        self.temporary.cleanup()

    def update(self,snapshot=None,receipt=10,frame=0,support=None):
        timestamp=(self.now-timedelta(seconds=10-receipt)).isoformat()
        self.publisher.update(snapshot or self.snapshot,received_at=receipt,detected_at=receipt,
                              observed_at_utc=timestamp,frame_index=frame,capture_index=frame,
                              support_centers=support or {'KEY_1':[100,200]},support_tolerance_px=4)
        # Keep wall-clock/monotonic domains explicit in this controlled test.
        self.publisher.tick(receipt,force=True)

    def test_atomic_output_schema_consumer_and_simulation_rejection(self):
        self.update()
        stored=json.loads((self.directory/'targets.json').read_text())
        self.assertIsInstance(stored['targets'],list)
        self.assertEqual(stored['observed_at'],self.now.isoformat())
        self.assertEqual(read_target(self.directory,'KEY_1')['mm'],[100.,300.])
        with self.assertRaisesRegex(ValueError,'simulation'):
            read_target(self.directory,'KEY_1',hardware=True)
        with self.assertRaisesRegex(ValueError,'missing'):
            read_target(self.directory,'KEY_9')

    def test_jitter_write_suppression_current_pixels_and_supported_old_snapshot(self):
        self.update(receipt=9.9)
        writes=self.files.target_writes
        current=CurrentTargets();current.bind(self.publisher)
        moved=deepcopy(self.snapshot);moved['targets']['KEY_1']['pixel']=[103,200]
        self.update(moved,receipt=10,frame=1,support={'KEY_1':[103,200]})
        self.assertEqual(self.files.target_writes,writes)
        self.assertEqual(read_target(self.directory,'KEY_1')['pixel'],[100,200])
        # CurrentTargets uses actual monotonic age; patch the clock explicitly.
        with patch('dmi_robot_master.integration.publication.time.monotonic',return_value=10):
            self.assertEqual(current.get()['targets'][0]['pixel'],[103,200])
        current.close();self.assertIsNone(current.get())

    def test_lost_support_bypasses_pixel_tolerance(self):
        self.update(receipt=9.9)
        writes=self.files.target_writes
        shifted=deepcopy(self.snapshot);shifted['targets']['KEY_1']['pixel']=[104,200]
        self.publisher.update(shifted,received_at=10,detected_at=10,
            observed_at_utc=self.now.isoformat(),frame_index=1,capture_index=1,
            support_centers={'KEY_1':[104,200]},support_tolerance_px=3)
        self.publisher.tick(10,force=True)
        self.assertEqual(self.files.target_writes,writes+1)
        self.assertEqual(read_target(self.directory,'KEY_1')['pixel'],[104,200])

    def test_removal_stop_expiry_and_missing_status(self):
        self.update()
        empty=deepcopy(self.snapshot);empty['targets']={}
        self.update(empty,receipt=10.1,frame=1)
        self.assertEqual(json.loads((self.directory/'targets.json').read_text())['targets'],[])
        self.publisher.close('error')
        with self.assertRaises(ValueError):read_target(self.directory,'KEY_1')
        (self.directory/'target_status.json').unlink()
        with self.assertRaisesRegex(ValueError,'unavailable'):read_target(self.directory,'KEY_1')

    def test_abrupt_process_death_stale_duplicate_and_uncalibrated_rejection(self):
        self.update()
        snapshot=json.loads((self.directory/'targets.json').read_text())
        status=json.loads((self.directory/'target_status.json').read_text())
        with self.assertRaisesRegex(ValueError,'stale'):
            select_target(snapshot,status,'KEY_1',now_utc=self.now+timedelta(seconds=2))
        duplicate=deepcopy(snapshot);duplicate['targets'].append(deepcopy(duplicate['targets'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            select_target(duplicate,status,'KEY_1')
        invalid=deepcopy(snapshot);invalid['targets'][0]['mm']=None
        with self.assertRaisesRegex(ValueError,'uncalibrated'):
            select_target(invalid,status,'KEY_1')
        changed=deepcopy(status);changed['revision']+=1
        with self.assertRaisesRegex(ValueError,'revision'):
            select_target(snapshot,changed,'KEY_1')

    def test_upstream_age_clock_future_and_unsupported_label_rejection(self):
        self.update()
        snapshot=json.loads((self.directory/'targets.json').read_text())
        status=json.loads((self.directory/'target_status.json').read_text())
        unsupported=deepcopy(status);unsupported['published_supported_labels']=[]
        with self.assertRaisesRegex(ValueError,'supporting'):
            select_target(snapshot,unsupported,'KEY_1')
        stale=deepcopy(status);stale['evidence_age_seconds']=2
        with self.assertRaisesRegex(ValueError,'stale'):
            select_target(snapshot,stale,'KEY_1')
        future=deepcopy(status);future['heartbeat_at']=(self.now+timedelta(seconds=2)).isoformat()
        with self.assertRaises(ValueError):select_target(snapshot,future,'KEY_1')

    def test_atomic_replacements_do_not_expose_partial_json_to_readers(self):
        from threading import Event, Thread
        self.update()
        path=self.directory/'targets.json'
        finished=Event()
        failures=[]
        def reader():
            while not finished.is_set():
                try:
                    json.loads(path.read_text())
                except Exception as exc:
                    failures.append(exc)
        worker=Thread(target=reader)
        worker.start()
        try:
            for revision in range(30):
                atomic_json(path,{'revision':revision,'padding':'x'*10000})
        finally:
            finished.set();worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(failures)

    def test_serialization_and_replace_failures_preserve_old_file(self):
        self.update()
        path=self.directory/'targets.json'
        before=path.read_bytes()
        with self.assertRaises(ValueError):atomic_json(path,{'bad':float('nan')})
        self.assertEqual(path.read_bytes(),before)
        with patch('dmi_robot_master.integration.targets.os.replace',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):atomic_json(path,{'new':'content'})
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(list(self.directory.glob('*.tmp')))


class LiveExportTests(unittest.TestCase):
    def test_declared_live_metadata_cannot_disguise_actual_adapter(self):
        from dmi_robot_master.integration.camera import RemoteCamera, RobotCamera
        from dmi_robot_master.integration.observe import check_target_source
        remote=RemoteCamera('http://pi-a:8080/frame.jpg')
        local=RobotCamera(0,width=640,height=480)
        check_target_source(remote,{'kind':'remote_bridge','url':remote.url})
        check_target_source(local,{'kind':'local_camera','index':0,'requested_size':[640,480]})
        for source, info in [
            (remote,{'kind':'local_camera','index':0,'requested_size':[640,480]}),
            (local,{'kind':'local_camera','index':1,'requested_size':[640,480]}),
            (remote,{'kind':'remote_bridge','url':'http://pi-b:8080/frame.jpg'}),
        ]:
            with self.subTest(info=info), self.assertRaisesRegex(ValueError,'actual adapter'):
                check_target_source(source,info)

    def test_live_exact_targets_and_coordinated_stop_or_failure(self):
        import numpy as np
        from dmi_robot_master.integration.camera import IntegrationFrame
        from dmi_robot_master.integration.observe import observe
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as temporary:
                directory=Path(temporary)
                calibration_path=directory/'calibration.json'
                save_calibration(fit(),calibration_path)
                current=CurrentTargets()
                seen=[]
                class Source:
                    def __init__(self):self.index=0;self.closed=False;self.last_packet=None
                    def __enter__(self):return self
                    def __exit__(self,*args):self.closed=True
                    def stats(self):return {'captured_frames':self.index,'dequeued_frames':self.index,'overwritten_frames':0,'pending_frames':0}
                    def read(self):
                        if self.index:
                            seen.append(current.get())
                        if self.index==2:
                            if fail:raise RuntimeError('source lost')
                            raise EOFError()
                        self.last_packet=IntegrationFrame(np.zeros((SIZE[1],SIZE[0],3),np.uint8),self.index,
                            time.monotonic(),datetime.now(timezone.utc).isoformat())
                        self.index+=1
                        return self.last_packet
                def detector(image,index,timestamp,*args,target_evidence=None):
                    result=record(index)['result']
                    result.update(frame_index=index,timestamp=timestamp)
                    if target_evidence is not None:target_evidence.update(direct_evidence())
                    return result
                source=Source()
                with patch('dmi_computer_vision.src.dmi.pipeline.frame_processor.process_frame',side_effect=detector):
                    options=dict(source_info={'kind':'synthetic','simulation':True},annotations=False,
                        export_targets=True,calibration_path=calibration_path,
                        calibration_context={'camera':CAMERA,'origin':ORIGIN},evidence_tolerance_px=1,
                        current_targets=current)
                    if fail:
                        with self.assertRaisesRegex(RuntimeError,'source lost'):
                            observe(source,directory/'live',**options)
                    else:observe(source,directory/'live',**options)
                self.assertTrue(source.closed)
                self.assertIsNone(current.get())
                self.assertTrue(seen)
                target=next(t for t in seen[0]['targets'] if t['label']=='KEY_5')
                self.assertTrue(target['usable'])
                self.assertAlmostEqual(target['mm'][0],150,places=3)
                self.assertEqual(json.loads((directory/'live/targets.json').read_text())['targets'],[])
                status=json.loads((directory/'live/target_status.json').read_text())
                self.assertEqual(status['source_status'],'error' if fail else 'stopped')


class EvidenceRegressionTests(unittest.TestCase):
    def test_optional_direct_evidence_preserves_detector_results(self):
        import cv2
        path=Path(__file__).resolve().parents[1]/'dmi_computer_vision/data/videos/dev/driver_id_12.mp4'
        capture=cv2.VideoCapture(str(path))
        try:
            plain=FrameProcessor()
            observed=FrameProcessor(collect_target_evidence=True)
            for index in range(3):
                ok,image=capture.read();self.assertTrue(ok)
                self.assertEqual(plain.process(image,index/30),observed.process(image,index/30))
                self.assertEqual(observed.target_evidence['right_state'],'Driver ID')
                self.assertIn('digit_1',observed.target_evidence['right_buttons'])
        finally:
            capture.release()


if __name__=='__main__':unittest.main()
