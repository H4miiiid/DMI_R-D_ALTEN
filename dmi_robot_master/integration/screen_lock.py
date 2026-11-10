"""Bounded SENSE layout acquisition. Cached geometry is presentation only.

The observation owner serializes calls. No images, OCR values, activity, action
evidence or robot coordinates are retained here. Full analysis still supplies
dynamic state; selective monitoring is a separate phase.
"""
from collections import deque
from copy import deepcopy
from itertools import combinations
import math
import time

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.mode_observation import connected_regions


GEOMETRY_FIELDS = ('center', 'corners', 'bbox', 'oriented_box')
# Existing Level baseline: max axis deviation from each control's median is
# 9 native px. This 10-px DISPLAY compatibility bound is not an action tolerance
# or a physical movement claim. Acquisition still requires 4-px agreement.
CACHE_CENTER_GUARD_PX = 10.
BUTTONS = {
    'Driver ID': frozenset([f'digit_{i}' for i in range(10)] + ['delete', 'decimal', 'cancel']),
    'Level': frozenset(['level_0', 'level_1', 'level_2', 'level_3', 'kvb',
                        'scmt', 'memor', 'atc_2', 'tbl1_plus', 'more', 'close']),
}


def _geometry(region: dict, size: tuple[int, int], monitor: dict) -> dict | None:
    """Accept measured finite, convex, in-region quads and native centers only."""
    try:
        quad = np.asarray(region['corners'], np.float32)
        center = np.asarray(region['center'], float)
        parent = np.asarray(monitor['corners'], np.float32)
        if (quad.shape != (4, 2) or center.shape != (2,) or not np.isfinite(quad).all()
                or not np.isfinite(center).all() or not cv2.isContourConvex(quad)
                or abs(cv2.contourArea(quad)) < 1 or (quad < 0).any()
                or (quad[:, 0] >= size[0]).any() or (quad[:, 1] >= size[1]).any()
                or cv2.pointPolygonTest(quad, tuple(center), False) < 0
                or any(cv2.pointPolygonTest(parent, tuple(map(float, p)), True) < -1 for p in quad)):
            return None
        return {key: deepcopy(region[key]) for key in GEOMETRY_FIELDS if key in region}
    except (KeyError, TypeError, ValueError, cv2.error):
        return None


def _close(a: dict, b: dict, *, center_limit: float = 4.) -> bool:
    """Read-only center/shape bounds; no change to action tolerances."""
    qa, qb = (np.asarray(r['corners'], float) for r in (a, b))
    shape_limit = min(12., float(np.min(np.linalg.norm(np.roll(qb, -1, axis=0)-qb, axis=1))) * .1)
    return bool(np.max(np.abs(np.asarray(a['center'])-b['center'])) <= center_limit
                and np.max(np.abs(qa-qb)) <= shape_limit)


def _median(samples: list[dict]) -> dict:
    # Every coordinate comes from current measured samples, never profile slots.
    region = {key: np.median([r[key] for r in samples], axis=0).tolist()
              for key in GEOMETRY_FIELDS if all(key in r for r in samples)}
    return region


