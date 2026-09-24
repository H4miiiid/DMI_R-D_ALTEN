"""Conservative asset matching inside image-supported left-display regions.

Templates come only from supplied assets. Every box is searched independently;
no box identity, video metadata, or previous classification supplies an answer.
"""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

ASSET_DIRECTORY = Path(__file__).resolve().parents[2] / "data/icons/levels"


def recognize_icons(frame: np.ndarray, boxes: dict) -> dict[str, str | None]:
    """Recognize full icon silhouettes after rectifying each local box."""
    templates = _templates()
    return {name: _recognize(_rectify_region(frame, quad), templates)
            for name, quad in boxes.items()}


def _rectify_region(frame: np.ndarray, quad: np.ndarray) -> np.ndarray:
    width = max(3, round(float(np.linalg.norm(quad[1] - quad[0]))))
    height = max(3, round(float(np.linalg.norm(quad[3] - quad[0]))))
    target = np.array([[0, 0], [width - 1, 0],
                       [width - 1, height - 1], [0, height - 1]], np.float32)
    transform = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
    return cv2.warpPerspective(frame, transform, (width, height))[1:-1, 1:-1]


def _foreground(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    threshold = float(np.percentile(gray, 20)) + 0.65 * (float(gray.max()) - float(np.percentile(gray, 20)))
    _, bright = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    neutral = cv2.inRange(hsv, (0, 0, 90), (179, 150, 255))
    return cv2.bitwise_and(bright, neutral)


def _normalize(mask: np.ndarray) -> np.ndarray:
    y, x = np.where(mask > 0)
    crop = mask[y.min():y.max() + 1, x.min():x.max() + 1]
    vector = cv2.resize(crop, (96, 40), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    vector -= vector.mean()
    return vector / max(float(np.linalg.norm(vector)), 1e-6)


@lru_cache(maxsize=1)
def _templates() -> dict[str, list[np.ndarray]]:
    templates = {}
    for path in sorted(ASSET_DIRECTORY.glob("*.bmp")):
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"Cannot read icon asset: {path}")
        mask = _foreground(image)
        if not np.any(mask):
            raise RuntimeError(f"Icon asset has no foreground: {path}")
        # Camera bloom thickens strokes. These generic variants retain the
        # digit and bar pattern rather than learning a particular video crop.
        templates[path.stem] = [
            _normalize(cv2.dilate(mask, np.ones((size, size), np.uint8)))
            for size in (1, 2, 3)
        ]
    if not templates:
        raise RuntimeError(f"No icon assets found in {ASSET_DIRECTORY}")
    return templates


def _recognize(image: np.ndarray, templates: dict) -> str | None:
    mask = _foreground(image)
    if not np.any(mask):
        return None
    # Join separated digit/bar components at the canonical left-display scale.
    joined = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 17), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(joined)
    matches = []
    for x, y, width, height, _ in stats[1:]:
        if width < 15 or height < 8 or not 1.4 < width / height < 4:
            continue
        candidate = mask[y:y + height, x:x + width]
        if not np.any(candidate):
            continue
        vector = _normalize(candidate)
        scores = sorted(((max(float(vector @ variant) for variant in variants), name)
                         for name, variants in templates.items()), reverse=True)
        best, name = scores[0]
        runner_up = scores[1][0] if len(scores) > 1 else -1
        if best >= 0.75 and best - runner_up >= 0.045:
            matches.append(name)
    # The output contract has one identity per box; ambiguous multiplicity
    # must not be silently reduced to whichever component was visited last.
    return matches[0] if len(matches) == 1 else None
