"""Phase 1 checks: fake devices/transport only, never bind a robot socket."""

import importlib
import pathlib
import runpy
import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

from dmi_robot_common.ComProtocol import ComProtocol
from dmi_robot_common.DmiMessages import DmiMessages as Message
from dmi_robot_common.UDPSocketManager import UDPSocketManager
from dmi_robot_common.YamlCfg import YamlCfg
from dmi_robot_master.DmiControllerMaster import DmiControllerMaster
from dmi_robot_master.integration.commands import RobotCommands
from dmi_robot_rasp.DmiControllerSlave import DmiControllerSlave

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FakeRobot:
    _X = 380
    _Y = 470

    def __init__(self):
        self.calls = []
        self.success = True
        self.current_x_y_position = (12, 34)

    def live_movement(self, *args):
        self.calls.append(('move', args))
        return self.success

    def click(self, *args):
        self.calls.append(('press', args))
        return self.success

    def initialize_hardware(self):
        self.calls.append(('initialize', ()))
        return self.success

    def return_to_zero(self):
        self.calls.append(('zero', ()))
        return self.success

    def take_picture(self, *args):
        raise RuntimeError('Camera is not initialized')


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.robot = FakeRobot()
        self.incoming = []
        self.replies = []
        self.sent = []
        self.slave = DmiControllerSlave(
            self.robot, lambda msg: self.replies.append(msg) or True,
            lambda: self.incoming.pop(0) if self.incoming else [],
        )
        def send(msg):
            self.sent.append(msg)
            self.incoming.append(msg)
            self.slave.run()
            return True
        self.master = DmiControllerMaster(
            send, lambda: self.replies.pop(0) if self.replies else [],
        )
        self.commands = RobotCommands(self.master, (380, 470), 0.01)

    def action(self, command, data, expected=Message.DONE, length=0):
        return self.master.manage_action(DmiControllerMaster.Action(
            command, data, expected, length, 0.01, 0.001,
        ))

    def test_absolute_millimeters_and_millisecond_payloads(self):
        self.assertEqual(self.commands.move(100, 300), (True, []))
        self.assertEqual(self.commands.press(120, 320, 250), (True, []))
        self.assertEqual(self.robot.calls, [('move', (100, 300, 0)), ('press', (120, 320, 250))])
        self.assertEqual(self.sent, [[3, 100, 300, 0], [1, 120, 320, 250]])

    def test_existing_control_commands(self):
        self.assertEqual(self.action(Message.ACK, [], Message.ACK), (True, []))
        self.assertEqual(self.action(Message.INITIALIZE, []), (True, []))
        self.assertEqual(self.action(Message.RETURN_TO_ZERO, []), (True, []))
        self.assertEqual(self.action(Message.GET_CURRENT_POSITION, [], length=2), (True, [12, 34]))
        self.assertEqual(self.robot.calls, [('initialize', ()), ('zero', ())])

    def test_adapter_rejects_without_sending(self):
        for args in [(-1, 2), (380, 0), (0, 470), (1.5, 2), (True, 2), (2**31, 2)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.commands.move(*args)
        with self.assertRaises(ValueError):
            self.commands.press(1, 2, -1)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.commands.move(379, 469), (True, []))

    def test_slave_rejects_bad_packets_before_robot_call(self):
        for packet in [[999], [3], [3, -1, 0, 0], [3, 380, 0, 0],
                       [1, 0, 0, -1], [3, 0.5, 0, 0], [5, 1], [10, -1, 1, 0]]:
            with self.subTest(packet=packet):
                self.incoming.append(packet)
                self.slave.run()
                self.assertEqual(self.replies.pop(), [Message.ERROR.value])
        self.assertEqual(self.robot.calls, [])

    def test_false_and_exception_propagate_error_without_retry(self):
        self.robot.success = False
        self.assertEqual(self.commands.press(1, 2, 200), (False, []))
        self.robot.click = Mock(side_effect=RuntimeError('motor failed'))
        self.assertEqual(self.commands.press(1, 2, 200), (False, []))
        self.assertEqual(len(self.sent), 2)
        self.robot.click.assert_called_once()

    def test_uninitialized_camera_is_failure(self):
        self.assertEqual(self.action(Message.TAKE_PICTURES, [0, 1, 100]), (False, []))

    def test_send_failure_timeout_disconnect_and_error(self):
        for send, receive in [
            (Mock(return_value=False), Mock()),
            (Mock(return_value=True), Mock(return_value=[])),
            (Mock(return_value=True), Mock(side_effect=ConnectionError('disconnected'))),
            (Mock(return_value=True), Mock(return_value=[Message.ERROR.value])),
            (Mock(return_value=True), Mock(return_value=[999])),
        ]:
            with self.subTest(receive=receive):
                commands = RobotCommands(DmiControllerMaster(send, receive), (380, 470), 0.002)
                self.assertEqual(commands.press(1, 2, 100), (False, []))
                send.assert_called_once_with([1, 1, 2, 100])
        receive = Mock(side_effect=[[Message.ERROR.value], [Message.DONE.value]])
        commands = RobotCommands(DmiControllerMaster(Mock(return_value=True), receive), (380, 470), 1)
        self.assertEqual(commands.move(1, 2), (False, []))
        self.assertEqual(receive.call_count, 1)


