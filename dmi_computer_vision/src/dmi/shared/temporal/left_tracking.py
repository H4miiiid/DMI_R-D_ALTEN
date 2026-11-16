"""Short, evidence-backed tracking of the left display through blurred frames."""
from __future__ import annotations

import cv2
import numpy as np


class LeftDisplayStabilizer:
    """Combine border measurements with verified inter-frame image motion.

    Optical flow can bridge up to three missed border measurements. Forward /
    backward consistency, RANSAC, spatial coverage and motion bounds must all
    pass. Without verified motion, missing regions are immediately omitted.
    """

    def __init__(self) -> None:
        self._previous: dict[str, np.ndarray] = {}
        self._ages: dict[str, int] = {}
        self._image: np.ndarray | None = None
        self._points: np.ndarray | None = None

    def reset(self) -> None:
        self._previous.clear()
        self._ages.clear()
        self._image = None
        self._points = None

    def update(
        self,
        boxes: dict[str, np.ndarray],
        speed: np.ndarray | None,
        frame: np.ndarray | None = None,
    ) -> tuple[dict[str, np.ndarray], np.ndarray | None]:
        current = dict(boxes)
        if speed is not None:
            current["speed"] = speed
        motion = self._image_motion(frame) if frame is not None else None
        previous = {
            name: (
                cv2.perspectiveTransform(q[None], motion)[0]
                if motion is not None
                else q
            )
            for name, q in self._previous.items()
        }
        changes = [
            np.linalg.norm(q - previous[name], axis=1).max()
            for name, q in current.items()
            if name in previous
        ]
        movement = float(np.median(changes)) if changes else 0
        alpha = 0.3 if movement < 3 else (0.7 if movement < 10 else 1.0)
        result, ages = {}, {}
        for name in current.keys() | previous.keys():
            detected, predicted = current.get(name), previous.get(name)
            age = self._ages.get(name, 0)
            disagreement = (
                float(np.max(np.linalg.norm(detected - predicted, axis=1)))
                if detected is not None and predicted is not None
                else 0
            )
            # A single inconsistent border cannot change the identity of a box.
            unreliable = detected is None or (motion is not None and disagreement > 12)
            if unreliable:
                if motion is not None and predicted is not None and age < 3:
                    result[name], ages[name] = predicted, age + 1
                continue
            result[name] = (
                detected.copy()
                if predicted is None
                else predicted + alpha * (detected - predicted)
            )
            ages[name] = 0
        self._previous, self._ages = result, ages
        ordered = sorted(
            (name for name in result if name != "speed"), key=lambda name: int(name[4:])
        )
        return {name: result[name] for name in ordered}, result.get("speed")

    def _image_motion(self, frame: np.ndarray) -> np.ndarray | None:
        gray = cv2.cvtColor(cv2.resize(frame, (400, 640)), cv2.COLOR_BGR2GRAY)
        old, points = self._image, self._points
        self._image = gray
        # Tiled features retain evidence away from the high-contrast dial.
        features = []
        for y in range(0, 640, 128):
            for x in range(0, 400, 100):
                found = cv2.goodFeaturesToTrack(
                    gray[y : y + 128, x : x + 100], 12, 0.02, 8, blockSize=5
                )
                if found is not None:
                    features.append(found + np.array([x, y], np.float32))
        self._points = np.concatenate(features) if features else None
        if old is None or points is None or len(points) < 20:
            return None
        tracked, status, _ = cv2.calcOpticalFlowPyrLK(
            old, gray, points, None, winSize=(21, 21), maxLevel=3
        )
        if tracked is None:
            return None
        back, reverse, _ = cv2.calcOpticalFlowPyrLK(
            gray, old, tracked, None, winSize=(21, 21), maxLevel=3
        )
        if back is None:
            return None
        good = (
            (status.ravel() > 0)
            & (reverse.ravel() > 0)
            & (np.linalg.norm(back - points, axis=2).ravel() < 0.7)
        )
        source, target = points[good, 0], tracked[good, 0]
        if len(source) < 20:
            return None
        transform, inliers = cv2.findHomography(source, target, cv2.RANSAC, 1.2)
        if transform is None or inliers is None:
            return None
        keep = inliers.ravel() > 0
        if keep.sum() < 20 or keep.mean() < 0.7:
            return None
        supported = source[keep]
        if (
            np.ptp(supported[:, 0]) < 200
            or np.ptp(supported[:, 1]) < 330
            or cv2.contourArea(cv2.convexHull(supported)) < 400 * 640 * 0.22
        ):
            return None
        control = np.array([[0, 0], [399, 0], [399, 639], [0, 639]], np.float32)
        moved = cv2.perspectiveTransform(control[None], transform)[0]
        if (
            not np.isfinite(moved).all()
            or np.max(np.linalg.norm(moved - control, axis=1)) > 25
        ):
            return None
        scale = np.diag([2.0, 2.0, 1.0])
        return scale @ transform @ np.linalg.inv(scale)
