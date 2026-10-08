"""Fit a simulation calibration from a Phase 2 replay observation directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dmi_robot_master.integration.calibration import (
    KeypadObservations, REFERENCE_PATH, fit_calibration, read_json, save_calibration,
    unique_object,
)


def calibrate_replay(directory: str | Path, output: str | Path, *, observations: int,
                     max_spread_px: float, ransac_threshold_mm: float,
                     simulation_tolerance_mm: float | None = None,
                     reference_path: str | Path = REFERENCE_PATH) -> dict:
    """Only replay/fake-source simulation; this CLI cannot mark a hardware fit."""
    directory = Path(directory).expanduser().resolve()
    session = read_json(directory / 'session.json')
    if session.get('simulation') is not True or session.get('error') is not None:
        raise ValueError('Use a successful explicitly simulated observation session')
    collector = None
    accepted_indices = []
    with (directory / 'results_debug.jsonl').open() as stream:
        for line in stream:
            record = json.loads(line, object_pairs_hook=unique_object)
            if record.get('type') != 'frame':
                continue
            if collector is None:
                collector = KeypadObservations(tuple(record['frame_size']),
                    observations=observations, max_spread_px=max_spread_px)
            if collector.add(record):
                accepted_indices = (accepted_indices + [record['capture_index']])[-observations:]
            else:
                accepted_indices.clear()
            if len(collector.samples) == observations:
                break
    if collector is None:
        raise ValueError('No debug frames; run observation with --debug')
    centers = collector.summarize()
    source = session['source']
    camera = {'identity': 'simulation:' + str(source.get('path', directory)),
              'source_kind': 'recorded_replay', 'mount_id': 'simulation-unverified-mount',
              'settings': {'rotation_clockwise': source.get('rotation_clockwise', 0),
                           'mirror_horizontal': source.get('mirror_horizontal', False),
                           'crop': None, 'frame_size': list(collector.frame_size)}}
    origin = {'identity': 'simulation:stored-reference',
              'axes': 'Reference +X KEY_1 toward KEY_3; +Y KEY_0 toward KEY_2; physical origin unverified'}
    document = fit_calibration(centers, frame_size=collector.frame_size,
        camera=camera, origin=origin, ransac_threshold_mm=ransac_threshold_mm,
        tolerance_mm=simulation_tolerance_mm,
        tolerance_basis=('Explicit development-example tolerance; not a physical acceptance tolerance'
                         if simulation_tolerance_mm is not None else None),
        observation_summary={"count": len(collector.samples),
                             "capture_indices": accepted_indices,
                             "max_spread_px": max_spread_px,
                             "evidence": "stabilized detector output from simulation replay"},
        reference_path=reference_path)
    save_calibration(document, output)
    return {'calibration': document, 'observation_capture_indices': accepted_indices,
            'accepted_observations': len(collector.samples),
            'rejected_observations': collector.rejected, 'max_spread_px': max_spread_px}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--observations', type=int, default=5)
    parser.add_argument('--max-spread-px', type=float, required=True)
    parser.add_argument('--ransac-threshold-mm', type=float, required=True)
    parser.add_argument('--simulation-tolerance-mm', type=float)
    args = parser.parse_args(argv)
    try:
        result = calibrate_replay(args.observation_dir, args.output,
            observations=args.observations, max_spread_px=args.max_spread_px,
            ransac_threshold_mm=args.ransac_threshold_mm,
            simulation_tolerance_mm=args.simulation_tolerance_mm)
        document = result['calibration']
        print('SIMULATION ONLY — not usable by physical robot execution.')
        print(json.dumps({k: v for k, v in result.items() if k != 'calibration'}, indent=2))
        print(json.dumps(document['validation'], indent=2))
        print(f"Calibration {document['calibration_id']} saved to {args.output}")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