class ProtocolTests(unittest.TestCase):
    def test_shared_protocol_round_trip_and_invalid_envelopes(self):
        socket = Mock()
        with patch('dmi_robot_common.ComProtocol.UDPSocketManager', return_value=socket):
            master = ComProtocol(('pc', 50, 0xBBBB), ('pi', 2000, 0xAAAA))
            slave = ComProtocol(('pi', 2000, 0xAAAA), ('pc', 50, 0xBBBB))
        socket.send.return_value = True
        self.assertTrue(master.put_data([1, 120, 300, 250]))
        envelope = socket.send.call_args.args[0]
        self.assertEqual(envelope[:7], [0xBBBB, 0xAAAA, 4, 1, 120, 300, 250])
        socket.receive.return_value = envelope
        self.assertEqual(slave.get_data(), [1, 120, 300, 250])
        for index in [0, 1, 2, -1]:
            invalid = envelope.copy()
            invalid[index] ^= 1
            socket.receive.return_value = invalid
            self.assertEqual(slave.get_data(), [])
        master.close()
        socket.close.assert_called_once()

    def test_udp_wire_encoding_and_cleanup_without_network(self):
        sock = Mock()
        with patch('dmi_robot_common.UDPSocketManager.socket.socket', return_value=sock):
            transport = UDPSocketManager(('pc', 50))
        payload = [0xBBBB, 0xAAAA, 4, 1, 120, 300, 250, 0]
        wire = struct.pack('!I', len(payload)) + struct.pack('!8i', *payload)
        sock.sendto.return_value = len(wire)
        self.assertTrue(transport.send(payload, ('pi', 2000)))
        sock.sendto.assert_called_once_with(wire, ('pi', 2000))
        sock.recvfrom.return_value = (wire, ('pi', 2000))
        self.assertEqual(transport.receive(), payload)
        sock.recvfrom.return_value = (wire[:-4], ('pi', 2000))
        self.assertEqual(transport.receive(), [])
        sock.recvfrom.side_effect = BlockingIOError()
        self.assertEqual(transport.receive(), [])
        sock.recvfrom.side_effect = OSError('disconnected')
        with self.assertRaises(OSError):
            transport.receive()
        transport.close()
        sock.close.assert_called_once()


class StartupTests(unittest.TestCase):
    def test_configs_and_gui_imports_from_another_directory(self):
        for name in ['pc_cfg.yaml', 'raspberry_cfg.yaml']:
            cfg = YamlCfg(str(ROOT / 'dmi_robot_config' / name))
            self.assertEqual(len(cfg.address), 3)
            self.assertEqual(len(cfg.remote_address), 3)
        # tkinterdnd2 is optional on this PC; stub only this third-party GUI dependency.
        dnd = types.ModuleType('tkinterdnd2')
        dnd.TkinterDnD = Mock()
        dnd.DND_FILES = 'DND_Files'
        with patch.dict(sys.modules, {'tkinterdnd2': dnd}):
            gui = runpy.run_path(str(ROOT / 'dmi_robot_master' / 'DmiGUI.pyw'))
        self.assertIs(gui['DmiControllerMaster'], DmiControllerMaster)
        panel = gui['DmiControlPanel'].__new__(gui['DmiControlPanel'])
        with patch.dict(panel._init_hardware_controller.__globals__,
                        {'setup_logging': Mock(), 'ComProtocol': Mock()}):
            panel._init_hardware_controller()
        self.assertIsInstance(panel.dmi_controller, DmiControllerMaster)

    def test_master_and_slave_entrypoints_with_fake_devices(self):
        transport = Mock()
        transport.get_data.return_value = [Message.ACK.value]
        with patch('dmi_robot_common.ComProtocol.ComProtocol', return_value=transport), \
             patch('dmi_robot_common.Logger.setup_logging'):
            runpy.run_path(str(ROOT / 'dmi_robot_master' / 'DmiControllerMaster.py'), run_name='__main__')
        transport.put_data.assert_called_once_with([Message.ACK.value])
        transport.close.assert_called_once()

        robot_module = types.ModuleType('dmi_robot_rasp.DmiRobot')
        robot_module.DmiRobot = Mock()
        robot = robot_module.DmiRobot.return_value
        transport = Mock()
        transport.get_data.side_effect = KeyboardInterrupt()
        with patch.dict(sys.modules, {'dmi_robot_rasp.DmiRobot': robot_module}), \
             patch('dmi_robot_common.ComProtocol.ComProtocol', return_value=transport), \
             patch('dmi_robot_common.Logger.setup_logging'), self.assertRaises(KeyboardInterrupt):
            runpy.run_path(str(ROOT / 'dmi_robot_rasp' / 'DmiControllerSlave.py'), run_name='__main__')
        robot_module.DmiRobot.assert_called_once()
        transport.close.assert_called_once()
        robot._button.close.assert_called_once()

    def test_real_robot_methods_absolute_offsets_and_duration_without_gpio(self):
        camera = types.ModuleType('picamera2')
        camera.Picamera2 = Mock()
        gpio = types.ModuleType('lgpio')
        with patch.dict(sys.modules, {'picamera2': camera, 'lgpio': gpio}):
            cls = importlib.import_module('dmi_robot_rasp.DmiRobot').DmiRobot
        robot = cls.__new__(cls)
        robot._x_steps, robot._y_steps, robot._z_steps = 10, 20, 0
        robot._x_total_steps, robot._y_total_steps = 3800, 4700
        robot._xy_linear_movement_steps = Mock()
        robot._z_click = Mock()
        robot._z_movement = Mock()
        with patch.object(cls, '__repr__', return_value='offline fake hardware'):
            self.assertTrue(robot.live_movement(100, 200, 0))
            robot._xy_linear_movement_steps.assert_called_with(990, 1980, robot._VELOCITY)
            self.assertTrue(robot.click(120, 220, 250))
            robot._xy_linear_movement_steps.assert_called_with(1190, 2180, robot._VELOCITY)
            robot._z_click.assert_called_once_with(0.25, robot._VELOCITY)
        camera.Picamera2.assert_not_called()


if __name__ == '__main__':
    unittest.main()
