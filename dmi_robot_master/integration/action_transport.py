"""Existing controller protocol with bounded fake transport and response trace."""
from __future__ import annotations

from collections import deque
from threading import Event
import time

from dmi_robot_common.DmiMessages import DmiMessages
from dmi_robot_common.command_validation import validate_command
from dmi_robot_master.DmiControllerMaster import DmiControllerMaster
from dmi_robot_master.integration.commands import RobotCommands
from dmi_robot_rasp.DmiControllerSlave import DmiControllerSlave


class FakeRobot:
    def __init__(self, limits_mm: tuple[int, int], success: bool = True) -> None:
        self._X, self._Y = limits_mm
        self.success = success
        self.calls = []
        self.picture_paths = []

    def live_movement(self, x_mm: int, y_mm: int, z: int) -> bool:
        self.calls.append(('move', x_mm, y_mm, z))
        return self.success

    def click(self, x_mm: int, y_mm: int, duration_ms: int, x_y_return_to_zero: bool = False) -> bool:
        self.return_after_click = x_y_return_to_zero
        self.calls.append(('press', x_mm, y_mm, duration_ms))
        return self.success

    def initialize_hardware(self) -> bool:
        self.calls.append(('initialize',))
        return self.success

    def take_picture(self, camera, count, duration_ms):
        self.calls.append(('pictures', camera, count, duration_ms))
        return list(self.picture_paths[:count]) if self.success else []

    @property
    def current_x_y_position(self):
        return (0, 0)  # Simulation only, not independent position feedback.


class FakeTransport:
    def __init__(self, limits_mm: tuple[int, int], *, response: str = 'DONE',
                 delay_seconds: float = 0.0, on_done=None) -> None:
        if response not in ('DONE', 'ERROR', 'TIMEOUT', 'DISCONNECT'):
            raise ValueError('Unknown fake response')
        if not 0 <= delay_seconds < float('inf'):
            raise ValueError('Fake delay must be finite and nonnegative')
        self.robot = FakeRobot(limits_mm, success=response != 'ERROR')
        self.response, self.delay_seconds, self.on_done = response, delay_seconds, on_done
        self.sent = []
        self._incoming = deque()
        self._replies = deque()
        self._ready_at = 0.0
        self._closed = Event()
        self.slave = DmiControllerSlave(self.robot, self._reply_from_robot,
                                       lambda: self._incoming.popleft())

    def _reply_from_robot(self, packet: list[int]) -> bool:
        self._replies.append(packet)
        return True

    def put_data(self, packet: list[int]) -> bool:
        if self._closed.is_set():
            return False
        self.sent.append(list(packet))
        self._incoming.append(list(packet))
        self._replies.clear()
        self.slave.run()
        self._ready_at = time.monotonic() + self.delay_seconds
        return True

    def get_data(self) -> list[int]:
        if self._closed.is_set():
            raise ConnectionError('Fake transport closed')
        if self.response == 'TIMEOUT' or time.monotonic() < self._ready_at:
            return []
        if self.response == 'DISCONNECT':
            raise ConnectionError('Simulated robot disconnect')
        packet = self._replies.popleft() if self._replies else None
        if packet is not None and packet[0] == DmiMessages.DONE.value and self.on_done is not None:
            self.on_done()
        return packet or []

    def close(self) -> None:
        self._closed.set()


class RobotLink:
    """Trace the response without changing the master/slave wire protocol."""
    def __init__(self, transport, *, limits_mm: tuple[int, int], timeout_seconds: float,
                 hardware: bool = False) -> None:
        self.transport, self.hardware = transport, hardware
        self.response = None
        self._expected = (DmiMessages.DONE.value, 0)
        self._pictures = False
        self.commands = RobotCommands(DmiControllerMaster(self._send, self._receive),
                                      limits_mm, timeout_seconds)

    def _send(self, packet: list[int]) -> bool:
        self.response = None
        try:
            sent = self.transport.put_data(packet)
        except OSError:
            self.response = 'DISCONNECT'
            raise
        if not sent:
            self.response = 'SEND_FAILED'
        return sent

    def _receive(self) -> list[int]:
        try:
            packet = self.transport.get_data()
        except (OSError, ConnectionError):
            self.response = 'DISCONNECT'
            raise
        if packet:
            expected, length = self._expected
            if packet[0] == DmiMessages.ERROR.value:
                self.response = 'ERROR'
            elif self._pictures and packet[0] in (DmiMessages.PICTURE.value,DmiMessages.PICTURE_DATA.value):
                self.response = DmiMessages(packet[0]).name
            elif packet[0] == expected and (length is None or len(packet) == length+1):
                self.response = DmiMessages(expected).name
            else:
                self.response = 'INVALID_RESPONSE'
        return packet

    def move(self, x_mm: int, y_mm: int) -> bool:
        self._expected = (DmiMessages.DONE.value, 0)
        success, _ = self.commands.move(x_mm, y_mm)
        if not success and self.response is None:
            self.response = 'TIMEOUT'
        return success and self.response == 'DONE'

    def press(self, x_mm: int, y_mm: int, duration_ms: int) -> bool:
        self._expected = (DmiMessages.DONE.value, 0)
        success, _ = self.commands.press(x_mm, y_mm, duration_ms)
        if not success and self.response is None:
            self.response = 'TIMEOUT'
        return success and self.response == 'DONE'

    def check(self, command: DmiMessages) -> tuple[bool, list[int]]:
        """Existing ACK/init/position wire messages; caller serializes ownership."""
        if command not in (DmiMessages.ACK, DmiMessages.INITIALIZE, DmiMessages.GET_CURRENT_POSITION):
            raise ValueError('Unsupported readiness command')
        validate_command(command, [], self.commands.xy_limits_mm)
        expected = DmiMessages.ACK if command == DmiMessages.ACK else DmiMessages.DONE
        length = 2 if command == DmiMessages.GET_CURRENT_POSITION else 0
        self._expected = (expected.value, length)
        success, data = self.commands.controller.manage_action(DmiControllerMaster.Action(
            command, [], expected, length, self.commands.timeout_seconds, .001))
        if not success and self.response is None:
            self.response = 'TIMEOUT'
        return bool(success and self.response == expected.name), data

    def pictures(self, command: DmiMessages, data: list[int]):
        """Existing photo transaction on this same owner; no extra camera client."""
        if command not in (DmiMessages.TAKE_PICTURES,DmiMessages.GET_PICTURES):
            raise ValueError('Unsupported photo command')
        validate_command(command,data,self.commands.xy_limits_mm)
        expected = DmiMessages.PICTURE if command == DmiMessages.GET_PICTURES else DmiMessages.DONE
        self._expected = (expected.value,None if expected == DmiMessages.PICTURE else 0)
        self._pictures = expected == DmiMessages.PICTURE
        try:
            success, result = self.commands.controller.manage_action(DmiControllerMaster.Action(
                command,data,expected,None if self._pictures else 0,self.commands.timeout_seconds,.001))
            if success:
                self.response = expected.name
            elif self.response is None:
                self.response = 'TIMEOUT'
            elif self.response in ('PICTURE','PICTURE_DATA'):
                self.response = 'INCOMPLETE_PICTURE'
            return bool(success),result
        finally:
            self._pictures = False

    def close(self) -> None:
        self.transport.close()
