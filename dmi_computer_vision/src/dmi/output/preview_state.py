"""Display-only stabilization; detector results and evidence are never modified."""
from __future__ import annotations

from copy import deepcopy
import math
import time
import cv2
import numpy as np

from dmi_computer_vision.src.dmi.output.annotation import annotate_frame


def connected_result(result: dict) -> bool:
    left, right = (result[side + "_display"]["geometry"] for side in ("left", "right"))
    return bool(left and right and np.max(np.linalg.norm(
        np.float32(left["corners"])[[1, 2]] - np.float32(right["corners"])[[0, 3]], axis=1)) < 3)


def _regions(result):
    for side in ("left_display", "right_display"):
        display = result[side]
        for name in ("geometry", "title", "data_field", "speed_indicator"):
            if isinstance(display.get(name), dict):
                yield (side, name), display[name]
        for category in ("buttons", "boxes", "summary"):
            for name, region in display.get(category, {}).items():
                yield (side, category, name), region


class PreviewState:
    def __init__(self, *, max_hold_seconds: float = 1.5, deadband_px: float = 4.) -> None:
        if not math.isfinite(max_hold_seconds) or not 0 < max_hold_seconds <= 1.5:
            raise ValueError("Preview hold must be positive and at most 1.5 seconds")
        if not math.isfinite(deadband_px) or not 0 <= deadband_px <= 4:
            raise ValueError("Preview deadband must be between zero and four pixels")
        self.max_hold = max_hold_seconds
        self.deadband = deadband_px
        self.clear()

    def clear(self):
        self.result = None
        self.received = None
        self._patches = []
        self._patches_by_key = {}
        self.overlay_valid = False
        self._shape = None
        self._upstream_age = 0.

    def _supports_result(self, result: dict) -> bool:
        return connected_result(result) and result['right_display']['visibility'] == 'clear'

    def update(self, result: dict, packet) -> None:
        if not self._supports_result(result):
            self.clear()
            return
        previous = self.result
        self.result = deepcopy(result)
        self.received = packet.received_at
        self._upstream_age = (getattr(packet, "remote_capture_age_seconds", 0.)
                              + getattr(packet, "transport_round_trip_seconds", 0.))
        self._shape = packet.image.shape
        self._patches = []
        self._patches_by_key = {}
        prior = dict(_regions(previous)) if previous is not None else {}
        same_state = previous is not None and previous["right_display"]["state"] == result["right_display"]["state"]
        observed_regions = dict(_regions(result))
        for key, region in _regions(self.result):
            old = prior.get(key) if same_state else None
            if old is not None and all(old.get(k) == region.get(k) for k in ("text", "value", "active", "icon")):
                distance = np.max(abs(np.float32(old["center"]) - np.float32(region["center"])))
                corner_shift = np.max(abs(np.float32(old["corners"]) - np.float32(region["corners"])))
                if "oriented_box" in region:
                    corner_shift = max(corner_shift, np.max(abs(np.float32(old["oriented_box"])
                                                               - np.float32(region["oriented_box"]))))
                corners = np.float32(region["corners"])
                shape_limit = min(12., float(np.min(np.linalg.norm(np.roll(corners, -1, axis=0)-corners, axis=1))) * .1)
                # A noisy border face can shift a corner more than its center.
                # Hold small center jitter only while the shape stays compatible;
                # relocated/resized controls snap to their current observation.
                if distance <= self.deadband and corner_shift <= shape_limit:
                    for field in ("corners", "bbox", "center", "oriented_box"):
                        if field not in region:
                            continue
                        region[field] = deepcopy(old[field])
            # Check the CURRENT measured region, not its display-smoothed copy.
            observed = observed_regions[key]
            box = np.asarray(observed["bbox"], dtype=int)
            patch = self._patch(packet.image, box)
            if patch is not None:
                self._patches.append((box, patch))
                self._patches_by_key[key] = (box, patch)

    @staticmethod
    def _patch(image, box):
        x1, y1, x2, y2 = map(int, box)
        height, width = image.shape[:2]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            return None
        gray = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, (min(160, gray.shape[1]), min(96, gray.shape[0])))

    def render(self, packet, now: float | None = None):
        now = time.monotonic() if now is None else now
        age = None if self.received is None else now - self.received + self._upstream_age
        frame_age = (now - packet.received_at + getattr(packet, "remote_capture_age_seconds", 0.)
                     + getattr(packet, "transport_round_trip_seconds", 0.))
        valid = (self.result is not None and packet.image.shape == self._shape
                 and 0 <= age <= self.max_hold and 0 <= frame_age <= self.max_hold)
        if valid:
            for box, reference in self._patches:
                patch = self._patch(packet.image, box)
                if patch is None or patch.shape != reference.shape:
                    valid = False
                    break
                change = cv2.absdiff(patch, reference) > 12
                # Local checks prevent a small changed glyph being diluted by
                # the full image. Uncertainty hides the entire held overlay.
                ys, xs = np.arange(0, change.shape[0], 8), np.arange(0, change.shape[1], 8)
                changed_pixels = np.add.reduceat(np.add.reduceat(change, ys, axis=0), xs, axis=1)
                area = np.minimum(8, change.shape[0] - ys)[:, None] * np.minimum(8, change.shape[1] - xs)[None, :]
                if np.any(changed_pixels > area * .2):
                    valid = False
                    break
        self.overlay_valid = valid
        image = annotate_frame(packet.image, self.result) if valid else packet.image.copy()
        text = f"PREVIEW ONLY | detection age {age:.2f}s" if age is not None else "PREVIEW | awaiting detection"
        if not valid and age is not None:
            text += " | overlay hidden"
        text += f" | frame age {frame_age:.2f}s"
        cv2.putText(image, text, (20, 150), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 190, 255), 2)
        return image


