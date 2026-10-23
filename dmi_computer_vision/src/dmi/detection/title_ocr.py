"""Read title text with an external, general English OCR model (Tesseract).

No vocabulary hints, supplied answers or recording-derived templates are fed
to OCR. Only confident exact recognized titles select a supported UI layout.
"""
from __future__ import annotations

import csv
import io
import math
import shutil
import subprocess

import cv2
import numpy as np

from dmi_computer_vision.src.dmi.detection.display_geometry import Frame


def read_title(frame: Frame, box: tuple[int, int, int, int] | None) -> str | None:
    if box is None:
        return None
    executable = shutil.which("tesseract")
    if executable is None:
        raise RuntimeError("Title OCR requires Tesseract with English language data; "
                           "see docs/PROJECT.md for installation.")
    x1, y1, x2, y2 = box
    crop = frame[y1:y2, x1:x2]
    if not crop.size:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Moderate linear enlargement avoids ringing that can split letter strokes.
    enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    prepared = cv2.copyMakeBorder(255 - enlarged, 10, 10, 10, 10,
                                 cv2.BORDER_CONSTANT, value=255)
    text = _recognize(executable, prepared)
    if text is not None:
        return text
    # Remove dark margins and blue band edges before retrying difficult text.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ys, xs = (binary > 0).nonzero()
    if not len(xs):
        return None
    binary = binary[ys.min():ys.max()+1, xs.min():xs.max()+1]
    binary = cv2.resize(binary, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    prepared = cv2.copyMakeBorder(255 - binary, 10, 10, 10, 10,
                                 cv2.BORDER_CONSTANT, value=255)
    return _recognize(executable, prepared)


def read_light_title(frame: Frame, box: tuple[int, int, int, int]) -> str | None:
    """Retry detected bright glyphs without inversion or vocabulary hints."""
    executable = shutil.which("tesseract")
    if executable is None:
        raise RuntimeError("Title OCR requires Tesseract with English language data")
    x1, y1, x2, y2 = box
    height, width = frame.shape[:2]
    for margin in (10, 6):
        crop = frame[max(0, y1 - margin):min(height, y2 + margin),
                     max(0, x1 - margin):min(width, x2 + margin)]
        if not crop.size:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        binary = cv2.threshold(gray, 0, 255,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        enlarged = cv2.resize(gray, None, fx=1.5, fy=1.5,
                              interpolation=cv2.INTER_LINEAR)
        for image in (gray, binary, enlarged):
            prepared = cv2.copyMakeBorder(image, 10, 10, 10, 10,
                                         cv2.BORDER_CONSTANT, value=255)
            text = _recognize(executable, prepared)
            if title_state(text) != "unknown":
                return text
    return None


def read_field(frame: Frame, box: tuple[int, int, int, int]) -> str | None:
    """Read dark text in a bright input field without a fixed value list."""
    executable = shutil.which("tesseract")
    if executable is None:
        raise RuntimeError("Field OCR requires Tesseract with English language data")
    x1, y1, x2, y2 = box
    crop = frame[y1:y2, x1:x2]
    if not crop.size:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    prepared = cv2.copyMakeBorder(enlarged, 10, 10, 10, 10,
                                 cv2.BORDER_CONSTANT, value=255)
    text = _recognize(executable, prepared)
    if text is not None and any(character.isalnum() for character in text):
        return text
    # Pale disabled-looking text can differ from its field by only a few
    # grayscale levels. Retry with contrast set by the local field background.
    threshold = max(0, float(np.percentile(gray, 95)) - 4)
    binary = np.where(gray < threshold, 0, 255).astype(np.uint8)
    enlarged = cv2.resize(binary, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    prepared = cv2.copyMakeBorder(enlarged, 10, 10, 10, 10,
                                 cv2.BORDER_CONSTANT, value=255)
    text = _recognize(executable, prepared)
    return text if text is not None and any(character.isalnum() for character in text) else None


def read_titles(crops: list[Frame]) -> list[str | None]:
    """Read separate current text crops in one call, with per-crop confidence.

    The atlas positions identify input crops only, never control identities.
    Uncertain, multiline or cross-crop words remain unknown for a single-crop
    retry by the caller. Nothing is retained between observations.
    """
    if not crops:
        return []
    present = [i for i, crop in enumerate(crops) if crop.size]
    if len(present) != len(crops):
        results = [None] * len(crops)
        for index, text in zip(present, read_titles([crops[i] for i in present])):
            results[index] = text
        return results
    executable = shutil.which("tesseract")
    if executable is None:
        raise RuntimeError("Title OCR requires Tesseract with English language data")
    prepared = []
    for crop in crops:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        prepared.append(cv2.copyMakeBorder(255 - enlarged, 10, 10, 10, 10,
                                          cv2.BORDER_CONSTANT, value=255))
    atlas = np.full((sum(p.shape[0] for p in prepared),
                     max(p.shape[1] for p in prepared)), 255, np.uint8)
    bands = []
    top = 0
    for image in prepared:
        bottom = top + image.shape[0]
        atlas[top:bottom, :image.shape[1]] = image
        bands.append((top, bottom, image.shape[1]))
        top = bottom
    rows: list[list[dict[str, str]]] = [[] for _ in crops]
    invalid = set()
    for word in _recognize_words(executable, atlas, page_segmentation=6):
        x, y, width, height = (int(word[key]) for key in ("left", "top", "width", "height"))
        overlaps = [i for i, (start, end, _) in enumerate(bands)
                    if y < end and y + height > start]
        if len(overlaps) != 1:
            invalid.update(overlaps)
            continue
        index = overlaps[0]
        start, end, row_width = bands[index]
        if not (0 <= x < x + width <= row_width and start <= y < y + height <= end):
            invalid.add(index)
            continue
        rows[index].append(word)
    results = []
    for index, words in enumerate(rows):
        lines = {tuple(word[key] for key in ("block_num", "par_num", "line_num"))
                 for word in words}
        results.append(_confident_text(words) if index not in invalid and len(lines) == 1 else None)
    return results


def _recognize(executable: str, prepared: Frame) -> str | None:
    return _confident_text(_recognize_words(executable, prepared))


def _confident_text(words: list[dict[str, str]]) -> str | None:
    scores = [float(row["conf"]) for row in words]
    if not scores or any(not math.isfinite(score) or score < 65 for score in scores):
        return None
    return " ".join(row["text"].strip() for row in words)


def _recognize_words(
    executable: str, prepared: Frame, *, page_segmentation: int = 7,
) -> list[dict[str, str]]:
    ok, encoded = cv2.imencode(".png", prepared)
    if not ok:
        return []
    try:
        result = subprocess.run(
            [executable, "stdin", "stdout", "-l", "eng", "--psm", str(page_segmentation), "tsv"],
            input=encoded.tobytes(), capture_output=True, timeout=5, check=True,
        )
    except subprocess.TimeoutExpired:
        return []
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Tesseract title OCR failed: " +
                           exc.stderr.decode(errors="replace").strip()) from exc
    return [row for row in csv.DictReader(io.StringIO(result.stdout.decode()), delimiter="\t")
            if row.get("level") == "5" and row.get("text", "").strip()]


def title_state(text: str | None) -> str:
    """Map recognized UI vocabulary; unsupported text never guesses a layout."""
    normalized = " ".join((text or "").casefold().split())
    return {
        "main": "Main", "driver id": "Driver ID", "level": "Level",
        "train running number": "Train Running Number",
        "train data": "Train Data",
        "validate train data": "Validate Train Data",
        "train data (1/2)": "Train Data (1/2)",
        "train data (2/2)": "Train Data (2/2)",
    }.get(normalized, "unknown")
