"""Output-contract and regression tests independent of reference recordings."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import tempfile
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dmi_computer_vision.src.dmi.detection.display_geometry import DisplayGeometry
from dmi_computer_vision.src.dmi.pipeline.frame_processor import process_frame
from dmi_computer_vision.src.dmi.evaluation.validation import validate_results, compare_frames, compare_annotated_videos


def region():
    return {'corners': [[10, 10], [50, 10], [50, 50], [10, 50]],
            'bbox': [10, 10, 50, 50], 'center': [30, 30]}


def frame():
    geom = {**region(), 'oriented_box': region()['corners']}
    return {'frame_index': 0, 'timestamp': 0.,
            'right_display': {'geometry': geom, 'visibility': 'clear',
                              'state': 'Driver ID', 'title': {**region(), 'text': 'Driver ID'},
                              'buttons': {'digit_1': region()},
                              'data_field': {**region(), 'value': '12'}},
            'left_display': {'geometry': deepcopy(geom),
                             'boxes': {'box_1': {**region(), 'icon': None}},
                             'speed_indicator': None}}


class ValidationTest(unittest.TestCase):
    def test_checks_both_displays_without_mutating_results(self):
        frames = [frame()];original = deepcopy(frames)
        counts = validate_results(frames, 30)
        self.assertEqual(counts['display_geometries'], 2)
        self.assertEqual(counts['right_regions'], 3)
        self.assertEqual(frames, original)

    def test_icon_identity_uses_available_assets(self):
        result = frame()
        result['left_display']['boxes']['box_1']['icon'] = 'power'
        self.assertEqual(validate_results([result], 30)['left_regions'], 1)

    def test_rejects_metadata_type_timing_and_geometry_errors(self):
        mutations = [
            lambda f: f.update(frame_index=1),
            lambda f: f.update(frame_index=False),
            lambda f: f.update(timestamp=float('nan')),
            lambda f: f.update(timestamp=.5),
            lambda f: f['right_display']['title'].update(text=12),
            lambda f: f['right_display']['buttons']['digit_1'].update(bbox=[20,20,30,30]),
            lambda f: f['right_display']['buttons']['digit_1'].update(center=[90,90]),
            lambda f: f['left_display']['boxes']['box_1'].update(icon='invented_icon'),
            lambda f: f['left_display']['boxes']['box_1'].update(corners=[[0,0]]*4),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                result = frame();mutate(result)
                with self.assertRaises(ValueError):validate_results([result], 30)

    def test_missing_or_occluded_display_cannot_retain_old_content(self):
        for side in ['left_display', 'right_display']:
            result = frame();result[side]['geometry'] = None
            with self.assertRaises(ValueError):validate_results([result], 30)
        result = frame();result['right_display']['visibility'] = 'occluded'
        with self.assertRaises(ValueError):validate_results([result], 30)
        result['right_display'].update(state='unknown', title=None, buttons={}, data_field=None)
        self.assertEqual(validate_results([result], 30)['occluded_frames'], 1)

    def test_serialized_bounds_cover_fitted_outlines_not_internal_mask_box(self):
        q = np.array(region()['corners'], np.float32)
        oriented = q + np.array([-3, 4], np.float32)
        geometry = DisplayGeometry(q, oriented, (12,12,48,48))
        self.assertEqual(geometry.as_result()['bbox'], [7,10,50,54])
        self.assertEqual(geometry.bbox, (12,12,48,48))

    def test_comparison_only_exempts_exact_outline_bound_correction(self):
        with self.assertRaisesRegex(ValueError, "frame count mismatch"):
            compare_frames([frame()], [])
        baseline = frame();baseline['right_display']['geometry']['bbox'] = [11,11,49,49]
        current = frame()
        self.assertEqual(compare_frames([current], [baseline])['display_bbox_only_frames'], [0])
        current['right_display']['buttons']['digit_1']['center'] = [31,30]
        self.assertEqual(compare_frames([current], [baseline])['other_changed_frames'], [0])

    def test_annotation_comparison_detects_visual_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ('first.mp4', 'second.mp4')]
            for path, value in zip(paths, [0, 100]):
                writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (80, 60))
                self.assertTrue(writer.isOpened())
                writer.write(np.full((60, 80, 3), value, np.uint8));writer.release()
            self.assertEqual(compare_annotated_videos(paths[0], paths[0])['changed_frames'], [])
            self.assertEqual(compare_annotated_videos(*paths)['changed_frames'], [0])
            self.assertIsNone(compare_annotated_videos(paths[0], Path(directory) / 'absent.mp4'))

    def test_core_rejects_nonfinite_time_and_fractional_index(self):
        image = np.zeros((30, 40, 3), np.uint8)
        for index, timestamp in [(1.5,0), (False,0), (0,float('inf')), (0,float('nan'))]:
            with self.assertRaises(ValueError):process_frame(image, index, timestamp)


if __name__ == '__main__':unittest.main()
