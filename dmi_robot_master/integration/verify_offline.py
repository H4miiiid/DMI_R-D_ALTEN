"""Repeatable recording verification; only ReplayCamera and FakeTransport are used."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
from threading import Event, Thread
import time

import cv2

from dmi_computer_vision.src.dmi.evaluation.compact import validate_compact
from dmi_computer_vision.src.dmi.evaluation.validation import validate_results
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_robot_master.integration.action_transport import FakeTransport, RobotLink
from dmi_robot_master.integration.actions import LabelActions, SessionMode
from dmi_robot_master.integration.calibrate import calibrate_replay
from dmi_robot_master.integration.camera import ReplayCamera
from dmi_robot_master.integration.observe import observe
from dmi_robot_master.integration.processing_policy import DetectionPolicy
from dmi_robot_master.integration.targets import CurrentTargets, atomic_json


ROOT = Path(__file__).resolve().parents[2]
VIDEOS = ROOT / 'dmi_computer_vision/data/videos/dev'


def inspect_recording_run(directory: Path) -> dict:
    """Check contracts and decode every saved annotation; accuracy needs review."""
    envelopes = [json.loads(line) for line in (directory / 'results_debug.jsonl').read_text().splitlines()]
    frames = [item['result'] for item in envelopes if item.get('type') == 'frame']
    contract = validate_results(frames, fps=None)
    compact = validate_compact(directory / 'results.jsonl', frames)
    capture = cv2.VideoCapture(str(directory / 'annotated.mp4'))
    count = 0
    try:
        if not capture.isOpened():
            raise ValueError('Saved annotation video cannot be opened')
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if image.shape[1::-1] != tuple(envelopes[0]['frame_size']):
                raise ValueError('Annotation dimensions differ from original input')
            count += 1
    finally:
        capture.release()
    if count != len(frames):
        raise ValueError('Annotation count differs from processed detections')
    return {'contract': contract, 'compact': compact, 'annotation_frames': count,
            'screens': dict(Counter(frame['right_display']['state'] for frame in frames)),
            'temporal_resets': dict(Counter(item['temporal_reset'] for item in envelopes
                                           if item.get('type') == 'frame' and item.get('temporal_reset')))}


def replay(path: Path, *, fps: float, start: float = 0) -> tuple[ReplayCamera, dict]:
    source = ReplayCamera(path, replay_fps=fps, start_seconds=start)
    return source, {'kind': 'recorded_replay', 'simulation': True, 'path': str(source.path),
                    'replay_fps': fps, 'start_seconds': start,
                    'rotation_clockwise': 0, 'mirror_horizontal': False}


def verify_offline(directory: Path) -> dict:
    """Run fresh calibration, three individually resolved fake presses and transition.

    This fixed development scenario has no live-source or hardware transport option.
    A rejected dispatch fails the run; it is never retried automatically.
    """
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = {'simulation': True, 'hardware_validated': False,
              'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                              'opencv': cv2.__version__}, 'passed': False}
    try:
        source, info = replay(VIDEOS / 'driver_id_12.mp4', fps=3, start=2.5)
        observe(source, directory / 'calibration_observation', source_info=info, max_frames=12, debug=True)
        report['calibration_observation_checks'] = inspect_recording_run(directory / 'calibration_observation')
        calibration_path = directory / 'calibration.simulation.json'
        fitted = calibrate_replay(directory / 'calibration_observation', calibration_path,
            observations=5, max_spread_px=3, ransac_threshold_mm=5, simulation_tolerance_mm=5)
        document = fitted['calibration']
        context = {'camera': document['camera'], 'origin': document['origin']}
        context_path = directory / 'context.simulation.json'
        atomic_json(context_path, context)
        report['calibration_validation'] = document['validation']

        current, state, stop = CurrentTargets(), LatestState(), Event()
        policy = DetectionPolicy()
        source, info = replay(VIDEOS / 'driver_id_12.mp4', fps=1.5, start=2.5)
        transport = FakeTransport((380, 470), delay_seconds=.1)
        link = RobotLink(transport, limits_mm=(380, 470), timeout_seconds=1)
        completed = Event()
        observation = {}
        def run_observation():
            try:
                observation['report'] = observe(source, directory / 'actions', source_info=info,
                    debug=True, latest_state=state, current_targets=current, stop_event=stop,
                    processing_policy=policy, annotations=True, export_targets=True,
                    calibration_path=calibration_path, calibration_context=context,
                    evidence_tolerance_px=3, target_history=True)
            except Exception as exc:
                observation['error'] = str(exc)
            finally:
                completed.set()
        worker = Thread(target=run_observation, name='offline-recording')
        results = []
        report['actions'] = results
        with (directory / 'button_tests.jsonl').open('x') as log:
            finished = Event()
            actions = LabelActions(current, state, link, calibration_path=calibration_path,
                context_path=context_path, source_info=info, policy=policy,
                mode=SessionMode.SIMULATED_PRESS, verification_timeout_seconds=1,
                log_stream=log, on_result=lambda result: finished.set(), stop_event=stop)
            worker.start()
            try:
                for label in ('KEY_4', 'KEY_5', 'KEY_6'):
                    deadline = time.monotonic() + 20
                    preview = actions.preview(label)
                    while not preview['accepted'] and time.monotonic() < deadline and not completed.is_set():
                        completed.wait(.05)
                        preview = actions.preview(label)
                    if not preview['accepted']:
                        raise ValueError(f'{label} cannot be selected: {preview.get("reason")}')
                    finished.clear()
                    requested = actions.request(label)
                    if not requested['accepted'] or not finished.wait(4):
                        raise ValueError(f'{label} dispatch failed or did not finish: {requested}')
                    result = actions.last_result
                    results.append(result)
                    if not result['accepted'] or result['response'] != 'DONE':
                        raise ValueError(f'{label} failed: {result}')
                    if result.get('newer_frame') is not True:
                        raise ValueError(f'{label} lacked a newer post-completion observation')
                    if result['ui_outcome'] == 'confirmed':
                        raise ValueError('Recording falsely claimed physical input confirmation')
                report['packets'] = transport.sent
                expected_packets = [[1, *result['commanded_mm'], result['press_duration_ms']] for result in results]
                if transport.sent != expected_packets or len(transport.robot.calls) != 3:
                    raise ValueError('Fake dispatch count/units differ from selected actions')
            finally:
                actions.close()
                worker.join(timeout=7)
                if worker.is_alive():
                    raise RuntimeError('Offline observation did not shut down')
        if 'error' in observation:
            raise RuntimeError(observation['error'])
        report['action_session'] = observation['report']
        report['action_checks'] = inspect_recording_run(directory / 'actions')

        source, info = replay(VIDEOS / 'driverID_to_level.mp4', fps=8)
        report['transition_session'] = observe(source, directory / 'transition', source_info=info,
            debug=True, processing_policy=DetectionPolicy(), annotations=True,
            export_targets=True, target_history=True)
        transition = inspect_recording_run(directory / 'transition')
        if not {'Driver ID', 'Level'} <= transition['screens'].keys():
            raise ValueError('Replay did not recognize both supported transition screens')
        history = [json.loads(line) for line in (directory / 'transition/targets_history.jsonl').read_text().splitlines()]
        if not any(item['screen'] == 'Level' for item in history):
            raise ValueError('Supported transition did not reach target output')
        if any(target['mm'] is not None or target['usable'] for item in history for target in item['targets']):
            raise ValueError('Uncalibrated transition targets unexpectedly usable')
        report['transition_checks'] = transition
        for name in ('actions', 'transition'):
            if json.loads((directory / name / 'targets.json').read_text())['targets']:
                raise ValueError('Stopped session retained targets')
        report['passed'] = True
    except BaseException as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        # LiveRunSummary contains artifact Paths; keep report JSON portable.
        atomic_json(directory / 'verification.json', json.loads(json.dumps(report, default=str, allow_nan=False)))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    print('OFFLINE SIMULATION — recordings and fake robot only; no physical UI causation.', flush=True)
    try:
        report = verify_offline(args.output_dir)
        print(f'Offline recording checks passed. Evidence: {args.output_dir / "verification.json"}')
        return 0 if report['passed'] else 1
    except (OSError, ValueError, RuntimeError, cv2.error) as exc:
        print(f'Offline verification failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
