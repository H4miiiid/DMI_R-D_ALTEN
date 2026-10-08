"""Calibration fitting/conversion/expiry checks; synthetic data only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from dmi_computer_vision.tests.test_validation import frame as detected_frame
from dmi_robot_master.integration.calibration import (
    KEYS, KeypadObservations, _identifier, convert_pixel, fit_calibration,
    read_json, recheck_keypad, reference_points, save_calibration, load_calibration,
    transform_point, validate_calibration,
)
from dmi_robot_master.integration.calibrate import calibrate_replay


CAMERA = {'identity': 'synthetic-camera', 'source_kind': 'synthetic',
          'mount_id': 'simulation-fixed-1',
          'settings': {'rotation_clockwise': 0, 'mirror_horizontal': False, 'crop': None}}
ORIGIN = {'identity': 'synthetic-origin', 'axes': '+X right, +Y up (simulation)'}
SIZE = (2000, 1500)
# Known perspective distortion for meaningful homography testing.
MM_TO_PIXEL = np.array([[3, .2, 120], [.1, -2, 1000], [.0004, .0001, 1]])


def points():
    reference, _ = reference_points()
    return {key: transform_point(MM_TO_PIXEL, xy) for key, xy in reference.items()}


def fit(centers=None, **kwargs):
    return fit_calibration(centers or points(), frame_size=SIZE, camera=CAMERA,
        origin=ORIGIN, ransac_threshold_mm=.5, tolerance_mm=.1,
        tolerance_basis='Synthetic test only', **kwargs)


def record(index, centers=None):
    result = detected_frame()
    result['right_display']['buttons'] = {
        f'digit_{key[-1]}': {'center': xy} for key, xy in (centers or points()).items()}
    return {'type': 'frame', 'capture_index': index, 'frame_size': list(SIZE),
            'temporal_reset': None, 'result': result}


class CalibrationMathTests(unittest.TestCase):
    def test_identity_matching_with_shuffled_input_and_independent_errors(self):
        centers = dict(reversed(list(points().items())))
        calibration = fit(centers)
        self.assertEqual([p['label'] for p in calibration['matched_points']], list(KEYS))
        self.assertEqual(calibration['validation']['method'], 'leave_one_key_out')
        self.assertEqual(len(calibration['validation']['per_key_error_mm']), 10)
        self.assertLess(calibration['validation']['max_error_mm'], .001)
        reference, _ = reference_points()
        for key, pixel in centers.items():
            actual = convert_pixel(calibration, pixel, frame_size=SIZE, camera=CAMERA, origin=ORIGIN)
            np.testing.assert_allclose(actual, reference[key], atol=.001)

    def test_held_out_error_does_not_hide_noisy_key(self):
        centers = points()
        centers['KEY_5'] = [centers['KEY_5'][0] + .4, centers['KEY_5'][1]]
        calibration = fit(centers)
        error = calibration['validation']['per_key_error_mm']['KEY_5']
        training = calibration['validation']['training_error_mm']['KEY_5']
        self.assertGreater(error, training)
        self.assertFalse(calibration['validation']['accepted'])
        with self.assertRaisesRegex(ValueError, 'accepted'):
            validate_calibration(calibration, frame_size=SIZE, camera=CAMERA, origin=ORIGIN)

    def test_missing_degenerate_duplicate_and_outlier_fits_rejected(self):
        bad = [dict(list(points().items())[:4]),
               {key: [10 + i, 20] for i, key in enumerate(KEYS)},
               {key: [100, 100] for key in KEYS}]
        swapped = points()
        swapped['KEY_1'], swapped['KEY_9'] = swapped['KEY_9'], swapped['KEY_1']
        bad.append(swapped)
        for centers in bad:
            with self.subTest(centers=centers), self.assertRaises(ValueError):
                fit(centers)

    def test_homogeneous_division_and_nonfinite_values(self):
        np.testing.assert_allclose(transform_point(2*np.eye(3), [1, 2]), [1, 2])
        for matrix in [np.zeros((3, 3)), np.full((3, 3), np.nan),
                       [[1, 0, 0], [0, 1, 0], [1, 0, -1]]]:
            with self.assertRaises(ValueError):
                transform_point(matrix, [1, 2])
        with self.assertRaises(ValueError):
            transform_point(np.eye(3), [np.inf, 1])

    def test_plane_and_validated_area_limit_conversion(self):
        calibration = fit()
        for options in [{'display': 'left'}, {'screen': 'Main'}]:
            with self.assertRaises(ValueError):
                convert_pixel(calibration, points()['KEY_1'], frame_size=SIZE,
                              camera=CAMERA, origin=ORIGIN, **options)
        with self.assertRaisesRegex(ValueError, 'outside'):
            convert_pixel(calibration, [10, 10], frame_size=SIZE, camera=CAMERA, origin=ORIGIN)

    def test_simulation_and_unverified_hardware_are_rejected_for_execution(self):
        calibration = fit()
        with self.assertRaisesRegex(ValueError, 'Hardware execution'):
            convert_pixel(calibration, points()['KEY_1'], frame_size=SIZE,
                          camera=CAMERA, origin=ORIGIN, hardware=True)
        with self.assertRaisesRegex(ValueError, 'Recorded/synthetic'):
            fit(provenance='hardware')
        camera = deepcopy(CAMERA)
        camera['source_kind'] = 'local_camera'
        hardware = fit_calibration(points(), frame_size=SIZE, camera=camera, origin=ORIGIN,
            ransac_threshold_mm=.5, tolerance_mm=.1, tolerance_basis='Test only', provenance='hardware')
        self.assertFalse(hardware['validation']['hardware_verified'])
        with self.assertRaisesRegex(ValueError, 'unverified'):
            validate_calibration(hardware, frame_size=SIZE, camera=camera, origin=ORIGIN, hardware=True)

    def test_setup_hash_origin_mount_and_content_invalidation(self):
        calibration = fit()
        changed_camera = deepcopy(CAMERA)
        changed_camera['mount_id'] = 'moved'
        rotated = deepcopy(CAMERA)
        rotated['settings']['rotation_clockwise'] = 90
        for size, camera, origin in [(SIZE, changed_camera, ORIGIN), (SIZE, rotated, ORIGIN),
                                    ((1000, 750), CAMERA, ORIGIN),
                                    (SIZE, CAMERA, {'identity': 'new origin', 'axes': 'changed'})]:
            with self.assertRaises(ValueError):
                validate_calibration(calibration, frame_size=size, camera=camera, origin=origin)
        changed = deepcopy(calibration)
        changed['homography'][0][0] += 1
        with self.assertRaisesRegex(ValueError, 'identifier'):
            validate_calibration(changed, frame_size=SIZE, camera=CAMERA, origin=ORIGIN)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'reference.json'
            from dmi_robot_master.integration.calibration import REFERENCE_PATH
            path.write_bytes(REFERENCE_PATH.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Reference'):
                validate_calibration(calibration, frame_size=SIZE, camera=CAMERA,
                                     origin=ORIGIN, reference_path=path)

    def test_no_tolerance_no_acceptance_and_keypad_recheck(self):
        calibration = fit_calibration(points(), frame_size=SIZE, camera=CAMERA,
            origin=ORIGIN, ransac_threshold_mm=.5)
        self.assertFalse(calibration['validation']['accepted'])
        with self.assertRaises(ValueError):
            validate_calibration(calibration, frame_size=SIZE, camera=CAMERA, origin=ORIGIN)
        recheck_keypad(fit(), points(), tolerance_px=1)
        shifted = {key: [xy[0] + 2, xy[1]] for key, xy in points().items()}
        with self.assertRaisesRegex(ValueError, 'recheck failed'):
            recheck_keypad(fit(), shifted, tolerance_px=1)

    def test_malformed_and_reidentified_invalid_artifacts_are_rejected(self):
        calibration = fit()
        invalid = []
        missing = deepcopy(calibration)
        del missing['matched_points']
        invalid.append(missing)
        exaggerated_area = deepcopy(calibration)
        exaggerated_area['validated_area_pixels'] = [[0, 0], [1900, 0], [1900, 1400], [0, 1400]]
        invalid.append(exaggerated_area)
        false_errors = deepcopy(calibration)
        false_errors['validation']['per_key_error_mm']['KEY_1'] = 0.08
        invalid.append(false_errors)
        wrong_matrix = deepcopy(calibration)
        wrong_matrix['homography'][0][2] += 1
        invalid.append(wrong_matrix)
        wrong_reference = deepcopy(calibration)
        wrong_reference['matched_points'][0]['mm'][0] += 1
        invalid.append(wrong_reference)
        for document in invalid:
            document['calibration_id'] = _identifier(document)
            with self.subTest(document=document), self.assertRaises(ValueError):
                validate_calibration(document, frame_size=SIZE, camera=CAMERA, origin=ORIGIN)

    def test_observation_size_change_reset_and_bounds(self):
        collector = KeypadObservations(SIZE, observations=3, max_spread_px=1)
        collector.add(record(0))
        reset = record(1)
        reset['temporal_reset'] = 'capture_gap'
        collector.add(reset)
        self.assertEqual(len(collector.samples), 1)
        outside = points()
        outside['KEY_1'] = [SIZE[0], 20]
        self.assertFalse(collector.add(record(2, outside)))
        changed_size = record(3)
        changed_size['frame_size'] = [1000, 750]
        with self.assertRaisesRegex(ValueError, 'size changed'):
            collector.add(changed_size)

    def test_json_roundtrip_no_overwrite_and_duplicate_keys(self):
        calibration = fit()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'calibration.json'
            save_calibration(calibration, path)
            self.assertEqual(read_json(path), calibration)
            self.assertEqual(load_calibration(path, frame_size=SIZE, camera=CAMERA, origin=ORIGIN), calibration)
            validate_calibration(read_json(path), frame_size=SIZE, camera=CAMERA, origin=ORIGIN)
            with self.assertRaises(FileExistsError):
                save_calibration(calibration, path)
            path.write_text('{"KEY_1":1,"KEY_1":2}')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                read_json(path)


class ObservationTests(unittest.TestCase):
    def collector(self):
        return KeypadObservations(SIZE, observations=3, max_spread_px=1)

    def test_complete_stable_observations_are_summarized_by_identity_median(self):
        collector = self.collector()
        for i, offset in enumerate([0, .1, -.1]):
            centers = {key: [xy[0]+offset, xy[1]] for key, xy in points().items()}
            self.assertTrue(collector.add(record(i, centers)))
        self.assertEqual(collector.summarize(), points())
        with self.assertRaises(ValueError):
            collector.add(record(2))

    def test_missing_ambiguous_unknown_and_unstable_observations_clear_run(self):
        bad_records = []
        missing = record(1); del missing['result']['right_display']['buttons']['digit_0']
        bad_records.append(missing)
        unknown = record(1); unknown['result']['right_display']['state'] = 'unknown'
        bad_records.append(unknown)
        duplicate = points(); duplicate['KEY_1'] = duplicate['KEY_2']
        bad_records.append(record(1, duplicate))
        unstable = points(); unstable['KEY_1'][0] += 10
        bad_records.append(record(1, unstable))
        for bad in bad_records:
            with self.subTest(bad=bad):
                collector = self.collector(); collector.add(record(0))
                self.assertFalse(collector.add(bad))
                with self.assertRaises(ValueError):
                    collector.summarize()

    def test_replay_cli_always_simulation_and_rejects_non_simulation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory/'session.json').write_text(json.dumps({'simulation':True,'error':None,
                                                            'source':{'kind':'recorded_replay','path':'synthetic.mp4'}}))
            (directory/'results_debug.jsonl').write_text(''.join(json.dumps(record(i))+'\n' for i in range(3)))
            output = directory/'calibration.json'
            report = calibrate_replay(directory, output, observations=3, max_spread_px=1,
                                     ransac_threshold_mm=.5, simulation_tolerance_mm=.1)
            self.assertEqual(report['calibration']['provenance'], 'simulation')
            self.assertEqual(report['accepted_observations'], 3)
            (directory/'session.json').write_text(json.dumps({'simulation':False}))
            with self.assertRaisesRegex(ValueError, 'simulated'):
                calibrate_replay(directory, directory/'bad.json', observations=3,
                                 max_spread_px=1, ransac_threshold_mm=.5)


if __name__ == '__main__':
    unittest.main()
