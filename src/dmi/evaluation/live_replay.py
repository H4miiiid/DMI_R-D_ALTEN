"""Replay a recording through the live consumer; this is not camera validation.

Frames are supplied sequentially on demand with monotonic receipt timestamps.
This checks identical detections for identical frames, not camera-rate sampling.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import cv2

from dmi.io.camera import CapturedFrame
from dmi.pipeline.live import process_live
from dmi.evaluation.validation import validate_results


class RecordedReplay:
    def __init__(self, capture):
        self.capture = capture
        self.index = 0

    def read(self):
        ok, image = self.capture.read()
        if not ok:
            raise RuntimeError("recorded replay ended before the baseline frame count")
        packet = CapturedFrame(image, self.index, time.monotonic())
        self.index += 1
        return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_video", type=Path)
    parser.add_argument("--baseline", required=True, type=Path, help="approved results.json")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    if baseline['video'] != args.input_video.name:
        raise ValueError("baseline source filename differs from replay input")
    capture = cv2.VideoCapture(str(args.input_video))
    try:
        if not capture.isOpened():
            raise RuntimeError(f"could not open replay input: {args.input_video}")
        run = process_live(RecordedReplay(capture), args.output_dir,
                           source_info={"kind": "recorded_replay", "video": args.input_video.name},
                           max_frames=len(baseline['frames']))
        if capture.read()[0]:
            raise RuntimeError("replay source has more frames than the baseline")
    finally:
        capture.release()
    records = [json.loads(line) for line in run.jsonl_path.read_text().splitlines()]
    frames = [r['result'] for r in records if r['type'] == 'frame']
    changes = [i for i, (frame, old) in enumerate(zip(frames, baseline['frames']))
               if {k: v for k, v in frame.items() if k != 'timestamp'} !=
                  {k: v for k, v in old.items() if k != 'timestamp'}]
    report = {**asdict(run), 'evidence': 'sequential recorded replay, not physical webcam',
              'contract': validate_results(frames, None),
              'changed_frames_excluding_timestamp': changes,
              'processed_fps': run.processed_frames / run.elapsed_seconds,
              'mean_processing_ms': 1000 * run.processing_seconds / run.processed_frames}
    (args.output_dir / 'verification.json').write_text(json.dumps(report, default=str, indent=2) + '\n')
    print(f"Replayed {len(frames)} frames; {len(changes)} changed detections; "
          f"{report['processed_fps']:.2f} processed FPS")
    if changes:
        raise RuntimeError("replay differs from approved detections; inspect verification.json")