class ScreenLock:
    """Confirm each element from three distinct full observations in five.

    Required: current right title, grey field geometry and the observed screen's
    supported buttons. Left boxes/speedometer are optional independently measured
    elements: incomplete left grids cannot fabricate boxes or prevent a right lock.
    The existing four-pixel monitor bound is deliberately conservative. It is a
    read-only compatibility check, not a physically validated movement threshold.
    """
    def __init__(self) -> None:
        self.generation = 0
        self.invalidate('session_start')

    def invalidate(self, reason: str) -> None:
        self.generation += 1
        self.reason = reason
        self.state = 'ACQUIRING'
        self.screen = None
        self._context = self._anchor = None
        self._last_index = -1
        self._last_receipt = None
        self._samples: deque = deque(maxlen=5)
        self._confirmed: dict = {}
        self._seen: dict = {}
        self._misses: dict = {}
        self._required: set = set()

    @staticmethod
    def _regions(observation) -> dict:
        result, direct = observation.result, observation.direct_evidence
        layout = observation.layout_evidence or {}
        right = layout.get('right_display')
        if right is None:
            return {}  # Stabilized results alone cannot establish independent measurements.
        candidates = {}
        for name in ('title', 'data_field'):
            region = right.get(name)
            if not region:
                continue
            if name == 'data_field' and (direct.get('right_field') is None or
                    np.max(np.abs(np.asarray(region['center'])-direct['right_field'])) > 4):
                continue
            candidates[('right_display', name)] = region
        for name, region in right.get('buttons', {}).items():
            raw = direct.get('right_buttons', {}).get(name)
            if name in BUTTONS[right['state']] and raw is not None and (
                    np.max(np.abs(np.asarray(region['center'])-raw)) <= 4):
                candidates[('right_display', 'buttons', name)] = region
        left = layout.get('left_display', {})
        candidates.update({('left_display', 'boxes', name): region
                           for name, region in left.get('boxes', {}).items()
                           if name in {f'box_{i}' for i in range(1, 23)}})
        if left.get('speed_indicator'):
            candidates[('left_display', 'speed_indicator')] = left['speed_indicator']
        measured = {key: geometry for key, region in candidates.items()
                    if (geometry := _geometry(region, observation.frame_size,
                                              result[key[0]]['geometry'])) is not None}
        # Duplicate identities in one cell cannot contribute to acquisition.
        duplicates = set()
        buttons = [key for key in measured if len(key) == 3 and key[1] == 'buttons']
        for a, b in combinations(buttons, 2):
            if np.max(np.abs(np.asarray(measured[a]['center'])-measured[b]['center'])) <= 4:
                duplicates.update((a, b))
        return {key: region for key, region in measured.items() if key not in duplicates}

    def observe_full(self, observation, *, context=None, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        age = now-observation.received_at+observation.upstream_age_seconds
        if not math.isfinite(age) or not 0 <= age <= 1.5:
            self.invalidate('stale_source')
            return
        result, direct = observation.result, observation.direct_evidence
        right = result['right_display']
        screen = direct.get('right_state')
        if (screen not in BUTTONS or right['state'] != screen or
                direct.get('right_visibility') != 'clear' or right['visibility'] != 'clear'
                or not connected_regions(result)):
            self.invalidate('unsupported_or_uncertain_view')
            return
        basis = (observation.source_id, observation.session_id, observation.frame_size, deepcopy(context))
        corners = {side: deepcopy(result[side]['geometry']['corners'])
                   for side in ('left_display', 'right_display')}
        if self._context is not None:
            reason = None
            if basis != self._context or screen != self.screen:
                reason = 'context_or_screen_changed'
            elif observation.received_at-self._last_receipt > 1.5:
                reason = 'source_gap'
            elif any(np.max(np.abs(np.asarray(corners[side])-self._anchor[side])) > 4
                     for side in corners):
                reason = 'monitor_geometry_changed'
            if reason:
                self.invalidate(reason)
        if observation.capture_index <= self._last_index:
            return  # A repeated frame cannot count toward confirmation.
        if self._context is None:
            self._context, self._anchor, self.screen = basis, corners, screen
            self._required = {('right_display', 'title'), ('right_display', 'data_field')} | {
                ('right_display', 'buttons', name) for name in BUTTONS[screen]}
        self._last_index = observation.capture_index
        self._last_receipt = observation.received_at
        measured = self._regions(observation)
        effective_receipt = observation.received_at-observation.upstream_age_seconds
        released = False
        for key, region in list(self._confirmed.items()):
            self._misses[key] = self._misses.get(key, 0)+1 if key not in measured else 0
            incompatible = key in measured and not _close(region, measured[key], center_limit=CACHE_CENTER_GUARD_PX)
            lost = self._misses[key] > 2 or (key not in measured and effective_receipt-self._seen[key] > 1.5)
            if incompatible or lost:
                # Release only the moved cell. Other confirmed elements stay fixed.
                del self._confirmed[key]
                self._seen.pop(key, None)
                self._misses.pop(key, None)
                for sample in self._samples:
                    sample.pop(key, None)
                released = True
            elif key in measured:
                self._seen[key] = effective_receipt
        if released:
            self.generation += 1
            self.reason = 'element_geometry_changed_or_lost'
        self._samples.append(measured)
        for key in measured.keys()-self._confirmed.keys():
            samples = [sample[key] for sample in self._samples if key in sample]
            # At most ten triples; no unbounded retries or stale successful history.
            for group in reversed(list(combinations(samples, 3))):
                median = _median(group)
                if (all(_close(item, median) for item in group) and
                        _geometry(median, observation.frame_size, result[key[0]]['geometry']) is not None):
                    self._confirmed[key] = median
                    self._seen[key] = effective_receipt
                    self._misses[key] = 0
                    break
        self.state = ('LOCKED' if self._required <= self._confirmed.keys() else
                      'PARTIAL_LOCK' if self._confirmed else 'ACQUIRING')

    def cached_layout(self) -> dict:
        """Detached presentation metadata. Never an Observation or target list."""
        return {'state': self.state, 'screen': self.screen, 'generation': self.generation,
                'reason': self.reason, 'presentation_only': True,
                'elements': {'/'.join(key): deepcopy(region) for key, region in self._confirmed.items()},
                'missing_required': sorted('/'.join(key) for key in self._required-self._confirmed.keys())}

    @staticmethod
    def measured_display(result: dict, layout_evidence: dict | None) -> dict:
        """Use same-pass measured right geometry in a detached preview copy.

        Keep stabilized values/activity/identity and the original Observation.
        LivePreviewState still independently filters direct presence and values.
        """
        candidate = deepcopy(result)
        if not layout_evidence or not layout_evidence.get('right_display'):
            return candidate
        layout_evidence = layout_evidence['right_display']
        right = candidate['right_display']
        pairs = [(right.get(key), layout_evidence.get(key)) for key in ('title', 'data_field')]
        pairs.extend((region, layout_evidence.get('buttons', {}).get(name))
                     for name, region in right.get('buttons', {}).items())
        for region, measured in pairs:
            if region is not None and measured is not None:
                region.update({key: deepcopy(measured[key]) for key in GEOMETRY_FIELDS if key in measured})
        return candidate

    @staticmethod
    def apply_display(result: dict | None, layout: dict) -> None:
        """Change geometry of an existing preview copy; never resurrect content."""
        if result is None or layout['screen'] != result['right_display']['state']:
            return
        for path, geometry in layout['elements'].items():
            parts = path.split('/')
            owner = result[parts[0]]
            region = owner.get(parts[1]) if len(parts) == 2 else owner.get(parts[1], {}).get(parts[2])
            if region is not None and _close(geometry, region, center_limit=CACHE_CENTER_GUARD_PX):
                region.update(deepcopy(geometry))