class LivePreviewState(PreviewState):
    """Shared GUI overlay for measured connected or separated display regions.

    The render worker owns this object. Existing CLI callers keep PreviewState's
    immediate loss behavior. No retained data is returned to detector consumers.
    """

    def clear(self):
        super().clear()
        self.basis = None
        self._retained = {}
        self._unknown_updates = 0

    @staticmethod
    def context(result, evidence, frame_size):
        corners = {side: result[side + '_display']['geometry']['corners']
                   for side in ('left', 'right') if result[side + '_display']['geometry']
                   and result[side + '_display'].get('visibility', 'clear') == 'clear'
                   and (side != 'right' or evidence.get('right_visibility', 'clear') == 'clear')}
        if not corners:
            return None
        return {'size': tuple(frame_size),
                'screen': evidence.get('right_state', result['right_display']['state']),
                'left_title': (result['left_display'].get('title') or {}).get('text') if 'left' in corners else None,
                'layout': ('connected' if connected_result(result) else 'separated') if len(corners) == 2 else None,
                'corners': corners}

    def _supports_result(self, result: dict) -> bool:
        return self.context(result, {}, ()) is not None

    @staticmethod
    def _same_context(old, new):
        if old is None or new is None or old['size'] != new['size']:
            return False
        if old['layout'] and new['layout'] and old['layout'] != new['layout']:
            return False
        if ('right' in old['corners'] and 'right' in new['corners'] and
                old['screen'] != 'unknown' and new['screen'] != 'unknown' and old['screen'] != new['screen']):
            return False
        if old['left_title'] and new['left_title'] and old['left_title'] != new['left_title']:
            return False
        return True

    @classmethod
    def compatible(cls, old, new):
        return (cls._same_context(old, new) and old['corners'].keys() == new['corners'].keys()
                and all(np.max(np.abs(np.asarray(old['corners'][side]) - new['corners'][side])) <= 4
                        for side in old['corners']))

    def _discard_side(self, side):
        if self.result is not None:
            self._hide_side(self.result[side + '_display'])
        self._retained = {key: row for key, row in self._retained.items() if key[0] != side + '_display'}
        self._patches_by_key = {key: row for key, row in self._patches_by_key.items() if key[0] != side + '_display'}

    @staticmethod
    def _hide_side(display):
        for key in ('geometry', 'title', 'data_field', 'speed_indicator'):
            if key in display:
                display[key] = None
        for key in ('buttons', 'boxes', 'summary'):
            if key in display:
                display[key] = {}

    @staticmethod
    def _set_region(result, key, region):
        owner = result[key[0]] if len(key) == 2 else result[key[0]].setdefault(key[1], {})
        if region is None and len(key) == 3:
            owner.pop(key[-1], None)
        else:
            owner[key[-1]] = deepcopy(region)

    @staticmethod
    def _retainable(key, region):
        return (len(key) == 3 and key[1] == 'buttons') or (
            len(key) == 2 and key[1] == 'title' and bool(region.get('text')))

    @staticmethod
    def _same_cell(old, new):
        a, b = np.asarray(old['bbox']), np.asarray(new['bbox'])
        overlap = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2]))
        return np.prod(overlap) >= .5 * min(np.prod(a[2:] - a[:2]), np.prod(b[2:] - b[:2]))

    def update(self, result, packet, *, evidence=None, reset=False, updates=1):
        evidence = evidence or {}
        context = self.context(result, evidence, (packet.image.shape[1], packet.image.shape[0]))
        if reset or not self._same_context(self.basis, context):
            self.clear()
        if context is None:
            return
        prior_basis = deepcopy(self.basis)
        for side in ('left', 'right'):
            if (side not in context['corners'] or prior_basis and side in prior_basis['corners'] and
                    np.max(np.abs(np.asarray(prior_basis['corners'][side]) - context['corners'][side])) > 4):
                self._discard_side(side)
                if prior_basis:
                    prior_basis['corners'].pop(side, None)
        screen = context['screen']
        candidate = deepcopy(result)
        pending_screen = screen != 'unknown' and screen != result['right_display']['state']
        self._unknown_updates = self._unknown_updates + updates if screen == 'unknown' and 'right' in context['corners'] else 0
        if pending_screen or self._unknown_updates > 2:
            self._discard_side('right')  # No stale controls during screen debounce.
            candidate['right_display']['state'] = 'unknown'
        if screen == 'unknown' and self.result is not None and self._unknown_updates <= 2:
            candidate['right_display']['state'] = self.result['right_display']['state']
        for side in ('left', 'right'):
            display = candidate[side + '_display']
            if side not in context['corners']:
                self._hide_side(display)
                continue
            # TWIN's accepted left-workflow output omits absent buttons and does
            # not export a raw left-buttons map. Reuse those measured regions for
            # display only; do not add evidence or change its detector contract.
            direct = evidence.get(side + '_buttons', {
                name: region['center'] for name, region in display.get('buttons', {}).items()
            } if side == 'left' else {})
            display['buttons'] = {name: region for name, region in display.get('buttons', {}).items()
                if name in direct and np.max(np.abs(np.asarray(region['center']) - direct[name])) <= 4}
            if side == 'right' and (screen == 'unknown' or pending_screen):
                display['buttons'], display['title'] = {}, None
                display['data_field'] = None
            if side == 'right' and display.get('data_field'):
                # Do not present a temporally retained field value as new evidence.
                field = display['data_field']
                if evidence.get('right_field') is None:
                    display['data_field'] = None
                elif field.get('value') != evidence.get('right_field_value'):
                    field['value'] = None
        previous = self._retained
        super().update(candidate, packet)
        self.basis = deepcopy(context)
        if prior_basis:
            for side in self.basis['corners'].keys() & prior_basis['corners'].keys():
                self.basis['corners'][side] = prior_basis['corners'][side]
            if self.basis['screen'] == 'unknown' and self._unknown_updates <= 2:
                self.basis['screen'] = prior_basis['screen']
        observed = dict(_regions(self.result))
        effective_receipt = self.received - self._upstream_age
        retained = {key: (deepcopy(region), effective_receipt, 0, self._patches_by_key.get(key))
                    for key, region in observed.items() if self._retainable(key, region)}
        for key, (region, seen, misses, patch) in previous.items():
            if key in observed or misses + updates > 2 or effective_receipt - seen > self.max_hold:
                continue
            # A changed identity in the same measured cell replaces the old label.
            if any(other != key and other[:2] == key[:2] and
                   self._same_cell(region, current)
                   for other, current in observed.items()):
                continue
            self._set_region(self.result, key, region)
            retained[key] = (region, seen, misses + updates, patch)
            if patch is not None:
                self._patches_by_key[key] = patch
        self._retained = retained
        self._patches = list(self._patches_by_key.values())

    @property
    def expires_at(self):
        if self.received is None:
            return 0.
        return min([self.received - self._upstream_age] +
                   [row[1] for row in self._retained.values()]) + self.max_hold

    def render(self, packet, now=None):
        now = time.monotonic() if now is None else now
        for key, row in list(self._retained.items()):
            if now - row[1] > self.max_hold:
                self._set_region(self.result, key, None)
                self._retained.pop(key)
                self._patches_by_key.pop(key, None)
        self._patches = list(self._patches_by_key.values())
        image = super().render(packet, now)
        if not self.overlay_valid:
            self.clear()  # Restored pixels alone cannot resurrect invalid overlays.
        return image
