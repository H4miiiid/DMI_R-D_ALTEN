from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.video import process_video  # noqa: E402


class ProcessVideoTest(unittest.TestCase):
    def test_processes_synthetic_video_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp4"
            self._write_test_video(source)

            summary = process_video(source, root / "output")

            self.assertEqual(summary.processed_frames, 6)
            self.assertEqual(summary.frame_size, (640, 160))
            self.assertTrue(summary.json_path.is_file())
            self.assertTrue(summary.annotated_video_path.is_file())

            payload = json.loads(summary.json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["video"], "source.mp4")
            self.assertEqual(len(payload["frames"]), 6)
            self.assertEqual(payload["frames"][5]["timestamp"], 0.5)

            capture = cv2.VideoCapture(str(summary.annotated_video_path))
            decoded_frames = 0
            while capture.read()[0]:
                decoded_frames += 1
            capture.release()
            self.assertEqual(decoded_frames, 6)

    def test_refuses_to_overwrite_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp4"
            self._write_test_video(source)
            process_video(source, root / "output", max_frames=1)

            with self.assertRaises(FileExistsError):
                process_video(source, root / "output", max_frames=1)

    @staticmethod
    def _write_test_video(path: Path) -> None:
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (640, 160)
        )
        if not writer.isOpened():
            raise RuntimeError("test environment cannot create MP4 videos")
        for index in range(6):
            frame = np.full((160, 640, 3), index * 20, dtype=np.uint8)
            writer.write(frame)
        writer.release()


if __name__ == "__main__":
    unittest.main()
