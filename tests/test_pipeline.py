from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dmi.pipeline import annotate_frame, process_frame  # noqa: E402


class ProcessFrameTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = np.zeros((160, 640, 3), dtype=np.uint8)

    def test_returns_output_contract(self) -> None:
        result = process_frame(self.frame, frame_index=12, timestamp=0.4)

        self.assertEqual(result["frame_index"], 12)
        self.assertEqual(result["timestamp"], 0.4)
        self.assertEqual(
            result["right_display"],
            {
                "geometry": None,
                "state": "unknown",
                "title": None,
                "buttons": {},
                "data_field": None,
            },
        )
        self.assertEqual(
            result["left_display"],
            {"geometry": None, "boxes": {}, "speed_indicator": None},
        )

    def test_annotation_is_a_modified_copy(self) -> None:
        result = process_frame(self.frame, frame_index=0, timestamp=0.0)
        annotated = annotate_frame(self.frame, result)

        self.assertIsNot(annotated, self.frame)
        self.assertEqual(annotated.shape, self.frame.shape)
        self.assertFalse(np.any(self.frame))
        self.assertTrue(np.any(annotated))

    def test_rejects_invalid_frame_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "three-channel BGR"):
            process_frame(np.zeros((20, 20), dtype=np.uint8), 0, 0.0)

    def test_rejects_negative_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "frame_index"):
            process_frame(self.frame, -1, 0.0)
        with self.assertRaisesRegex(ValueError, "timestamp"):
            process_frame(self.frame, 0, -0.1)


if __name__ == "__main__":
    unittest.main()
