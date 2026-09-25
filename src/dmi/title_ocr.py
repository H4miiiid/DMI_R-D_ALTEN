"""Read title text with an external, general English OCR model (Tesseract).

No vocabulary hints, supplied answers or recording-derived templates are fed
to OCR. Only confident exact recognized titles select a supported UI layout.
"""
from __future__ import annotations

import csv
import io
import shutil
import subprocess

import cv2

from dmi.geometry import Frame


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


def _recognize(executable: str, prepared: Frame) -> str | None:
    ok, encoded = cv2.imencode(".png", prepared)
    if not ok:
        return None
    try:
        result = subprocess.run(
            [executable, "stdin", "stdout", "-l", "eng", "--psm", "7", "tsv"],
            input=encoded.tobytes(), capture_output=True, timeout=5, check=True,
        )
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Tesseract title OCR failed: " +
                           exc.stderr.decode(errors="replace").strip()) from exc
    words = [row for row in csv.DictReader(io.StringIO(result.stdout.decode()),
                                          delimiter="\t")
             if row.get("level") == "5" and row.get("text", "").strip()]
    if not words or min(float(row["conf"]) for row in words) < 65:
        return None
    return " ".join(row["text"].strip() for row in words)


def title_state(text: str | None) -> str:
    """Map recognized UI vocabulary; unsupported text never guesses a layout."""
    normalized = " ".join((text or "").casefold().split())
    return {"main": "Main", "driver id": "Driver ID", "level": "Level"}.get(
        normalized, "unknown"
    )
