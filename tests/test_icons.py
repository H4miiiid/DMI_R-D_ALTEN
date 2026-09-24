"""Asset-derived synthetic cases; video predictions are not ground truth."""
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi.icons import ASSET_DIRECTORY, recognize_icons


class IconRecognitionTest(unittest.TestCase):
    def scene(self, name, scale=2, exposure=1, blur=0):
        image = np.full((180, 360, 3), (34, 17, 3), np.uint8)
        icon = cv2.imread(str(ASSET_DIRECTORY / f"{name}.bmp"))
        icon = cv2.resize(icon, None, fx=scale, fy=scale)
        h, w = icon.shape[:2]
        image[55:55+h, 65:65+w] = icon
        if blur:
            image = cv2.GaussianBlur(image, (0, 0), blur)
        image = np.clip(image.astype(float) * exposure, 0, 255).astype(np.uint8)
        boxes = {"arbitrary_box": np.array([[20, 20], [250, 20], [250, 150], [20, 150]], np.float32)}
        return image, boxes

    def test_assets_at_multiple_scales_exposures_and_blur(self):
        for name in ("level0_icon", "level1_icon", "level2_icon"):
            for scale, exposure, blur in ((1, 1, 0), (1.5, .65, .5), (2, 1.2, 1), (2.5, 1, .7)):
                with self.subTest(name=name, scale=scale):
                    image, boxes = self.scene(name, scale, exposure, blur)
                    self.assertEqual(recognize_icons(image, boxes)["arbitrary_box"], name)

    def test_local_perspective_and_box_association(self):
        image, boxes = self.scene("level1_icon")
        source = np.array([[0, 0], [359, 0], [359, 179], [0, 179]], np.float32)
        target = np.array([[12, 5], [345, 20], [350, 175], [0, 160]], np.float32)
        transform = cv2.getPerspectiveTransform(source, target)
        warped = cv2.warpPerspective(image, transform, (360, 180))
        boxes = {k: cv2.perspectiveTransform(v[None], transform)[0] for k, v in boxes.items()}
        boxes["empty_neighbor"] = np.array([[260, 35], [330, 35], [330, 130], [260, 130]], np.float32)
        self.assertEqual(recognize_icons(warped, boxes), {"arbitrary_box": "level1_icon", "empty_neighbor": None})

    def test_empty_unknown_and_partial_symbols_abstain(self):
        _, boxes = self.scene("level0_icon")
        for symbol in ("blank", "circle", "triangle", "bar", "digit", "noise"):
            image = np.full((180, 360, 3), (34, 17, 3), np.uint8)
            if symbol == "circle": cv2.circle(image, (110, 80), 22, (220, 220, 220), 5)
            if symbol == "triangle": cv2.fillPoly(image, [np.array([[70, 100], [120, 50], [160, 100]])], (210, 240, 190))
            if symbol == "bar": cv2.rectangle(image, (60, 80), (170, 100), (220, 220, 220), -1)
            if symbol == "digit": cv2.putText(image, "2", (100, 90), 0, 1, (220, 220, 220), 2)
            if symbol == "noise": image = np.random.default_rng(7).integers(0, 256, image.shape, dtype=np.uint8)
            with self.subTest(symbol=symbol):
                self.assertIsNone(recognize_icons(image, boxes)["arbitrary_box"])

    def test_multiple_boxes_and_ambiguous_multiplicity(self):
        image, boxes = self.scene("level0_icon")
        second, _ = self.scene("level2_icon")
        combined = np.hstack((image, second))
        boxes["second_box"] = boxes["arbitrary_box"] + (360, 0)
        self.assertEqual(recognize_icons(combined, boxes),
                         {"arbitrary_box": "level0_icon", "second_box": "level2_icon"})
        whole = np.array([[0, 0], [719, 0], [719, 179], [0, 179]], np.float32)
        self.assertIsNone(recognize_icons(combined, {"whole": whole})["whole"])

    def test_annotation_uses_structured_icon_identity(self):
        from unittest.mock import patch
        from dmi.pipeline import _draw_left_content
        image, boxes = self.scene("level1_icon")
        region = {"corners": boxes["arbitrary_box"].tolist(),
                  "center": [135, 85], "icon": "level1_icon"}
        with patch("dmi.pipeline.cv2.putText", wraps=cv2.putText) as draw:
            _draw_left_content(image, {"boxes": {"arbitrary_box": region},
                                       "speed_indicator": None})
        self.assertTrue(draw.call_args_list)
        self.assertTrue(all(call.args[1] == "arbitrary_box: level1_icon"
                            for call in draw.call_args_list))

    def test_no_history_can_preserve_or_delay_an_icon(self):
        for name in ("level0_icon", "level2_icon", "level1_icon"):
            image, boxes = self.scene(name)
            self.assertEqual(recognize_icons(image, boxes)["arbitrary_box"], name)
            image[:] = (34, 17, 3)
            self.assertIsNone(recognize_icons(image, boxes)["arbitrary_box"])
        self.assertEqual(recognize_icons(image, {}), {})


if __name__ == "__main__":
    unittest.main()
