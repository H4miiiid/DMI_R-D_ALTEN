"""One GUI command owner using the existing validated controller and transport."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import ipaddress
import math
from threading import Lock
import time
from uuid import uuid4

from dmi_robot_common.DmiMessages import DmiMessages
from dmi_robot_common.command_validation import validate_command
from dmi_robot_master.integration.action_transport import FakeTransport, RobotLink
from dmi_robot_master.integration.calibration import read_json

MANUAL_STEP_MM = 5

HOMING_CHECKS = ('xy_limits_verified', 'z_retracted', 'stop_mechanism_available',
                 'homing_area_clear', 'origin_and_mount_verified')


def _endpoint(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('Endpoint must be [IPv4 address, port, protocol ID]')
    ipaddress.IPv4Address(value[0])
    if (type(value[1]) is not int or not 0 < value[1] <= 65535
            or type(value[2]) is not int or not 0 <= value[2] < 2**31):
        raise ValueError('Invalid endpoint port/protocol ID')
    return tuple(value)


@dataclass(frozen=True)
class RobotSettings:
    address: tuple
    remote_address: tuple
    xy_limits_mm: tuple[int, int]
    timeout_seconds: float

    def __post_init__(self):
        _endpoint(list(self.address))
        _endpoint(list(self.remote_address))
        if (len(self.xy_limits_mm) != 2 or any(type(v) is not int or not 0 < v < 2**31 for v in self.xy_limits_mm)
                or type(self.timeout_seconds) not in (int,float)
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120):
            raise ValueError('Invalid XY bounds or bounded command timeout')

    @classmethod
    def load(cls, path):
        data = read_json(path)
        limits = data['xy_limits_mm']
        timeout = data['timeout_seconds']
        if (not isinstance(limits, list) or len(limits) != 2
                or any(type(v) is not int or not 0 < v < 2**31 for v in limits)
                or type(timeout) not in (float, int) or not math.isfinite(timeout)
                or not 0 < timeout <= 120):
            raise ValueError('Configure measured integer XY bounds and timeout (0, 120] seconds')
        return cls(_endpoint(data['address']), _endpoint(data['remote_address']), tuple(limits), float(timeout))

    @classmethod
    def demo(cls):
        # No socket is opened. These explicit simulation bounds are not a robot setup.
        return cls(('127.0.0.1', 19001, 0xBBBB), ('127.0.0.1', 19002, 0xAAAA), (1000, 1000), .2)


class RobotSession:
    """Serialized bounded transactions. ACK is connection evidence, not readiness.

    Live single-button testing requires a valid current calibrated target,
    movement limits and explicit readiness confirmation. Static-coordinate XML
    requires its separate explicit legacy mode and homing.
    """
    def __init__(self, settings: RobotSettings, *, simulation=False, transport_factory=None):
        if type(simulation) is not bool:
            raise ValueError('Simulation must be an explicit boolean')
        self.settings, self.simulation = settings, simulation
        self._factory = transport_factory
        self._operation = Lock()
        self._link = None
        self._state = {'connection': 'disconnected', 'response': None, 'homed': False,
                       'origin_epoch': uuid4().hex, 'simulation': self.simulation,
                       'physical_verified': False, 'action_ready': False}
        self._legacy = False
        self._last_press_created_at = -math.inf

    def status(self) -> dict:
        result = deepcopy(self._state)
        at = result.get('last_response_at')
        result['last_response_age_seconds'] = time.monotonic()-at if at is not None else None
        result['legacy_xml_armed'] = self._legacy
        return result

    @contextmanager
    def _exclusive(self):
        if not self._operation.acquire(blocking=False):
            raise RuntimeError('A robot transaction is already active')
        try:
            yield
        finally:
            self._operation.release()

    def _invalidate(self, connection, response=None):
        self._legacy = False
        self._state = {**self._state, 'connection': connection, 'response': response,
                       'homed': False, 'origin_epoch': uuid4().hex,
                       'last_response_at': None,
                       'physical_verified': False, 'action_ready': False}

    def _close(self):
        link = self._link
        if link:
            link.close()
        self._link = None

    def _check(self, command):
        try:
            success, data = self._link.check(command)
            response = self._link.response
            if not success:
                raise RuntimeError(response or 'TIMEOUT')
            self._state = {**self._state, 'response': response, 'last_response_at': time.monotonic()}
            return data
        except Exception as exc:
            self._invalidate('fault', self._link.response or str(exc))
            self._close()
            raise RuntimeError(f'{command.name}: {self._state["response"]}') from exc

    def connect(self) -> dict:
        with self._exclusive():
            if self._link is not None:
                raise RuntimeError('Disconnect before opening another robot session')
            transport = None
            linked = False
            try:
                if self._factory:
                    transport = self._factory()
                elif self.simulation:
                    transport = FakeTransport(self.settings.xy_limits_mm)
                else:
                    from dmi_robot_common.ComProtocol import ComProtocol
                    transport = ComProtocol(self.settings.address, self.settings.remote_address)
                if self.simulation and not isinstance(transport, FakeTransport):
                    raise ValueError('Demo requires the fake transport, never UDP')
                self._link = RobotLink(transport, limits_mm=self.settings.xy_limits_mm,
                    timeout_seconds=self.settings.timeout_seconds, hardware=not self.simulation)
                linked = True
                self._check(DmiMessages.ACK)  # No initialization or motion on connect.
                self._state = {**self._state, 'connection': 'connected',
                               'transport': 'fake' if isinstance(transport,FakeTransport) else 'udp'}
                return self.status()
            except Exception:
                if self._link is not None:
                    self._close()
                elif transport is not None and not linked:
                    transport.close()
                self._invalidate('fault', self._state.get('response') or 'CONNECT_FAILED')
                raise

    def ping(self) -> dict:
        with self._exclusive():
            if self._link is None:
                raise RuntimeError('Connect the robot first')
            self._check(DmiMessages.ACK)
            return self.status()

    def initialize(self, *, operator_confirmed: bool, checks: dict) -> dict:
        with self._exclusive():
            if self._link is None:
                raise RuntimeError('Connect and inspect ACK before initialization')
            if (operator_confirmed is not True or not isinstance(checks,dict)
                    or any(checks.get(key) is not True for key in HOMING_CHECKS)):
                raise ValueError('Confirm homing explicitly and complete operator readiness checks')
            self._invalidate('connected', self._state['response'])
            self._check(DmiMessages.ACK)
            self._check(DmiMessages.INITIALIZE)
            self._state = {**self._state, 'homed': True, 'operator_checks': deepcopy(checks)}
            return self.status()

    def position(self) -> dict:
        with self._exclusive():
            if self._link is None:
                raise RuntimeError('Connect first')
            xy = self._checked_position()
            return {'xy_mm': xy, 'independent_measurement': False, 'simulation': self.simulation}

    def jog(self, axis, direction, *, operator_confirmed=False, checks=None):
        """One operator-requested 5 mm XY step, Z=0; no queue/retry/return."""
        from dmi_robot_master.integration.move_only import MOVE_CHECKS
        with self._exclusive():
            if (axis not in ('x', 'y') or type(direction) is not int or direction not in (-1, 1)):
                raise ValueError('Select X or Y and one positive/negative 5 mm step')
            if (operator_confirmed is not True or not isinstance(checks, dict)
                    or any(checks.get(key) is not True for key in MOVE_CHECKS)
                    or any(self._state.get('operator_checks', {}).get(key) is not True for key in HOMING_CHECKS)):
                raise ValueError('Confirm retraction, clear path, starting position, limits and physical stop')
            if self._link is None or not self._state['homed'] or self._legacy:
                raise ValueError('Connect/home the shared owner and leave legacy XML mode first')
            self._check(DmiMessages.ACK)
            start = self._checked_position()
            target = list(start)
            target[0 if axis == 'x' else 1] += direction * MANUAL_STEP_MM
            # Reject a full step outside travel; never silently clamp its distance.
            validate_command(DmiMessages.MOVE, [*target, 0], self.settings.xy_limits_mm)
            try:
                if not self._link.move(*target):
                    raise RuntimeError(self._link.response or 'MOVE_FAILED')
            except Exception as exc:
                self._invalidate('fault', self._link.response or str(exc)); self._close()
                raise
            response = self._link.response
            self._state = {**self._state, 'response': response, 'last_response_at': time.monotonic()}
            reported = self._checked_position()
            return {'command': 'MOVE', 'start_xy_mm': list(start), 'command_xy_mm': target,
                    'xy_mm': list(reported), 'requested_z_mm': 0, 'response': response,
                    'step_mm': MANUAL_STEP_MM, 'independent_measurement': False,
                    'simulation': isinstance(self._link.transport, FakeTransport)}

    def _checked_position(self):
        xy = self._check(DmiMessages.GET_CURRENT_POSITION)
        if (not isinstance(xy, (tuple, list)) or len(xy) != 2
                or any(type(v) is not int or not 0 <= v < limit for v, limit in zip(xy, self.settings.xy_limits_mm))):
            self._invalidate('fault', 'INVALID_POSITION'); self._close()
            raise ValueError('Controller position is outside configured XY bounds')
        return xy

    def legacy_action(self, name: str, args: tuple) -> bool:
        with self._exclusive():
            if (not self.simulation and not self._legacy) or self._link is None or not self._state['homed']:
                raise ValueError('Hardware commands disabled outside the explicit initialized legacy XML mode')
            validate_command(DmiMessages[name],list(args),self.settings.xy_limits_mm)
            if not (name == 'MOVE' and args[2] == 0 or name == 'MOVE_AND_CLICK'):
                raise ValueError('Unsupported legacy action')
            try:
                success = self._link.move(*args[:2]) if name == 'MOVE' else self._link.press(*args)
            except Exception as exc:
                self._invalidate('fault',self._link.response or str(exc))
                self._close()
                raise
            if not success:
                self._invalidate('fault', self._link.response)
                self._close()
            else:
                self._state = {**self._state,'response':self._link.response,'last_response_at':time.monotonic()}
            return success

    def begin_legacy(self, *, operator_confirmed: bool) -> None:
        with self._exclusive():
            if operator_confirmed is not True or self._link is None or not self._state['homed']:
                raise ValueError('Confirm the initialized static-coordinate XML workflow explicitly')
            self._legacy = True

    def move_only(self, plan, observer, *, operator_confirmed: bool, checks: dict) -> dict:
        """One bounded commissioning MOVE with Z=0, no retry/press/return motion."""
        from dmi_robot_master.integration.move_only import MOVE_CHECKS, MovePlan
        with self._exclusive():
            if (not isinstance(plan,MovePlan) or operator_confirmed is not True or
                    not isinstance(checks,dict) or any(checks.get(k) is not True for k in MOVE_CHECKS)):
                raise ValueError('Explicitly confirm each move and all independent safety checks')
            if self._legacy or self._link is None or not self._state['homed']:
                raise ValueError('Connect/home the one owner and leave legacy XML mode first')
            if plan.origin_epoch != self._state['origin_epoch']:
                raise ValueError('Robot origin changed; prepare again')
            # Validate before any packets, then again after communication delays.
            plan.resolve(observer,origin_epoch=self._state['origin_epoch'],
                limits=self.settings.xy_limits_mm,simulation=self.simulation)
            self._check(DmiMessages.ACK)
            position = self._check(DmiMessages.GET_CURRENT_POSITION)
            if any(type(v) is not int or not 0 <= v < lim for v,lim in zip(position,self.settings.xy_limits_mm)):
                self._invalidate('fault','INVALID_POSITION');self._close()
                raise ValueError('Controller position exceeds configured travel limits')
            xy = plan.resolve(observer,origin_epoch=self._state['origin_epoch'],
                limits=self.settings.xy_limits_mm,simulation=self.simulation,position=position)
            try:
                success = self._link.move(*xy)
                response = self._link.response
                if not success:
                    raise RuntimeError(response or 'MOVE_FAILED')
            except Exception as exc:
                self._invalidate('fault',self._link.response or str(exc));self._close()
                raise
            self._state = {**self._state,'response':response,'last_response_at':time.monotonic()}
            return {**plan.preview(),'response':response,'command':'MOVE','requested_z_mm':0,
                    'start_xy_mm':position,'simulation':self.simulation,
                    'alignment_verified':False,'ui_outcome':'not_requested'}

    def end_legacy(self) -> None:
        with self._exclusive():
            self._legacy = False

    def prepare_physical_press(self, observer, selection, envelope_path, *, experimental_one_click=False):
        from dmi_robot_master.integration.move_only import prepare_move
        from dmi_robot_master.integration.physical_press import PhysicalPressPlan
        from dmi_robot_master.integration.recorded_test import RecordedTestProjector, prepare_recorded_press
        with self._exclusive():
            if (self.simulation or self._link is None or not self._state['homed'] or self._legacy):
                raise ValueError('Connect/home the hardware owner and leave legacy XML mode first')
            if type(observer.projector) is RecordedTestProjector:
                return prepare_recorded_press(observer, selection, origin_epoch=self._state['origin_epoch'],
                                              limits=self.settings.xy_limits_mm, one_click=experimental_one_click)
            if experimental_one_click:
                raise ValueError('One-click testing requires the experimental SENSE mapping')
            target = prepare_move(observer, selection, envelope_path,
                origin_epoch=self._state['origin_epoch'], limits=self.settings.xy_limits_mm, simulation=False)
            return PhysicalPressPlan(target)

    def press_physical_once(self, plan, observer, *, operator_confirmed, checks):
        """One commissioned right-button click; no file/model is promoted."""
        from dmi_robot_master.integration.physical_press import PhysicalPressPlan, PHYSICAL_PRESS_CHECKS
        from dmi_robot_master.integration.recorded_test import RecordedPressPlan
        with self._exclusive():
            if (self.simulation or self._link is None or not self._state['homed'] or self._legacy
                    or type(plan) not in (PhysicalPressPlan, RecordedPressPlan)):
                raise ValueError('No initialized hardware owner for this physical press')
            created_at = plan.created_at if type(plan) is RecordedPressPlan else plan.target.created_at
            if created_at <= self._last_press_created_at:
                raise ValueError('Physical press intent already consumed or superseded')
            # Every confirmation attempt consumes its intent, even if a guard fails.
            self._last_press_created_at = created_at
            if (operator_confirmed is not True or not isinstance(checks, dict)
                    or any(checks.get(k) is not True for k in PHYSICAL_PRESS_CHECKS)
                    or any(self._state.get('operator_checks', {}).get(k) is not True for k in HOMING_CHECKS)):
                raise ValueError('Confirm one physical press and all robot readiness checks')
            plan.resolve(observer, origin_epoch=self._state['origin_epoch'], limits=self.settings.xy_limits_mm)
            self._check(DmiMessages.ACK)
            position = self._check(DmiMessages.GET_CURRENT_POSITION)
            if (len(position) != 2 or any(type(v) is not int or not 0 <= v < lim
                                         for v,lim in zip(position,self.settings.xy_limits_mm))):
                self._invalidate('fault', 'INVALID_POSITION'); self._close()
                raise ValueError('Invalid controller position before physical press')
            resolved = {}
            if type(plan) is RecordedPressPlan and plan.one_click:
                xy, sample = plan.resolve(observer, origin_epoch=self._state['origin_epoch'],
                    limits=self.settings.xy_limits_mm, position=position, with_sample=True)
                resolved = {'pixel': list(sample['target']['pixel']),
                    'predicted_xy_mm': list(sample['target']['mm']),
                    'evidence_capture_index': sample['capture_index'],
                    'missed_detection_updates': sample.get('missed_updates', 0)}
            else:
                xy = plan.resolve(observer, origin_epoch=self._state['origin_epoch'],
                    limits=self.settings.xy_limits_mm, position=position)
            envelope = plan.preview()['independent_envelope']
            if (any(not lo <= 0 <= hi for lo, hi in zip(envelope['minimum_xy_mm'], envelope['maximum_xy_mm']))
                    or math.hypot(*xy) > envelope['maximum_move_mm']):
                raise ValueError('Home or return distance exceeds the confirmed movement limits')
            try:
                if not self._link.press(*xy, plan.duration_ms):
                    raise RuntimeError(self._link.response or 'PRESS_FAILED')
            except Exception as exc:
                self._invalidate('fault', self._link.response or str(exc)); self._close()
                raise
            done = time.monotonic()
            self._state = {**self._state, 'response': self._link.response, 'last_response_at': done}
            return {**plan.preview(), **resolved, 'command_xy_mm': list(xy),
                    'command': 'MOVE_AND_CLICK', 'response': self._link.response,
                    'simulation': isinstance(self._link.transport, FakeTransport),
                    'done_at_monotonic': done, 'physical_contact_verified': False,
                    'ui_outcome': 'unconfirmed', 'verification_reason': 'DONE is protocol completion; inspect new DMI observations. No retry.'}

    def press_once(self, plan, observer, *, operator_confirmed: bool, checks: dict) -> dict:
        """Simulation entry point; physical commissioning uses its separate guard."""
        from dmi_robot_master.integration.actions import check_hardware_readiness, SessionMode
        from dmi_robot_master.integration.pressing import PRESS_CHECKS, PressPlan
        with self._exclusive():
            if (self.simulation is not True or self._link is None or
                    not isinstance(self._link.transport,FakeTransport)):
                raise ValueError('Physical vision pressing is disabled pending independent hardware validation')
            if (type(plan) is not PressPlan or operator_confirmed is not True or
                    not isinstance(checks,dict) or any(checks.get(k) is not True for k in PRESS_CHECKS)):
                raise ValueError('Explicitly confirm one simulated press and all readiness checks')
            if self._legacy or not self._state['homed']:
                raise ValueError('Initialize the one owner and leave legacy XML mode first')
            check_hardware_readiness(SessionMode.PHYSICAL_PRESS,
                {**self._state['operator_checks'],**checks,'homed':True})
            if plan.target.created_at <= self._last_press_created_at:
                raise ValueError('Press intent was already consumed or superseded; prepare again')
            self._last_press_created_at = plan.target.created_at
            plan.resolve(observer,origin_epoch=self._state['origin_epoch'],
                limits=self.settings.xy_limits_mm,simulation=True)
            self._check(DmiMessages.ACK)
            position = self._check(DmiMessages.GET_CURRENT_POSITION)
            if any(type(v) is not int or not 0 <= v < lim for v,lim in zip(position,self.settings.xy_limits_mm)):
                self._invalidate('fault','INVALID_POSITION');self._close()
                raise ValueError('Controller position exceeds configured travel limits')
            xy = plan.resolve(observer,origin_epoch=self._state['origin_epoch'],
                limits=self.settings.xy_limits_mm,simulation=True,position=position)
            try:
                success = self._link.press(*xy,plan.duration_ms)
                response = self._link.response
                if not success:
                    raise RuntimeError(response or 'PRESS_FAILED')
            except Exception as exc:
                self._invalidate('fault',self._link.response or str(exc));self._close()
                raise
            done_at = time.monotonic()
            self._state = {**self._state,'response':response,'last_response_at':done_at}
            return {**plan.preview(),'response':response,'command':'MOVE_AND_CLICK',
                'start_xy_mm':position,'simulation':True,'physical_verified':False,
                'done_at_monotonic':done_at,'ui_outcome':'unconfirmed'}

    def photo(self, name: str, args: tuple, *, directory=None) -> bool:
        with self._exclusive():
            if self._link is None or not self._state['homed']:
                raise ValueError('Initialize the shared owner before legacy photos')
            command = DmiMessages[name]
            if command not in (DmiMessages.TAKE_PICTURES,DmiMessages.GET_PICTURES):
                raise ValueError('Unsupported photo command')
            validate_command(command,list(args),self.settings.xy_limits_mm)
            if directory is not None:
                self._link.commands.controller.image_directory = Path(directory).expanduser().resolve()
            try:
                success,_ = self._link.pictures(command,list(args))
            except Exception as exc:
                self._invalidate('fault',self._link.response or str(exc))
                self._close()
                raise
            response = self._link.response
            if not success and response not in ('ERROR','INCOMPLETE_PICTURE'):
                self._invalidate('fault',response)
                self._close()
            else:
                self._state = {**self._state,'response':response,'last_response_at':time.monotonic()}
            return success

    def close(self) -> None:
        with self._exclusive():
            try:
                self._close()
            except Exception:
                self._invalidate('fault', 'CLOSE_FAILED')
                raise
            else:
                self._invalidate('disconnected')
