"""One operator-selected label action, independent of capture and terminal input."""
from __future__ import annotations

from copy import deepcopy
from enum import Enum
import math
from pathlib import Path
from threading import Event, RLock, Thread
import time

from dmi_computer_vision.src.dmi.output.json_writer import write_record
from dmi_robot_master.integration.calibration import (
    read_json, recheck_keypad, convert_pixel,
)
from dmi_robot_master.integration.targets import validate_camera_source


class SessionMode(str, Enum):
    DRY_RUN = 'dry-run'
    SIMULATED_PRESS = 'simulated-press'
    MOVE_ONLY = 'move-only'
    PHYSICAL_PRESS = 'physical-press'


def check_hardware_readiness(mode: SessionMode, checks: dict | None) -> None:
    required = ['homed', 'xy_limits_verified', 'z_retracted', 'contact_sensing_checked',
                'stop_mechanism_available', 'origin_and_mount_verified', 'contact_routine_reviewed']
    if mode == SessionMode.PHYSICAL_PRESS:
        required.append('move_only_alignment_reviewed')
    if not checks or any(checks.get(name) is not True for name in required):
        raise ValueError('Physical readiness/alignment checks are incomplete')


def rounded_mm(value: float) -> int:
    """Integer protocol: nearest whole mm, half upward; never truncate silently."""
    if not math.isfinite(value) or value < 0:
        raise ValueError('Command coordinates must be finite and nonnegative')
    return math.floor(value + 0.5)


