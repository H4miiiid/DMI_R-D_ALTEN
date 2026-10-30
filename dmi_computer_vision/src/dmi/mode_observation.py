"""Opt-in SENSE mode evidence, separate from detector output and action gates."""
from collections import deque
from copy import deepcopy
from functools import lru_cache
import math

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.icons import (
    ASSET_DIRECTORY, _normalize, _recognize, _rectify_region,
)

# Reviewed corresponding silhouettes, not numerical filename arithmetic.
MODE_PAIRS = {"mode_01": ("MO_01", "MO_02"), "mode_06": ("MO_06", "MO_05"),
              "mode_07": ("MO_07", "MO_08"), "mode_09": ("MO_09", "MO_10"),
              "mode_14": ("MO_14", "MO_15"), "mode_16": ("MO_16", "MO_17"),
              "mode_19": ("MO_19", "MO_20"), "mode_21": ("MO_21", "MO_22")}


def _mask(image, yellow):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (18, 100, 80) if yellow else (0, 0, 80),
                       (42, 255, 255) if yellow else (179, 100, 255))


@lru_cache(maxsize=1)
def _mode_templates():
    result = {}
    for box, yellow in (("box_14", False), ("box_16", True)):
        templates = {}
        paths = {mode: ASSET_DIRECTORY / "modes" / box / f"{pair[int(yellow)]}.bmp"
                 for mode, pair in MODE_PAIRS.items()}
        if not yellow:
            paths["power"] = ASSET_DIRECTORY / "modes/power.bmp"
        for mode, path in paths.items():
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f"Missing mode template: {path}")
            mask = _mask(image, yellow)
            if not mask.any():
                raise ValueError(f"Empty mode template: {path}")
            templates[mode] = [_normalize(cv2.dilate(mask, np.ones((size, size), np.uint8)))
                               for size in (1, 2, 3)]
        result[box] = templates
    return result


def connected_regions(result: dict) -> bool:
    """Require measured shared corners, never a camera-index arrangement rule."""
    try:
        left = np.asarray(result["left_display"]["geometry"]["corners"], float)
        right = np.asarray(result["right_display"]["geometry"]["corners"], float)
        return (left.shape == right.shape == (4, 2) and np.isfinite(left).all()
                and np.isfinite(right).all()
                and np.allclose(left[[1, 2]], right[[0, 3]], atol=1, rtol=0))
    except (KeyError, TypeError, ValueError):
        return False


def observe_modes(image: np.ndarray, result: dict) -> dict:
    """Match only inside current measured boxes; never infer missing boxes."""
    if not connected_regions(result):
        return {}
    templates = _mode_templates()
    boxes = result["left_display"].get("boxes", {})
    observations = {}
    for box in ("box_14", "box_16"):
        region = boxes.get(box)
        if region is None:
            continue
        quad = np.asarray(region["corners"], np.float32)
        if (quad.shape != (4, 2) or not np.isfinite(quad).all()
                or not cv2.isContourConvex(quad)
                or (quad < 0).any() or (quad[:, 0] >= image.shape[1]).any()
                or (quad[:, 1] >= image.shape[0]).any()):
            continue
        crop = _rectify_region(image, quad)
        mask = _mask(crop, box == "box_16")
        # Reuse the conservative silhouette/margin matcher. Color is measured
        # first, then supplied as neutral foreground to the existing matcher.
        neutral = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        mode = _recognize(neutral, templates[box]) if mask.any() else None
        # A foreign-color/unknown glyph is not a proven empty blink-off box.
        bright = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 75
        status = "recognized" if mode else "unknown" if bright.mean() > .015 else "empty"
        observations[box] = {"mode": mode, "status": status,
                             "center": list(region["center"])}
    return observations


