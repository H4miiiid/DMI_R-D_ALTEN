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
from dmi_robot_master.integration.screen_profiles import load_profiles, region_at


GEOMETRY_FIELDS = ('center', 'corners', 'bbox', 'oriented_box')
# Existing Level baseline: max axis deviation from each control's median is
# 9 native px. This 10-px DISPLAY compatibility bound is not an action tolerance
# or a physical movement claim. Acquisition still requires 4-px agreement.
CACHE_CENTER_GUARD_PX = 10.
LOCK_EDGE_MARGIN_PX = 6.
LOCK_MIN_INSIDE_FRACTION = .95


def _geometry(region: dict, size: tuple[int, int], monitor: dict, *,
              edge_margin_px: float = 1., min_inside_fraction: float = 0.) -> dict | None:
    """Accept measured finite, convex, in-region quads and native centers only."""
    try:
        quad = np.asarray(region['corners'], np.float32)
        center = np.asarray(region['center'], float)
        parent = np.asarray(monitor['corners'], np.float32)
        if (quad.shape != (4, 2) or center.shape != (2,) or not np.isfinite(quad).all()
                or not np.isfinite(center).all() or not cv2.isContourConvex(quad)
                or abs(cv2.contourArea(quad)) < 1 or (quad < 0).any()
                or parent.shape != (4, 2) or not np.isfinite(parent).all()
                or not cv2.isContourConvex(parent)
                or (quad[:, 0] >= size[0]).any() or (quad[:, 1] >= size[1]).any()
                or cv2.pointPolygonTest(quad, tuple(center), False) < 0
                or cv2.pointPolygonTest(parent, tuple(center), False) < 0
                or any(cv2.pointPolygonTest(parent, tuple(map(float, p)), True) < -edge_margin_px for p in quad)):
            return None
        if min_inside_fraction:
            inside, _ = cv2.intersectConvexConvex(quad, parent)
            if inside / abs(cv2.contourArea(quad)) < min_inside_fraction:
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

    JSON selects required/optional measured elements on both sides. It never
    supplies coordinates, identities, OCR values or action authorization.
    The existing four-pixel monitor bound is deliberately conservative. It is a
    read-only compatibility check, not a physically validated movement threshold.
    """
    def __init__(self, *, profile_path=None) -> None:
        self.profiles = load_profiles() if profile_path is None else load_profiles(profile_path)
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
        self._required: set = set()
        self._profile = None
        self._pending_sidebar = None

    @staticmethod
    def _regions(observation, profile) -> dict:
        result, direct = observation.result, observation.direct_evidence
        layout = observation.layout_evidence or {}
        if not connected_regions(result):
            return {}
        candidates = {}
        for key in profile.allowed:
            region = region_at(layout, key)
            if not region and key[:2] == ('right_display', 'buttons'):
                # Same-pass OCR/border measurements excluded from the strict
                # target path. This channel is presentation/lock evidence only.
                region = layout.get('edge_buttons', {}).get(key[2])
                if region:
                    candidates[key] = region
                    continue
            if not region:
                continue
            raw = None
            if len(key) == 3 and key[1] == 'buttons':
                raw = direct.get('right_buttons' if key[0] == 'right_display' else 'left_buttons', {}).get(key[2])
            elif key == ('right_display', 'data_field'):
                raw = direct.get('right_field')
            else:
                # Other candidates come from the pre-tracking measurement channel.
                candidates[key] = region
                continue
            if raw is not None and np.max(np.abs(np.asarray(region['center'])-raw)) <= 4:
                candidates[key] = region
        measured = {key: geometry for key, region in candidates.items()
                    if (geometry := _geometry(region, observation.frame_size,
                                              result[key[0]]['geometry'], edge_margin_px=LOCK_EDGE_MARGIN_PX,
                                              min_inside_fraction=LOCK_MIN_INSIDE_FRACTION)) is not None}
        # Duplicate identities in one cell cannot contribute to acquisition.
        duplicates = set()
        buttons = [key for key in measured if len(key) == 3 and key[1] == 'buttons']
        for a, b in combinations(buttons, 2):
            if np.max(np.abs(np.asarray(measured[a]['center'])-measured[b]['center'])) <= 4:
                duplicates.update((a, b))
        return {key: region for key, region in measured.items() if key not in duplicates}

    def observe_full(self, observation, *, context=None, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        basis = (observation.source_id, observation.session_id, observation.frame_size, deepcopy(context))
        if self._context is not None and basis != self._context:
            self.invalidate('context_changed')
        age = now-observation.received_at+observation.upstream_age_seconds
        if not math.isfinite(age) or not 0 <= age <= 1.5:
            # Expired observations cannot confirm anything or renew evidence.
            # They do not expire the independently cached static layout.
            self._samples.clear()
            return
        result, direct = observation.result, observation.direct_evidence
        right = result['right_display']
        screen = direct.get('right_state')
        profile = self.profiles.get(screen)
        if (direct.get('right_visibility') != 'clear' or right['visibility'] != 'clear'
                or not connected_regions(result)):
            self.invalidate('unsupported_or_uncertain_view')
            return
        corners = {side: deepcopy(result[side]['geometry']['corners'])
                   for side in ('left_display', 'right_display')}
        if self._context is not None and any(
                np.max(np.abs(np.asarray(corners[side])-self._anchor[side])) > 4 for side in corners):
            self.invalidate('monitor_geometry_changed')
        if self._context is not None and screen not in (None, 'unknown', self.screen):
            # A recognized different identity is a real transition. Unknown OCR
            # alone is not evidence that the old screen has changed.
            prior = (self._context, self._anchor, self._last_receipt, self._confirmed)
            reuse = self._profile.reuse_left_sidebar
            self.invalidate('screen_changed')
            if reuse:
                self._pending_sidebar = prior
        if profile is None or not profile.matches(observation.layout_evidence or {}):
            if self._context is not None and screen in (None, 'unknown', self.screen):
                self._pause_identity(observation)
            else:
                self.invalidate('unsupported_or_uncertain_view')
            return
        measured = self._regions(observation, profile)
        prior = self._pending_sidebar
        if self._profile is not None and self._profile.reuse_left_sidebar:
            prior = (self._context, self._anchor, self._last_receipt, self._confirmed)
        retained = {}
        if (profile.reuse_left_sidebar and prior is not None and basis == prior[0]
                and 0 <= observation.received_at-prior[2] <= 1.5
                and all(np.max(np.abs(np.asarray(corners[side])-prior[1][side])) <= 4 for side in corners)):
            retained = {key: value for key, value in prior[3].items()
                        if key[0] == 'left_display' and key in measured and _close(value, measured[key])}
        if right['state'] != screen:
            if self._context is not None and self.screen == screen:
                self._pause_identity(observation)
                return
            # Legacy state smoothing may temporarily report unknown during a
            # normal-screen transition. Keep no active lock, only sidebar cells
            # remeasured NOW; every uncertain/context/loss case otherwise clears.
            self.invalidate('pending_screen_identity')
            if retained:
                self._pending_sidebar = (basis, prior[1], observation.received_at, retained)
            return
        if observation.capture_index <= self._last_index:
            return  # A repeated frame cannot count toward confirmation.
        if self._last_receipt is not None and observation.received_at-self._last_receipt > 1.5:
            self._samples.clear()  # Unconfirmed history cannot bridge a source gap.
        if self._context is None:
            # Reuse never copies right controls, title, values or evidence ages.
            self._confirmed = retained
            self._pending_sidebar = None
            self._context, self._anchor, self.screen = basis, corners, screen
            self._profile = profile
            self._required = set(profile.required)
        self._last_index = observation.capture_index
        self._last_receipt = observation.received_at
        released = False
        for key, region in list(self._confirmed.items()):
            incompatible = key in measured and not _close(region, measured[key], center_limit=CACHE_CENTER_GUARD_PX)
            if incompatible:
                # Release only the moved cell. Other confirmed elements stay fixed.
                del self._confirmed[key]
                for sample in self._samples:
                    sample.pop(key, None)
                released = True
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
                        _geometry(median, observation.frame_size, result[key[0]]['geometry'],
                                  edge_margin_px=LOCK_EDGE_MARGIN_PX,
                                  min_inside_fraction=LOCK_MIN_INSIDE_FRACTION) is not None):
                    self._confirmed[key] = median
                    break
        self.state = ('LOCKED' if self._required <= self._confirmed.keys() else
                      'PARTIAL_LOCK' if self._confirmed else 'ACQUIRING')

    def _pause_identity(self, observation) -> None:
        # Keep static confirmations dormant until current identity is readable
        # again; never acquire across an uncertain transition.
        self._samples.clear()
        self.state = 'PARTIAL_LOCK' if self._confirmed else 'ACQUIRING'
        self.reason = 'awaiting_screen_identity'
        self._last_index = max(self._last_index, observation.capture_index)
        self._last_receipt = observation.received_at

    def cached_layout(self) -> dict:
        """Detached presentation metadata. Never an Observation or target list."""
        return {'state': self.state, 'screen': self.screen, 'generation': self.generation,
                'reason': self.reason, 'presentation_only': True,
                'elements': {'/'.join(key): deepcopy(region) for key, region in self._confirmed.items()},
                'missing_required': sorted('/'.join(key) for key in self._required-self._confirmed.keys()),
                'profile': self._profile.metadata() if self._profile else None}

    @staticmethod
    def measured_display(result: dict, layout_evidence: dict | None, *, layout=None, frame_size=None) -> dict:
        """Use same-pass measured geometry on both sides in a detached preview.

        Keep stabilized values/activity/identity and the original Observation.
        LivePreviewState still independently filters direct presence and values.
        """
        candidate = deepcopy(result)
        pairs = []
        for side in ('left_display', 'right_display'):
            current, measured = candidate[side], (layout_evidence or {}).get(side, {})
            pairs.extend((current.get(key), measured.get(key)) for key in ('title', 'data_field', 'speed_indicator'))
            for kind in ('buttons', 'boxes'):
                pairs.extend((region, measured.get(kind, {}).get(name))
                             for name, region in current.get(kind, {}).items())
        for region, measured in pairs:
            if region is not None and measured is not None:
                region.update({key: deepcopy(measured[key]) for key in GEOMETRY_FIELDS if key in measured})
        if (layout and frame_size and layout['screen'] == candidate['right_display']['state']
                and connected_regions(candidate)):
            right = candidate['right_display']
            for name, measured in (layout_evidence or {}).get('edge_buttons', {}).items():
                cached = layout['elements'].get('right_display/buttons/'+name)
                if (name not in right['buttons'] and cached is not None and
                        _geometry(measured, frame_size, right['geometry'], edge_margin_px=LOCK_EDGE_MARGIN_PX,
                                  min_inside_fraction=LOCK_MIN_INSIDE_FRACTION) is not None
                        and _close(cached, measured, center_limit=CACHE_CENTER_GUARD_PX)):
                    right['buttons'][name] = deepcopy(measured)
        return candidate

    @staticmethod
    def display_evidence(direct: dict, layout_evidence: dict | None, display: dict) -> dict:
        """Detached preview presence map. Never use it for targets/actions."""
        evidence = deepcopy(direct)
        for name, region in (layout_evidence or {}).get('edge_buttons', {}).items():
            if name not in direct.get('right_buttons', {}) and name in display['right_display']['buttons']:
                evidence.setdefault('right_buttons', {})[name] = deepcopy(region['center'])
        return evidence

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
