"""Pi observation-only JPEG bridge: one source owner and one recent frame.

Run only on the camera host. No robot GPIO/controller is imported.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
import time
import uuid
import logging

import cv2

from dmi_robot_master.integration.camera import RobotCamera


class FrameBridge:
    def __init__(self, source: RobotCamera, max_age_seconds: float = 1.0) -> None:
        if not 0 < max_age_seconds < float('inf'):
            raise ValueError('Frame age limit must be finite and positive')
        self.session_id = uuid.uuid4().hex
        self.source = source
        self.max_age_seconds = max_age_seconds
        self._lock, self._stop = Lock(), Event()
        self._latest = None
        self.error = None
        self.thread = None

    def __enter__(self):
        self.source.__enter__()
        self.thread = Thread(target=self._publish, name='dmi-jpeg-bridge', daemon=True)
        self.thread.start()
        return self

    def _publish(self) -> None:
        try:
            while not self._stop.is_set():
                packet = self.source.read()
                ok, encoded = cv2.imencode('.jpg', packet.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if not ok:
                    raise RuntimeError('JPEG encoding failed')
                with self._lock:
                    self._latest = (packet.capture_index, packet.received_at, encoded.tobytes())
        except Exception as exc:
            with self._lock:
                if not self._stop.is_set():
                    self.error = str(exc)
                    logging.error("Camera bridge failed: %s", exc)
                self._latest = None

    def get(self):
        with self._lock:
            if self.error is not None:
                raise RuntimeError(self.error)
            if self._latest is None:
                return None
            index, received, data = self._latest
            age = time.monotonic() - received
            if age < 0 or age > self.max_age_seconds:
                return None
            return index, age, data

    def __exit__(self, *args):
        self._stop.set()
        self.source.__exit__(*args)
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise RuntimeError('Bridge acquisition is blocked; exit process to release camera')
        with self._lock:
            self._latest = None


def handler_for(bridge: FrameBridge):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/frame.jpg':
                self.send_error(404)
                return
            try:
                snapshot = bridge.get()
            except RuntimeError:
                self.send_error(503, 'Camera failed')
                return
            if snapshot is None:
                self.send_error(503, 'No fresh camera frame')
                return
            index, age, data = snapshot
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Camera-Session', bridge.session_id)
            self.send_header('X-Capture-Index', str(index))
            self.send_header('X-Capture-Age-Seconds', str(age))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Consumer left; this handler owns no camera.

        def log_message(self, *args):
            pass
    return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True, help='Camera-host interface address')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--camera', type=int, required=True)
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    parser.add_argument('--max-age-seconds', type=float, default=1.0)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1..65535')
    source = RobotCamera(args.camera, width=args.width, height=args.height)
    with FrameBridge(source, args.max_age_seconds) as bridge:
        with ThreadingHTTPServer((args.bind, args.port), handler_for(bridge)) as server:
            server.daemon_threads = True
            print(json.dumps({'mode': 'observation only', 'endpoint': '/frame.jpg',
                              'camera': args.camera, 'bind': args.bind, 'port': args.port}), flush=True)
            try:
                server.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
