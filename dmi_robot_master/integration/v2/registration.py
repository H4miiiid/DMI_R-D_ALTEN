"""Version 2 registration calculations over detached measurements.

The existing RecordedTestProjector owns state, locks, epochs and commits. These
functions create no cache and cannot admit observations or authorize an action.
"""
from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from dmi_robot_master.integration.shared.projection.recorded_test import RecordedTestProjector


def recovery_aligned_geometry(a: dict, b: dict) -> bool:
    """The existing fixed-setup experimental 20-native-pixel comparison."""
    return all(np.max(np.abs(np.asarray(a[s])-b[s])) <= 20 for s in ('left', 'right'))


def median_geometry(group: list[dict]) -> dict:
    return {s: np.median([g[s] for g in group], axis=0).tolist() for s in ('left', 'right')}


def finite_monitor(document: dict, matrix: np.ndarray, geometry: dict) -> None:
    corners = np.asarray(geometry['left']+geometry['right'])
    calibration = np.asarray(document['models']['homography']['matrix'])
    for transform in (matrix, calibration @ matrix):
        denominators = np.column_stack((corners, np.ones(8))) @ transform[2]
        if not ((denominators > 1e-9).all() or (denominators < -1e-9).all()):
            raise ValueError('Registration is not finite across the SENSE monitor')


def evaluate_registration(
    projector: RecordedTestProjector, document: dict, samples: list[dict],
    anchor: dict | None, needs_matrix: bool, frame_size: tuple[int, int], *,
    normalize_geometry: Callable[[dict, tuple[int, int]], dict], recovering: bool = False,
) -> tuple[dict | None, np.ndarray | None, str, str | None, str | None]:
    """Calculate a proposed update from detached bounded state; no writes."""
    matrix = None
    if needs_matrix:
        for group in reversed(list(combinations(samples, 3))):
            median = projector._median_geometry(group)
            if not all(projector._close_geometry(item, median) for item in group):
                continue
            anchor = normalize_geometry(median, frame_size)
            matrix = projector._view_matrix(document, anchor)
            projector._finite_monitor(document, matrix, anchor)
            break
        if matrix is None:
            return anchor, None, 'acquiring', 'Waiting for three consistent current monitor measurements', None
    if not projector._aligned_geometry(samples[-1], anchor):
        group = samples[-3:]
        median = projector._median_geometry(group)
        moved = (len(group) == 3 and all(not projector._aligned_geometry(g, anchor) for g in group)
                 and not projector._aligned_geometry(median, anchor)
                 and all(projector._close_geometry(g, median) for g in group))
        return (anchor, matrix, 'alignment_pending', 'Monitor alignment uncertain; mapping suspended',
                'Confirmed monitor movement' if moved and not projector.recover_alignment else None)
    if projector.recover_alignment and recovering and not needs_matrix:
        good = [g for g in samples[:-1] if projector._aligned_geometry(g, anchor)]
        consistent = any(all(projector._close_geometry(g, projector._median_geometry(group)) for g in group)
                         for pair in combinations(good, 2) for group in [(*pair, samples[-1])])
        if not consistent:
            return anchor, None, 'alignment_pending', 'Waiting for three fresh measurements agreeing with the original monitor pose', None
    return anchor, matrix, 'locked', None, None
