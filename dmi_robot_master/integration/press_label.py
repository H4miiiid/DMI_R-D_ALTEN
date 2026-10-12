"""One terminal session: observation stays live while one selected action runs."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr
import json
import logging
from pathlib import Path
import sys
from threading import Event, Lock, Thread

from dmi_computer_vision.src.dmi.io.preview import LivePreview
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_robot_common.ComProtocol import ComProtocol
from dmi_robot_common.YamlCfg import YamlCfg
from dmi_robot_master.integration.actions import LabelActions, SessionMode, check_hardware_readiness
from dmi_robot_master.integration.action_transport import FakeTransport, RobotLink
from dmi_robot_master.integration.camera import ReplayCamera, RobotCamera, RemoteCamera
from dmi_robot_master.integration.calibration import read_json
from dmi_robot_master.integration.observe import observe, check_target_source
from dmi_robot_master.integration.processing_policy import DetectionPolicy
from dmi_robot_master.integration.targets import CurrentTargets

PROMPT = 'KEY_n or quit> '


class TerminalInput:
    """Blocking input belongs to one daemon thread; labels are never queued."""
    def __init__(self, actions: LabelActions, *, input_stream, output_stream, stop_event: Event) -> None:
        self.actions, self.input = actions, input_stream
        self.output, self.stop = output_stream, stop_event
        self._lock = Lock()
        self.error = None
        self.thread = None

    def message(self, result: dict) -> None:
        with self._lock:
            print('\n'+json.dumps(result,allow_nan=False),file=self.output,flush=True)
            if not self.stop.is_set():
                print(PROMPT,end='',file=self.output,flush=True)

    def __enter__(self):
        self.thread = Thread(target=self._read,name='dmi-terminal-input',daemon=True)
        self.thread.start()
        return self

    def _read(self):
        try:
            with self._lock:
                print(PROMPT,end='',file=self.output,flush=True)
            while not self.stop.is_set():
                line = self.input.readline()
                if not line or line.strip().lower() == 'quit':
                    self.stop.set()
                    return
                label = line.strip()
                if not label:
                    continue
                result = self.actions.request(label)
                if result.get('pending') or 'response' not in result:
                    self.message(result)
        except BaseException as exc:
            self.error = exc
            self.stop.set()

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=.2)
        # readline cannot portably be cancelled. An abandoned input-only daemon
        # owns no camera/socket and cannot dispatch after the stop flag is set.


def run_terminal(source, directory: str | Path, *, source_info: dict, link: RobotLink,
                 calibration_path: str | Path, context_path: str | Path,
                 evidence_tolerance_px: float, mode: SessionMode = SessionMode.DRY_RUN,
                 policy: DetectionPolicy | None = None, preview=None,
                 press_duration_ms: int = 200, verification_timeout_seconds: float = 5.0,
                 hardware_checks: dict | None = None, input_stream=None, output_stream=None,
                 debug: bool = False) -> dict:
    """Main thread owns detection/optional GUI; action and input use separate workers."""
    directory = Path(directory).expanduser().resolve()
    if directory.exists():
        raise FileExistsError(f'Choose a new session output directory: {directory}')
    directory.parent.mkdir(parents=True,exist_ok=True)
    # Separate logs can be created before observe creates its fresh directory.
    progress_path = directory.parent/(directory.name+'_progress.log')
    action_path = directory.parent/(directory.name+'_button_tests.jsonl')
    stop = Event()
    targets, state = CurrentTargets(), LatestState()
    result = None
    actions = None
    with ExitStack() as stack:
        if preview is not None:
            stack.callback(preview.close)
        progress = stack.enter_context(progress_path.open('x',encoding='utf-8'))
        action_log = stack.enter_context(action_path.open('x',encoding='utf-8'))
        stack.callback(link.close)
        stack.enter_context(redirect_stderr(progress))
        # Bind logging directly to the file; frequent detector/master warnings
        # must not share the terminal prompt.
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        handler = logging.StreamHandler(progress)
        root_logger.handlers = [handler]
        stack.callback(setattr,root_logger,'handlers',original_handlers)
        actions = LabelActions(targets,state,link,calibration_path=calibration_path,
            context_path=context_path,source_info=source_info,policy=policy,mode=mode,
            press_duration_ms=press_duration_ms,verification_timeout_seconds=verification_timeout_seconds,
            hardware_checks=hardware_checks,source_check=lambda:check_target_source(source,source_info),
            log_stream=action_log,stop_event=stop)
        stack.callback(actions.close)
        terminal = TerminalInput(actions,input_stream=input_stream or sys.stdin,
                                 output_stream=output_stream or sys.stdout,stop_event=stop)
        actions.on_result = terminal.message
        print(f'MODE: {SessionMode(mode).value} | TRANSPORT: {"HARDWARE" if link.hardware else "FAKE/SIMULATION"}',
              file=terminal.output,flush=True)
        print(f'Progress: {progress_path}\nAction log: {action_path}',file=terminal.output,flush=True)
        stack.enter_context(terminal)
        try:
            result = observe(source,directory,source_info=source_info,latest_state=state,
                current_targets=targets,processing_policy=policy,annotations=preview is not None,
                preview=preview,debug=debug,export_targets=True,calibration_path=calibration_path,
                calibration_context=read_json(context_path),evidence_tolerance_px=evidence_tolerance_px,
                stop_event=stop)
        finally:
            stop.set()
        if isinstance(terminal.error,KeyboardInterrupt):
            raise terminal.error
        if terminal.error is not None:
            raise RuntimeError('Terminal input failed') from terminal.error
    return {'observation':result,'last_action':actions.last_result,
            'progress_path':str(progress_path),'action_log_path':str(action_path)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--replay',type=Path)
    sources.add_argument('--camera',type=int)
    sources.add_argument('--bridge-url')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--calibration',type=Path,required=True)
    parser.add_argument('--calibration-context',type=Path,required=True)
    parser.add_argument('--evidence-tolerance-px',type=float,required=True)
    parser.add_argument('--max-x-mm',type=int,required=True)
    parser.add_argument('--max-y-mm',type=int,required=True)
    parser.add_argument('--mode',choices=[m.value for m in SessionMode],default='dry-run')
    parser.add_argument('--transport',choices=['fake','udp'],default='fake')
    parser.add_argument('--robot-config',type=Path)
    parser.add_argument('--hardware-checks',type=Path)
    parser.add_argument('--fake-response',choices=['DONE','ERROR','TIMEOUT','DISCONNECT'],default='DONE')
    parser.add_argument('--fake-delay',type=float,default=0)
    parser.add_argument('--command-timeout',type=float,default=5)
    parser.add_argument('--verification-timeout',type=float,default=5)
    parser.add_argument('--press-ms',type=int,default=200)
    parser.add_argument('--replay-fps',type=float)
    parser.add_argument('--start-seconds',type=float,default=0)
    parser.add_argument('--width',type=int)
    parser.add_argument('--height',type=int)
    parser.add_argument('--rotation',type=int,choices=[0,90,180,270],default=0)
    parser.add_argument('--mirror',action='store_true')
    parser.add_argument('--processing',choices=['regular','selective'],default='selective')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--debug',action='store_true')
    args = parser.parse_args(argv)
    preview = LivePreview() if args.preview else None
    link = transport = None
    try:
        mode = SessionMode(args.mode)
        if any(type(v) is not int or not 0 < v < 2**31 for v in (args.max_x_mm,args.max_y_mm)):
            raise ValueError('Configure positive signed-32-bit XY limits in mm')
        if not 0 < args.command_timeout < float('inf') or not 0 < args.verification_timeout < float('inf'):
            raise ValueError('Command/verification timeouts must be finite and positive')
        if args.replay is not None and (args.width is not None or args.height is not None):
            raise ValueError('Replay preserves original dimensions; width/height are camera requests')
        if args.replay is None and (args.replay_fps is not None or args.start_seconds):
            raise ValueError('Replay options require --replay')
        checks = read_json(args.hardware_checks) if args.hardware_checks else None
        if args.transport == 'udp':
            if mode not in (SessionMode.MOVE_ONLY,SessionMode.PHYSICAL_PRESS) or args.replay is not None:
                raise ValueError('UDP execution requires explicit physical mode and a live camera source')
            check_hardware_readiness(mode,checks)
            if args.robot_config is None:
                raise ValueError('Explicit PC robot configuration required for UDP')
        if args.replay:
            source = ReplayCamera(args.replay,replay_fps=args.replay_fps,start_seconds=args.start_seconds,
                                  rotation=args.rotation,mirror=args.mirror)
            info = {'kind':'recorded_replay','path':str(source.path),'simulation':True}
        elif args.bridge_url:
            source = RemoteCamera(args.bridge_url,rotation=args.rotation,mirror=args.mirror,
                                  request_fps=10 if args.processing=='selective' else None)
            info = {'kind':'remote_bridge','url':args.bridge_url,'simulation':False}
        else:
            source = RobotCamera(args.camera,width=args.width,height=args.height,
                                 rotation=args.rotation,mirror=args.mirror)
            info = {'kind':'local_camera','index':args.camera,'requested_size':[args.width,args.height],
                    'simulation':False}
        info.update(rotation_clockwise=args.rotation,mirror_horizontal=args.mirror)
        limits = (args.max_x_mm,args.max_y_mm)
        if args.transport == 'fake':
            transport = FakeTransport(limits,response=args.fake_response,delay_seconds=args.fake_delay)
        else:
            cfg = YamlCfg(str(args.robot_config.expanduser().resolve()))
            transport = ComProtocol(cfg.address,cfg.remote_address)
        link = RobotLink(transport,limits_mm=limits,timeout_seconds=args.command_timeout,
                         hardware=args.transport=='udp')
        policy = DetectionPolicy() if args.processing=='selective' else None
        report = run_terminal(source,args.output_dir,source_info=info,link=link,calibration_path=args.calibration,
            context_path=args.calibration_context,evidence_tolerance_px=args.evidence_tolerance_px,
            mode=mode,policy=policy,preview=preview,press_duration_ms=args.press_ms,
            verification_timeout_seconds=args.verification_timeout,hardware_checks=checks,debug=args.debug)
        return 130 if report['observation']['run']['stop_reason']=='interrupted' else 0
    except (ValueError,OSError,RuntimeError) as exc:
        print(f'error: {exc}',file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if link is not None:
            link.close()
        elif transport is not None:
            transport.close()
        if preview is not None:
            preview.close()


if __name__=='__main__':
    raise SystemExit(main())
