"""Record unannotated Pi-bridge frames on the PC without running detection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import cv2

from dmi_robot_master.integration.camera import RemoteCamera


def record(source: RemoteCamera, directory: Path, *, seconds: float = 30, playback_fps: float = 5,
           preview: bool = False) -> dict:
    """Own the source/writer and keep original frame dimensions and receipt times."""
    if not 0 < seconds < float('inf') or not 0 < playback_fps < float('inf'):
        raise ValueError('Duration and playback FPS must be finite and positive')
    directory.mkdir(parents=True, exist_ok=False)
    writer, last, frame_size = None, None, None
    started, first_receipt, count = time.monotonic(), None, 0
    reason, error = 'duration', None
    window = 'Raw camera — no detection (q to stop)'
    try:
        if preview:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window, 1152, 864)
        with source, (directory / 'processed_frames.jsonl').open('x') as stream:
            while time.monotonic() - started < seconds:
                try:
                    packet = source.read()
                except EOFError:
                    reason = 'source_exhausted'
                    break
                image = packet.image
                size = (image.shape[1], image.shape[0])
                if writer is None:
                    frame_size = size
                    writer = cv2.VideoWriter(str(directory / 'raw.mp4'),
                        cv2.VideoWriter_fourcc(*'mp4v'), playback_fps, size)
                    if not writer.isOpened():
                        raise RuntimeError('Could not open raw MP4 writer')
                    if not cv2.imwrite(str(directory / 'first_raw.png'), image):
                        raise RuntimeError('Could not save first unannotated frame')
                    first_receipt = packet.received_at
                elif size != frame_size:
                    raise RuntimeError('Camera frame size changed; start a new recording')
                writer.write(image)
                stream.write(json.dumps({'frame_index': count, 'capture_index': packet.capture_index,
                    'received_at_monotonic': packet.received_at,
                    'received_at_utc': packet.received_at_utc,
                    'elapsed_receipt_seconds': packet.received_at-first_receipt,
                    'remote_capture_age_seconds': getattr(packet, 'remote_capture_age_seconds', None),
                    'transport_round_trip_seconds': getattr(packet, 'transport_round_trip_seconds', None)})+'\n')
                last, count = image, count+1
                if preview:
                    cv2.imshow(window, image)
                    if cv2.waitKey(1) & 0xff in (ord('q'), 27):
                        reason = 'preview_closed'
                        break
    except KeyboardInterrupt:
        reason = 'interrupted'
    except Exception as exc:
        reason, error = 'error', str(exc)
        raise
    finally:
        if writer is not None:
            writer.release()
        if preview:
            cv2.destroyWindow(window)
        if last is not None and not cv2.imwrite(str(directory / 'last_raw.png'), last):
            error = error or 'Could not save final unannotated frame'
        if count == 0 and error is None:
            error = 'No frames received'
        if error is not None:
            reason = 'error'
        report = {'kind': 'unannotated_bridge_recording', 'source_url': getattr(source, 'url', None),
                  'frames': count,
                  'frame_size': frame_size, 'elapsed_seconds': time.monotonic()-started,
                  'playback_fps': playback_fps, 'stop_reason': reason, 'error': error,
                  'limits': 'Bridge JPEG and MP4 compression remain. No detection, annotation or robot commands. '
                            'Use receipt times for event timing; playback FPS is not measured capture FPS.'}
        (directory / 'session.json').write_text(json.dumps(report, indent=2)+'\n')
    if error is not None or count == 0:
        raise RuntimeError(error or 'No frames received')
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-url', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--request-fps', type=float, default=5)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args(argv)
    source = RemoteCamera(args.bridge_url, request_fps=args.request_fps)
    report = record(source, args.output_dir, seconds=args.seconds,
                    playback_fps=args.request_fps, preview=args.preview)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
