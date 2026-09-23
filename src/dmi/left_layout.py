"""Image-supported border fitting for the left display's logical topology."""
from __future__ import annotations

import cv2
import numpy as np

Line = tuple[float, float]  # dependent = slope * independent + intercept


class BorderEvidence:
    """Blue-channel gradients, excluding bright glyphs and icons."""

    def __init__(self, frame: np.ndarray) -> None:
        blue = cv2.GaussianBlur(frame[:, :, 0].astype(np.float32), (5, 5), 1)
        # Relative contrast preserves faint borders when exposure drops.
        blue = 80 * np.log1p(blue / 12)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        foreground = ((hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 70)).astype(np.uint8)
        foreground = cv2.dilate(foreground, np.ones((9, 9), np.uint8))
        self.horizontal = np.abs(cv2.Sobel(blue, cv2.CV_32F, 0, 1))
        self.vertical = np.abs(cv2.Sobel(blue, cv2.CV_32F, 1, 0)).T
        self.horizontal[foreground > 0] = 0
        self.vertical[foreground.T > 0] = 0

    def fit(
        self,
        axis: str,
        position: float,
        cross: float,
        start: float,
        end: float,
        *,
        radius: float = 10,
        slope: float = 0,
        slope_radius: float = 0.025
    ) -> Line | None:
        """Search line position/orientation, then robustly fit local edge maxima.

        A majority of samples must support a border. No predicted line is
        returned when the image does not support it.
        """
        response = self.horizontal if axis == "h" else self.vertical
        xs = np.linspace(start, end, 64, dtype=np.float32)
        slopes = np.linspace(
            slope - slope_radius,
            slope + slope_radius,
            max(3, int(slope_radius * (end - start)) + 1),
        )
        offsets = np.arange(-radius, radius + 0.5, 1)
        yy = (
            position
            + offsets[:, None, None]
            + slopes[None, :, None] * (xs[None, None, :] - cross)
        )
        xx = np.broadcast_to(xs, yy.shape)
        values = cv2.remap(
            response,
            xx.reshape(-1, 64),
            yy.astype(np.float32).reshape(-1, 64),
            cv2.INTER_LINEAR,
        )
        # A clipped mean rewards coverage, not a few high-contrast pixels.
        scores = np.mean(
            np.minimum(values, np.quantile(values, 0.45, axis=1)[:, None]), axis=1
        )
        best = int(np.argmax(scores))
        if scores[best] < max(0.8, float(np.median(scores)) * 1.35):
            return None
        predicted = yy.reshape(-1, 64)[best]
        nearby = predicted[None, :] + np.arange(-3, 4)[:, None]
        sampled = cv2.remap(
            response,
            np.broadcast_to(xs, nearby.shape),
            nearby.astype(np.float32),
            cv2.INTER_LINEAR,
        )
        maxima = sampled.argmax(axis=0)
        ys = nearby[maxima, np.arange(64)]
        strength = sampled[maxima, np.arange(64)]
        keep = strength > max(0.8, float(np.median(strength)) * 0.35)
        if keep.sum() < 35:
            return None
        fit = np.polyfit(xs[keep], ys[keep], 1)
        for _ in range(2):
            keep &= np.abs(ys - np.polyval(fit, xs)) < 3
            if keep.sum() < 30:
                return None
            fit = np.polyfit(xs[keep], ys[keep], 1)
        if abs(np.polyval(fit, cross) - position) > radius + 3:
            return None
        return float(fit[0]), float(fit[1])


def position(line: Line, cross: float) -> float:
    return line[0] * cross + line[1]


def intersection(vertical: Line, horizontal: Line) -> tuple[float, float]:
    a, b = vertical
    c, d = horizontal
    y = (c * b + d) / (1 - c * a)
    return a * y + b, y


def quad(left: Line, right: Line, top: Line, bottom: Line) -> np.ndarray:
    return np.array(
        [
            intersection(left, top),
            intersection(right, top),
            intersection(right, bottom),
            intersection(left, bottom),
        ],
        np.float32,
    )


def consistent_sidebar(rows: list[Line], cross: float) -> bool:
    """Reject noise peaks that do not preserve the observed row topology."""
    heights = np.diff([position(row, cross) for row in rows])
    unit = float(np.median(heights[2:]))
    return bool(
        unit > 0
        and 1.65 * unit < heights[0] < 2.55 * unit
        and 8 * unit < heights[1] < 10.5 * unit
        and np.all((heights[2:] > 0.7 * unit) & (heights[2:] < 1.3 * unit))
    )


def valid_quad(points: np.ndarray) -> bool:
    """Do not emit crossed, collapsed, or numerically invalid regions."""
    return bool(
        np.isfinite(points).all()
        and cv2.isContourConvex(points)
        and cv2.contourArea(points, oriented=True) > 64
        and np.min(np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)) > 8
    )


def sidebar_borders(evidence: BorderEvidence) -> tuple[Line, list[Line]] | None:
    """Find the sidebar divider and its 2, 9, 1, ... unit row topology.

    Relative row heights identify the UI structure; all reported borders are
    subsequently fitted to visible image edges, never to reference pixels.
    """
    h, w = evidence.horizontal.shape
    profile = np.median(evidence.vertical[:, int(h * 0.2) : int(h * 0.85)], axis=1)
    lo, hi = int(w * 0.07), int(w * 0.3)
    side = float(lo + np.argmax(profile[lo:hi]))
    divider = evidence.fit(
        "v", side, h / 2, h * 0.14, h * 0.9, radius=8, slope_radius=0.04
    )
    if divider is None:
        return None
    side = position(divider, h / 2)
    profile = np.median(
        evidence.horizontal[:, int(side * 0.15) : int(side * 0.8)], axis=1
    )
    profile = cv2.GaussianBlur(profile[:, None], (1, 5), 0).ravel()
    candidates = []
    work = profile.copy()
    noise_floor = max(1.2, float(np.median(profile)) * 3)
    for _ in range(40):
        i = int(work.argmax())
        if work[i] < noise_floor:
            break
        candidates.append(i)
        work[max(0, i - 15) : i + 16] = 0
    candidates = np.array(sorted(candidates))
    units = np.array([0, 2, 11, 12, 13, 14, 15, 16, 17, 18])
    best = None
    for first in candidates[(candidates > h * 0.12) & (candidates < h * 0.32)]:
        for lower in candidates[(candidates > h * 0.5) & (candidates < h * 0.72)]:
            step = (lower - first) / 9
            expected = first + (units - 2) * step
            if expected[0] < h * 0.04 or expected[-1] > h * 0.99:
                continue
            distance = np.abs(expected[:, None] - candidates)
            ids = distance.argmin(axis=1)
            errors = distance[np.arange(10), ids]
            matched = errors < step * 0.32
            if matched.sum() < 8 or not matched[:4].all():
                continue
            score = (
                matched.sum() * 4
                - np.minimum(errors / step, 1).sum()
                + np.log1p(profile[candidates[ids]] / noise_floor).sum()
            )
            if best is None or score > best[0]:
                best = score, expected, step
    if best is None:
        return None
    _, expected, step = best
    borders = []
    for y in expected:
        border = evidence.fit(
            "h",
            y,
            side / 2,
            side * 0.13,
            side * 0.82,
            radius=step * 0.32,
            slope_radius=0.12,
        )
        if border is None:
            return None
        borders.append(border)
    if not consistent_sidebar(borders, side / 2):
        return None
    return divider, borders