class ModeHistory:
    """Bounded UI history. Retained blink identity never renews direct evidence."""
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.samples = deque(maxlen=32)
        self._geometry = None
        self._power_at = None
        self._blink_mode = None
        self._blink_at = None
        self._blink_power_at = None

    def _result(self, state, mode, evidence_at, timestamp):
        # A short retained transition identity can span a later five-second hold,
        # but is neither renewed by blink-off nor any action authorization.
        recent = self._blink_at is not None and timestamp-self._blink_at <= 8.
        same = recent and mode == self._blink_mode
        replaced = state == 'steady' and same and self._blink_power_at is not None
        return {"state": state, "mode": mode, "evidence_at": evidence_at,
                "replacement_verified": bool(replaced),
                "previous_blink_mode": self._blink_mode if recent else None,
                "blink_confirmed_at": self._blink_at if recent else None,
                "power_observed_at": self._blink_power_at if recent else self._power_at}

    def update(self, timestamp: float, observations: dict, geometry=None) -> dict:
        if not math.isfinite(timestamp):
            raise ValueError("Mode timestamps must be finite")
        if (self.samples and (timestamp <= self.samples[-1][0]
                             or timestamp - self.samples[-1][0] > 1.0)):
            self.reset()
        if geometry is not None:
            current = np.asarray(geometry, float)
            if self._geometry is not None and (
                    current.shape != self._geometry.shape
                    or np.max(np.abs(current-self._geometry)) > 4):
                self.reset()
            # Anchor to this history's basis: small per-frame movement must not
            # accumulate indefinitely across evidence from incompatible geometry.
            if self._geometry is None:
                self._geometry = current.copy()
        if any(observations.get(box, {}).get("status") not in ("recognized", "empty")
               for box in ("box_14", "box_16")):
            self.reset()
            return self._result("unknown", None, None, timestamp)
        self.samples.append((timestamp, deepcopy(observations)))
        while self.samples and timestamp-self.samples[0][0] > 3.0:
            self.samples.popleft()
        samples = list(self.samples)
        white, yellow = (observations[b]["mode"] for b in ("box_14", "box_16"))
        if white == "power":
            self._power_at = timestamp
        else:
            self._power_at = None
            if white is not None and white != self._blink_mode:
                # Another white mode has already replaced power. Returning to
                # the old blinking identity later is a different transition.
                self._blink_mode = self._blink_at = self._blink_power_at = None
        if yellow is not None and self._blink_mode is not None and yellow != self._blink_mode:
            self._blink_mode = self._blink_at = None
            self._blink_power_at = None
        # Changes of yellow identity discard older blink cycles.
        ons = [(t, o["box_16"]["mode"]) for t, o in samples if o["box_16"]["mode"]]
        last_mode = ons[-1][1] if ons else None
        if last_mode:
            incompatible = [t for t, mode in ons if mode != last_mode]
            after = max(incompatible) if incompatible else -math.inf
            cycle = [(t, o) for t, o in samples if t > after]
            lit = [t for t, o in cycle if o["box_16"]["mode"] == last_mode]
            off_between = any(lit[0] < t < lit[-1] and o["box_16"]["status"] == "empty"
                              for t, o in cycle) if len(lit) >= 2 else False
            if off_between and lit[-1]-lit[0] >= .35 and timestamp-lit[-1] <= .9:
                # Only a directly observed on-frame confirms/renews blinking.
                if yellow:
                    self._blink_mode, self._blink_at = last_mode, lit[-1]
                    # Historical power cannot establish lineage after a mode
                    # has already become white before it starts blinking.
                    self._blink_power_at = timestamp if white == "power" else None
                return self._result("blinking" if yellow else "blink_off", last_mode, lit[-1], timestamp)
        # Steady needs consecutive current samples, not an old matching sample.
        consecutive = []
        for t, o in reversed(samples):
            if not white or o["box_14"]["mode"] != white or o["box_16"]["status"] != "empty":
                break
            consecutive.append(t)
        if len(consecutive) >= 3 and timestamp-consecutive[-1] >= .8:
            return self._result("power" if white == "power" else "steady", white, timestamp, timestamp)
        return self._result("pending", yellow or white, timestamp, timestamp)
