from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.video import process_video  # noqa: E402

spec = importlib.util.spec_from_file_location("run_video", REPOSITORY_ROOT / "scripts/run_video.py")
run_video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_video)


class ProcessVideoTest(unittest.TestCase):
    def test_path_only_cli_creates_named_outputs_and_preserves_other_runs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.object(run_video, "REPOSITORY_ROOT", root):
                for name in ("first input", "second"):
                    source = root / f"{name}.mp4"
                    self._write_test_video(source)
                    with patch.object(sys, "argv", ["run_video.py", str(source)]):
                        self.assertEqual(run_video.main(), 0)
                    output = root / "outputs"
                    payload = json.loads((output / f"{name}.json").read_text())
                    self.assertEqual(payload["video"], source.name)
                    self.assertEqual(len(payload["frames"]), 6)
                    capture = cv2.VideoCapture(str(output / f"{name}_annotated.mp4"))
                    count = 0
                    while capture.read()[0]:
                        count += 1
                    capture.release()
                    self.assertEqual(count, 6)
                before = {p.name: p.read_bytes() for p in output.iterdir()}
                with patch.object(sys, "argv", ["run_video.py", str(source)]):
                    self.assertEqual(run_video.main(), 1)
                self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)
                with patch.object(sys, "argv", ["run_video.py", str(source), "--overwrite"]):
                    self.assertEqual(run_video.main(), 0)
                self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)

    def test_cli_custom_output_directory_and_missing_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp4"
            output = root / "nested" / "custom"
            args = ["run_video.py", str(source), "--output-dir", str(output)]
            with patch.object(sys, "argv", args):
                self.assertEqual(run_video.main(), 1)
            self.assertFalse(output.exists())
            self._write_test_video(source)
            with patch.object(sys, "argv", args):
                self.assertEqual(run_video.main(), 0)
            self.assertEqual({p.name for p in output.iterdir()},
                             {"source.json", "source_annotated.mp4"})

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

    def test_failed_processing_preserves_previous_outputs_and_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp4"
            self._write_test_video(source)
            directory = root / "output"
            process_video(source, directory, max_frames=1)
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            with patch("dmi.video.process_frame", side_effect=RuntimeError("injected failure")):
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    process_video(source, directory, overwrite=True)
            self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, before)

    def test_rejects_fractional_and_boolean_frame_limits(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory);source = root / "source.mp4"
            self._write_test_video(source)
            for limit in [0, -1, 2.5, True]:
                with self.assertRaises(ValueError):
                    process_video(source, root / "output", max_frames=limit)
            self.assertFalse((root / "output").exists())

    def test_nonfinite_json_is_not_published(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory);source = root / "source.mp4"
            self._write_test_video(source)
            with patch("dmi.video.process_frame", return_value={"timestamp": float('nan')}), \
                    patch("dmi.video.annotate_frame", side_effect=lambda image, _: image):
                with self.assertRaises(ValueError):
                    process_video(source, root / "output")
            self.assertEqual(list((root / "output").iterdir()), [])

    def test_source_frame_count_is_informational_and_nonfinite_fps_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory);source = root / "source.mp4"
            self._write_test_video(source)
            for fps in [float('nan'), 10.]:
                with self.subTest(fps=fps):
                    capture = cv2.VideoCapture(str(source))
                    actual_get = capture.get
                    def properties(key):
                        if key == cv2.CAP_PROP_FPS:return fps
                        if key == cv2.CAP_PROP_FRAME_COUNT:return 7
                        return actual_get(key)
                    with patch("dmi.video.cv2.VideoCapture") as factory:
                        factory.return_value.isOpened.return_value = True
                        factory.return_value.get.side_effect = properties
                        factory.return_value.read.side_effect = capture.read
                        if not np.isfinite(fps):
                            with self.assertRaises(RuntimeError):
                                process_video(source, root / "output")
                            self.assertEqual(list((root / "output").iterdir()), [])
                        else:
                            run = process_video(source, root / "output")
                            self.assertEqual(run.processed_frames, 6)
                            self.assertEqual(run.declared_frames, 7)
                    capture.release()

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
