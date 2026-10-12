"""Existing controller protocol with bounded fake transport and response trace."""
from __future__ import annotations

from collections import deque
from threading import Event
import time

from dmi_robot_common.DmiMessages import DmiMessages
from dmi_robot_master.DmiControllerMaster import DmiControllerMaster
from dmi_robot_master.integration.commands import RobotCommands
from dmi_robot_rasp.DmiControllerSlave import DmiControllerSlave


class FakeRobot:
    def __init__(self, limits_mm: tuple[int, int], success: bool = True) -> None:
        self._X, self._Y = limits_mm
        self.success = success
        self.calls = []

    def live_movement(self, x_mm: int, y_mm: int, z: int) -> bool:
        self.calls.append(('move', x_mm, y_mm, z))
        return self.success

    def click(self, x_mm: int, y_mm: int, duration_ms: int) -> bool:
        self.calls.append(('press', x_mm, y_mm, duration_ms))
        return self.success


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
        self._reply = None
        self._ready_at = 0.0
        self._closed = Event()
        self.slave = DmiControllerSlave(self.robot, self._reply_from_robot,
                                       lambda: self._incoming.popleft())

    def _reply_from_robot(self, packet: list[int]) -> bool:
        self._reply = packet
        return True

    def put_data(self, packet: list[int]) -> bool:
        if self._closed.is_set():
            return False
        self.sent.append(list(packet))
        self._incoming.append(list(packet))
        self._reply = None
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
        packet, self._reply = self._reply, None
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
            self.response = {DmiMessages.DONE.value: 'DONE', DmiMessages.ERROR.value: 'ERROR'}.get(packet[0], 'INVALID_RESPONSE')
            if self.response == 'DONE' and len(packet) != 1:
                self.response = 'INVALID_RESPONSE'
        return packet

    def move(self, x_mm: int, y_mm: int) -> bool:
        success, _ = self.commands.move(x_mm, y_mm)
        if not success and self.response is None:
            self.response = 'TIMEOUT'
        return success and self.response == 'DONE'

    def press(self, x_mm: int, y_mm: int, duration_ms: int) -> bool:
        success, _ = self.commands.press(x_mm, y_mm, duration_ms)
        if not success and self.response is None:
            self.response = 'TIMEOUT'
        return success and self.response == 'DONE'

    def close(self) -> None:
        self.transport.close()
