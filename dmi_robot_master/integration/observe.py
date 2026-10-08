"""One observation-only command for robot camera or paced simulation replay."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import cv2

from dmi_computer_vision.src.dmi.io.preview import LivePreview
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_computer_vision.src.dmi.pipeline.live import process_live
from dmi_robot_master.integration.camera import ReplayCamera, RobotCamera, RemoteCamera


class AnnotationSink:
    """Stream one annotated video frame and receipt metadata per processed frame."""
    def __init__(self, directory: Path, source, preview=None) -> None:
        self.directory, self.source, self.preview = directory, source, preview
        self.writer = None
        self.shape = None
        self.count = 0
        self.stream = None

    def __enter__(self):
        self.stream = (self.directory / 'processed_frames.jsonl').open('x', encoding='utf-8')
        return self

    def show(self, image) -> bool:
        packet = self.source.last_packet
        if self.writer is None:
            self.shape = image.shape
            self.writer = cv2.VideoWriter(str(self.directory / 'annotated.mp4'),
                cv2.VideoWriter_fourcc(*'mp4v'), 5.0, (image.shape[1], image.shape[0]))
            if not self.writer.isOpened():
                raise RuntimeError('Cannot open annotation video writer')
        if image.shape != self.shape:
            raise RuntimeError('Frame size changed; start a new observation session')
        self.writer.write(image)
        record = {'processed_frame_index': self.count, 'capture_index': packet.capture_index,
                  'received_at_monotonic': packet.received_at,
                  'received_at_utc': packet.received_at_utc,
                  'source_video_seconds': packet.source_video_seconds,
                  'remote_capture_age_seconds': packet.remote_capture_age_seconds,
                  'transport_round_trip_seconds': packet.transport_round_trip_seconds,
                  'frame_size': [image.shape[1], image.shape[0]],
                  'receipt_to_saved_annotation_seconds': time.monotonic() - packet.received_at}
        self.stream.write(json.dumps(record, allow_nan=False) + '\n')
        self.stream.flush()
        self.count += 1
        return self.preview.show(image) if self.preview is not None else True

    def __exit__(self, *args):
        if self.writer is not None:
            self.writer.release()
        if self.stream is not None:
            self.stream.close()


def observe(source: ReplayCamera | RobotCamera | RemoteCamera, directory: str | Path, *, source_info: dict,
            max_frames: int | None = None, preview=None, debug=False,
            latest_state: LatestState | None = None) -> dict:
    """Observe and annotate. Source is the sole owner; no motor transport exists."""
    directory = Path(directory).expanduser().resolve()
    # Require a new output directory so partial artifacts cannot be overwritten.
    directory.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    run = None
    failure = None
    try:
        with source, AnnotationSink(directory, source, preview) as sink:
            run = process_live(source, directory, source_info=source_info,
                max_frames=max_frames, preview=sink.show, debug=debug,
                latest_state=latest_state or LatestState())
    except BaseException as exc:
        failure = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        elapsed = time.monotonic() - started
        counters = source.stats()
        report = {'source': source_info, 'simulation': bool(source_info.get('simulation', source_info['kind'] == 'recorded_replay')),
                  'processing_host': 'local PC', 'elapsed_seconds': elapsed,
                  'capture_fps': (None if isinstance(source, RemoteCamera) else
                                  counters['captured_frames'] / max(elapsed, 1e-9)),
                  'capture_counters': counters, 'error': failure,
                  'annotation_playback_fps': 5.0,
                  'limits': 'Local receipt excludes upstream capture age; only recording/fake-source runs are simulation.'}
        if run is not None:
            report.update({'run': asdict(run),
                           'processed_fps': run.processed_frames / max(elapsed, 1e-9)})
        (directory / 'session.json').write_text(json.dumps(report, default=str, indent=2) + '\n')
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--replay', type=Path)
    inputs.add_argument('--bridge-url', help='Pi frame bridge HTTP(S) /frame.jpg URL')
    inputs.add_argument('--camera', type=int, help='Local PC USB camera index; no stream URLs')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--replay-fps', type=float, help='Default: original recording FPS')
    parser.add_argument('--start-seconds', type=float, default=0.0)
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    parser.add_argument('--rotation', type=int, choices=[0, 90, 180, 270], default=0)
    parser.add_argument('--mirror', action='store_true')
    parser.add_argument('--max-source-age', type=float, default=1.0)
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--preview', action='store_true', help='Main-thread OpenCV preview')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args(argv)
    preview = LivePreview() if args.preview else None
    try:
        if args.max_frames is not None and args.max_frames <= 0:
            raise ValueError('max-frames must be positive')
        if args.replay is not None:
            if args.width is not None or args.height is not None:
                raise ValueError('Replay retains original dimensions; width/height are camera requests')
            source = ReplayCamera(args.replay, replay_fps=args.replay_fps,
                start_seconds=args.start_seconds, rotation=args.rotation,
                mirror=args.mirror, timeout=args.timeout)
            info = {'kind': 'recorded_replay', 'simulation': True, 'path': str(source.path),
                    'replay_fps': args.replay_fps, 'start_seconds': args.start_seconds}
        elif args.bridge_url:
            if args.width is not None or args.height is not None or args.replay_fps is not None or args.start_seconds:
                raise ValueError('Configure dimensions on the bridge; replay options require --replay')
            source = RemoteCamera(args.bridge_url, timeout=args.timeout,
                max_age_seconds=args.max_source_age, rotation=args.rotation, mirror=args.mirror)
            info = {'kind': 'remote_bridge', 'url': args.bridge_url,
                    'max_source_age_seconds': args.max_source_age}
        else:
            if args.replay_fps is not None or args.start_seconds:
                raise ValueError('Replay options require --replay')
            source = RobotCamera(args.camera, width=args.width, height=args.height,
                rotation=args.rotation, mirror=args.mirror, timeout=args.timeout)
            info = {'kind': 'local_camera', 'index': args.camera,
                    'requested_size': [args.width, args.height]}
        info.update({'rotation_clockwise': args.rotation, 'mirror_horizontal': args.mirror})
        print('OBSERVATION ONLY — no robot commands. Replay artifacts are simulation.', flush=True)
        report = observe(source, args.output_dir, source_info=info,
                         max_frames=args.max_frames, preview=preview, debug=args.debug)
        print(json.dumps(report, default=str, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if preview is not None:
            preview.close()


if __name__ == '__main__':
    raise SystemExit(main())
