"""One observation-only command for robot camera or paced simulation replay."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import time

import cv2

from dmi_computer_vision.src.dmi.io.preview import LivePreview
from dmi_computer_vision.src.dmi.output.latest_state import LatestState
from dmi_computer_vision.src.dmi.pipeline.live import process_live
from dmi_robot_master.integration.camera import ReplayCamera, RobotCamera, RemoteCamera
from dmi_robot_master.integration.processing_policy import DetectionPolicy
from dmi_robot_master.integration.publication import ChangePublisher, StatusHeartbeat, project_pixels
from dmi_computer_vision.src.dmi.output.json_writer import write_record


class AnnotationSink:
    """Stream one annotated video frame and receipt metadata per processed frame."""
    def __init__(self, directory: Path, source, preview=None) -> None:
        self.directory, self.source, self.preview = directory, source, preview
        self.writer = None
        self.shape = None
        self.count = 0
        self.stream = None
        self.last_image = None
        self.last_received = None

    def __enter__(self):
        self.stream = (self.directory / 'processed_frames.jsonl').open('x', encoding='utf-8')
        return self

    def show(self, image) -> bool:
        packet = self.source.last_packet
        self.last_image, self.last_received = image, packet.received_at
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

    def idle(self) -> bool:
        if self.preview is None or self.last_image is None:
            return True
        image = self.last_image.copy()
        age = time.monotonic() - self.last_received
        cv2.putText(image, f"REUSED OBSERVATION - age {age:.2f}s", (15, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 180, 255), 2)
        return self.preview.show(image)

    def __exit__(self, *args):
        if self.writer is not None:
            self.writer.release()
        if self.stream is not None:
            self.stream.close()


def observe(source: ReplayCamera | RobotCamera | RemoteCamera, directory: str | Path, *, source_info: dict,
            max_frames: int | None = None, preview=None, debug=False,
            latest_state: LatestState | None = None,
            processing_policy: DetectionPolicy | None = None, annotations: bool = True,
            publication: bool = False, tolerance_px: float = 4.0,
            heartbeat_seconds: float = 0.5, max_evidence_age_seconds: float = 1.5,
            max_capture_frames: int | None = None) -> dict:
    """Observe and annotate. Source is the sole owner; no motor transport exists."""
    directory = Path(directory).expanduser().resolve()
    # Require a new output directory so partial artifacts cannot be overwritten.
    directory.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    run = None
    failure = None
    publisher = None
    try:
        with ExitStack() as stack:
            stack.enter_context(source)
            sink = stack.enter_context(AnnotationSink(directory, source, preview)) if annotations else None
            if preview is not None and sink is None:
                raise ValueError('Preview requires annotations')
            callback = None
            if publication:
                events = stack.enter_context((directory / 'publication_review.jsonl').open('x', encoding='utf-8'))
                publisher = ChangePublisher(lambda event: write_record(events, event),
                    tolerance_px=tolerance_px, heartbeat_seconds=heartbeat_seconds,
                    max_evidence_age_seconds=max_evidence_age_seconds)
                heartbeat = stack.enter_context(StatusHeartbeat(publisher))
                def callback(result, packet, finished):
                    if heartbeat.error is not None:
                        raise RuntimeError('Status publication failed') from heartbeat.error
                    publisher.update(project_pixels(result,
                        frame_size=(packet.image.shape[1], packet.image.shape[0])),
                        received_at=packet.received_at, detected_at=finished,
                        observed_at_utc=getattr(packet, 'received_at_utc', None),
                        upstream_age_seconds=(getattr(packet, 'remote_capture_age_seconds', 0.0) +
                                              getattr(packet, 'transport_round_trip_seconds', 0.0)))
            run = process_live(source, directory, source_info=source_info,
                max_frames=max_frames, preview=sink.show if sink else None, debug=debug,
                latest_state=latest_state or LatestState(), processing_policy=processing_policy,
                annotate=annotations, on_detection=callback,
                on_skipped=sink.idle if sink else None, max_capture_frames=max_capture_frames)
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
        report['policy'] = processing_policy.stats() if processing_policy else None
        report['publication'] = ({'target_updates': publisher.updates, 'heartbeats': publisher.heartbeats,
                                  'pixel_tolerance': publisher.tolerance} if publisher else None)
        report['annotations_enabled'] = annotations
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
    parser.add_argument('--frame-request-fps', type=float, help='Selective default: 10; regular: uncapped')
    parser.add_argument('--max-source-age', type=float, default=1.0)
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--processing', choices=['regular', 'selective'], default='regular')
    parser.add_argument('--detection-fps', type=float, default=5.0)
    parser.add_argument('--refresh-seconds', type=float, default=0.4)
    parser.add_argument('--burst-seconds', type=float, default=3.0)
    parser.add_argument('--pixel-delta', type=float, default=12.0)
    parser.add_argument('--changed-fraction', type=float, default=0.002)
    parser.add_argument('--publication-tolerance-px', type=float, default=4.0)
    parser.add_argument('--heartbeat-seconds', type=float, default=0.5)
    parser.add_argument('--max-evidence-age', type=float, default=1.5)
    parser.add_argument('--publish-changes', action='store_true')
    parser.add_argument('--save-annotations', action='store_true')
    parser.add_argument('--max-captures', type=int)
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--preview', action='store_true', help='Main-thread OpenCV preview')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args(argv)
    preview = LivePreview() if args.preview else None
    try:
        if args.frame_request_fps is not None and not args.bridge_url:
            raise ValueError('Frame request rate requires --bridge-url')
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
            request_fps = args.frame_request_fps if args.frame_request_fps is not None else (10.0 if args.processing == "selective" else None)
            source = RemoteCamera(args.bridge_url, timeout=args.timeout,
                max_age_seconds=args.max_source_age, rotation=args.rotation, mirror=args.mirror,
                request_fps=request_fps)
            info = {'kind': 'remote_bridge', 'url': args.bridge_url,
                    'max_source_age_seconds': args.max_source_age, 'request_fps': request_fps}
        else:
            if args.replay_fps is not None or args.start_seconds:
                raise ValueError('Replay options require --replay')
            source = RobotCamera(args.camera, width=args.width, height=args.height,
                rotation=args.rotation, mirror=args.mirror, timeout=args.timeout)
            info = {'kind': 'local_camera', 'index': args.camera,
                    'requested_size': [args.width, args.height]}
        info.update({'rotation_clockwise': args.rotation, 'mirror_horizontal': args.mirror})
        print('OBSERVATION ONLY — no robot commands. Replay artifacts are simulation.', flush=True)
        policy = (DetectionPolicy(max_detection_fps=args.detection_fps,
            refresh_seconds=args.refresh_seconds, burst_seconds=args.burst_seconds,
            pixel_delta=args.pixel_delta, changed_fraction=args.changed_fraction)
            if args.processing == 'selective' else None)
        report = observe(source, args.output_dir, source_info=info,
            max_frames=args.max_frames, preview=preview, debug=args.debug,
            processing_policy=policy,
            annotations=args.processing == 'regular' or args.save_annotations or args.preview,
            publication=args.publish_changes or args.processing == 'selective',
            tolerance_px=args.publication_tolerance_px, heartbeat_seconds=args.heartbeat_seconds,
            max_evidence_age_seconds=args.max_evidence_age, max_capture_frames=args.max_captures)
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
