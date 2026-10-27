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
        self._shape = None
        self._upstream_age = 0.

    def update(self, result: dict, packet) -> None:
        if not connected_result(result) or result["right_display"]["visibility"] != "clear":
            self.clear()
            return
        previous = self.result
        self.result = deepcopy(result)
        self.received = packet.received_at
        self._upstream_age = (getattr(packet, "remote_capture_age_seconds", 0.)
                              + getattr(packet, "transport_round_trip_seconds", 0.))
        self._shape = packet.image.shape
        self._patches = []
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
        image = annotate_frame(packet.image, self.result) if valid else packet.image.copy()
        text = f"PREVIEW ONLY | detection age {age:.2f}s" if age is not None else "PREVIEW | awaiting detection"
        if not valid and age is not None:
            text += " | overlay hidden"
        text += f" | frame age {frame_age:.2f}s"
        cv2.putText(image, text, (20, 150), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 190, 255), 2)
        return image