class LabelActions:
    def __init__(self, targets, latest_state, link, *, calibration_path: str | Path,
                 context_path: str | Path, source_info: dict, policy=None,
                 mode: SessionMode = SessionMode.DRY_RUN, press_duration_ms: int = 200,
                 verification_timeout_seconds: float = 5.0,
                 hardware_checks: dict | None = None, source_check=None,
                 log_stream=None, on_result=None, stop_event: Event | None = None) -> None:
        self.mode = SessionMode(mode)
        if type(press_duration_ms) is not int or not 0 < press_duration_ms < 2**31:
            raise ValueError('Press duration must be positive signed-32-bit milliseconds')
        if not 0 < verification_timeout_seconds < float('inf'):
            raise ValueError('Verification timeout must be finite and positive')
        if link.hardware and self.mode not in (SessionMode.MOVE_ONLY, SessionMode.PHYSICAL_PRESS):
            raise ValueError('Motor transport requires an explicit physical action mode')
        if link.hardware:
            check_hardware_readiness(self.mode, hardware_checks)
            if source_check is None:
                raise ValueError('Physical execution requires an actual-source check')
        self.targets, self.latest_state, self.link = targets, latest_state, link
        self.calibration_path = Path(calibration_path).expanduser().resolve()
        self.context_path = Path(context_path).expanduser().resolve()
        self.source_info = deepcopy(source_info)
        self.policy, self.source_check = policy, source_check
        self.press_duration_ms = press_duration_ms
        self.verification_timeout = verification_timeout_seconds
        self.hardware_checks = deepcopy(hardware_checks)
        self.log_stream, self.on_result = log_stream, on_result
        self.stop_event = stop_event or Event()
        self._lock = RLock()
        self._busy = self._closed = self._failed = False
        self._thread = None
        self.last_result = None

    def _selected(self, label: str) -> tuple[dict, dict]:
        observation = self.targets.action_observation()
        if observation is None:
            raise ValueError('No fresh live target observation')
        if observation.get('screen') != 'Driver ID':
            raise ValueError('Expected Driver ID screen')
        if label not in {f'KEY_{digit}' for digit in range(10)}:
            raise ValueError('Only known keypad labels KEY_0..KEY_9 are allowed')
        labels = [target.get('label') for target in observation['targets'].values()]
        if len(labels) != len(set(labels)) or any(key != target.get('label') for key,target in observation['targets'].items()):
            raise ValueError('Target labels are duplicate or ambiguous')
        target = observation['targets'].get(label)
        if target is None:
            raise ValueError('Target label is missing')
        if target.get('label') != label or target.get('kind') != 'button' or target.get('display') != 'right':
            raise ValueError('Target label/type/display is ambiguous or not an approved button')
        return observation, target

    def _validate(self, observation: dict, target: dict) -> tuple[list[float], list[int]]:
        if not target.get('usable') or target.get('mm') is None:
            raise ValueError('Target is unusable, uncalibrated or lacks current geometry support')
        if self.link.hardware:
            check_hardware_readiness(self.mode, self.hardware_checks)
            if observation.get('simulation') is not False or observation.get('calibration_provenance') != 'hardware':
                raise ValueError('Physical execution rejects simulation targets')
        if self.source_check is not None:
            self.source_check()
        document, context = read_json(self.calibration_path), read_json(self.context_path)
        if document['calibration_id'] != observation['calibration_id']:
            raise ValueError('Calibration changed since the target observation')
        validate_camera_source(context['camera'], self.source_info)
        xy = convert_pixel(document,target['pixel'],frame_size=tuple(observation['frame_size']),
            camera=context['camera'],origin=context['origin'],display=target['display'],
            screen=observation['screen'],hardware=self.link.hardware)
        tolerance = observation.get('support_tolerance_px')
        centers = observation.get('support_centers')
        if not isinstance(centers, dict) or tolerance is None:
            raise ValueError('Current direct supporting evidence is missing')
        recheck_keypad(document, centers, tolerance_px=tolerance)
        if target['label'] not in centers or max(abs(a-b) for a,b in zip(target['pixel'],centers[target['label']])) > tolerance:
            raise ValueError('Selected center lacks recent direct support')
        if len(target['mm']) != 2 or any(not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-6) for a,b in zip(xy,target['mm'])):
            raise ValueError('Observed mm do not match revalidated calibration')
        limits = self.link.commands.xy_limits_mm
        command_xy = [rounded_mm(value) for value in xy]
        if any(not 0 <= value < limit for value,limit in zip(xy,limits)) or any(
                not 0 <= value < limit for value,limit in zip(command_xy,limits)):
            raise ValueError('Target or rounded command is outside travel limits')
        return xy, command_xy

    def preview(self, label: str) -> dict:
        record = {'label':label,'mode':self.mode.value,'simulation_transport':not self.link.hardware,
                  'pixel':None,'mm':None,'commanded_mm':None,'response':'NOT_SENT','ui_outcome':'not_requested',
                  'press_duration_ms':self.press_duration_ms if self.mode in (SessionMode.SIMULATED_PRESS,SessionMode.PHYSICAL_PRESS) else None}
        try:
            observation, target = self._selected(label)
            record.update(pixel=target['pixel'],mm=target.get('mm'),source_frame=observation['frame_index'],
                          session_id=observation['session_id'],calibration_id=observation['calibration_id'],
                          source_observed_at=observation.get('observed_at'))
            xy, command_xy = self._validate(observation,target)
            record.update(mm=xy,commanded_mm=command_xy,accepted=True)
        except Exception as exc:
            record.update(accepted=False,reason=str(exc))
        return record

    def request(self, label: str) -> dict:
        with self._lock:
            if self._closed or self.stop_event.is_set():
                return {'accepted':False,'reason':'Session is stopped','label':label}
            if self._failed:
                return {'accepted':False,'reason':'Robot failure latched; restart session','label':label}
            if self._busy:
                return {'accepted':False,'reason':'An action is outstanding; label rejected, not queued','label':label}
            self._busy = True
        preview = self.preview(label)
        with self._lock:
            if self._closed or self.stop_event.is_set():
                self._busy = False
                return {'accepted':False,'reason':'Session stopped during validation','label':label}
            asynchronous = preview['accepted'] and self.mode != SessionMode.DRY_RUN
            if asynchronous:
                self._thread = Thread(target=self._execute,args=(label,preview),name='dmi-one-action',daemon=True)
                self._thread.start()
            else:
                # Finish synchronous previews under the same reservation lock,
                # so shutdown cannot close their log between validation/recording.
                self._finish(preview)
                return preview
        return {'accepted':True,'pending':True,'label':label,'mode':self.mode.value}

    def _driver_value(self, observation: dict):
        state = self.latest_state.get(max_age_seconds=1.5)
        if state is None or state['frame_index'] != observation['frame_index']:
            return None
        value = state['state']['right_display']['fields'].get('driver_id',{}).get('value')
        return value if value == observation.get('direct_driver_value') else None

    def _execute(self, label: str, selected: dict) -> None:
        result = dict(selected)
        try:
            observation, target = self._selected(label)
            if observation['session_id'] != selected['session_id'] or observation['calibration_id'] != selected['calibration_id']:
                raise ValueError('Target session/calibration changed before dispatch')
            xy, command_xy = self._validate(observation,target)
            # Refitting/file checks may have taken time: re-resolve immediately.
            fresh, fresh_target = self._selected(label)
            if fresh['session_id'] != observation['session_id'] or fresh['calibration_id'] != observation['calibration_id']:
                raise ValueError('Target context changed during validation')
            if fresh['frame_index'] != observation['frame_index'] or fresh_target != target:
                observation, target = fresh, fresh_target
                xy, command_xy = self._validate(observation,target)
                final, final_target = self._selected(label)
                if final['frame_index'] != observation['frame_index'] or final_target != target:
                    raise ValueError('Target changed again before dispatch; request rejected')
            before = self._driver_value(observation)
            if self.stop_event.is_set() or self._closed:
                raise ValueError('Session stopped before dispatch')
            result.update(source_frame=observation['frame_index'],
                          source_observed_at=observation.get('observed_at'),
                          pixel=target['pixel'],mm=xy,commanded_mm=command_xy)
            success = (self.link.move(*command_xy) if self.mode == SessionMode.MOVE_ONLY else
                       self.link.press(*command_xy,self.press_duration_ms))
            result['response'] = self.link.response
            if not success:
                with self._lock:
                    self._failed = True
                result.update(accepted=False,reason='Command failed; further commands disabled',ui_outcome='unconfirmed')
            else:
                completed = time.monotonic()
                if self.policy is not None:
                    self.policy.request_refresh(after_received_at=completed)
                if self.mode == SessionMode.MOVE_ONLY:
                    result['ui_outcome'] = 'alignment_requires_operator_review'
                else:
                    expected = before + label[-1] if isinstance(before,str) and before.isdigit() else None
                    result.update(self._verify(observation,completed,expected))
        except Exception as exc:
            result.update(accepted=False,reason=str(exc),ui_outcome='unconfirmed')
        finally:
            self._finish(result)

    def _verify(self, chosen: dict, completed_at: float, expected: str | None) -> dict:
        deadline = time.monotonic()+self.verification_timeout
        newer = False
        observed = None
        while not self.stop_event.is_set() and time.monotonic() < deadline:
            targets = self.targets.action_observation()
            state = self.latest_state.get(max_age_seconds=1.5)
            if targets is not None and (targets['session_id'] != chosen['session_id'] or targets['calibration_id'] != chosen['calibration_id']):
                return {'ui_outcome':'unconfirmed','verification_reason':'Observation session changed'}
            if (targets is not None and state is not None and
                    targets['frame_index'] == state['frame_index'] and
                    targets['frame_index'] > chosen['frame_index'] and
                    targets['received_at_monotonic']-targets['upstream_age_seconds'] > completed_at):
                newer = True
                observed = state['state']['right_display']['fields'].get('driver_id',{}).get('value')
                if expected is not None and state['state']['right_display']['state']=='Driver ID' and observed==expected and targets.get('direct_driver_value')==expected:
                    return {'ui_outcome':'confirmed' if self.link.hardware else 'expected_change_observed_in_simulation',
                            'newer_frame':True,'verification_frame':targets['frame_index']}
            self.stop_event.wait(.02)
        return {'ui_outcome':'unconfirmed','newer_frame':newer,
                'verification_reason':'Expected input change not established' if expected is not None else 'Baseline value unknown',
                'observed_value':observed}

    def _finish(self, result: dict) -> None:
        with self._lock:
            self.last_result = deepcopy(result)
            if self.log_stream is not None:
                write_record(self.log_stream,result)
            self._busy = False
        if self.on_result is not None:
            self.on_result(deepcopy(result))

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self.stop_event.set()
        self.link.close()
        if self._thread is not None:
            self._thread.join(timeout=self.verification_timeout+1)
            if self._thread.is_alive():
                raise RuntimeError('Robot action wait is still blocked; outcome unconfirmed')
