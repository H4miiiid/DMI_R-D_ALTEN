"""Session-owned SENSE acceleration, without retained recognition evidence."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import ctypes
import ctypes.util
from pathlib import Path
import shutil
import subprocess
import weakref

import numpy as np

_CURRENT: ContextVar[AnalysisSession | None] = ContextVar("dmi_analysis_session", default=None)


def select_connected(connected: bool) -> None:
    """Image-derived localization selects acceleration; camera index never does."""
    session = _CURRENT.get()
    if session is not None:
        session.connected = connected


def current_session() -> AnalysisSession | None:
    session = _CURRENT.get()
    return session if session is not None and session.connected else None


class AnalysisSession:
    """One processor owns one OCR engine. Every call still reads current pixels.

    Library/model availability falls back to the existing command-line reader.
    No recognized text, coordinates, evidence ages or confirmations are cached.
    """
    def __init__(self) -> None:
        self.connected = False
        self._attempted = False
        self._ocr: _Tesseract | None = None

    @contextmanager
    def frame(self):
        self.connected = False
        token = _CURRENT.set(self)
        try:
            yield
        finally:
            self.connected = False
            _CURRENT.reset(token)

    def recognize(self, image: np.ndarray, page_segmentation: int) -> str | None:
        if not self._attempted:
            self._attempted = True
            try:
                self._ocr = _Tesseract()
            except (OSError, AttributeError, RuntimeError):
                self._ocr = None
        return self._ocr.recognize(image, page_segmentation) if self._ocr is not None else None

    def close(self) -> None:
        if self._ocr is not None:
            self._ocr.close()
        self._ocr = None
        self._attempted = False


class _Tesseract:
    """Existing Tesseract C API, same English model/PSM and five-second deadline."""
    def __init__(self) -> None:
        executable = shutil.which("tesseract")
        if executable is None:
            raise OSError("Tesseract is not installed")
        prefix = Path(executable).resolve().parent.parent
        candidates = [prefix / "lib" / name for name in
                      ("libtesseract.dylib", "libtesseract.so", "libtesseract.so.5")]
        library = next((str(p) for p in candidates if p.is_file()), None)
        library = library or ctypes.util.find_library("tesseract")
        if library is None:
            raise OSError("Tesseract shared library is unavailable")
        self.lib = ctypes.CDLL(library)
        self.lib.TessVersion.argtypes = []
        self.lib.TessVersion.restype = ctypes.c_char_p
        try:
            version = subprocess.run([executable, "--version"], capture_output=True,
                                     text=True, check=True, timeout=5).stdout.splitlines()[0].split()[1]
        except (subprocess.SubprocessError, IndexError) as exc:
            raise OSError("Cannot verify the installed OCR version") from exc
        if self.lib.TessVersion().decode() != version:
            raise OSError("OCR library and command-line versions differ")
        pointer, integer = ctypes.c_void_p, ctypes.c_int
        signatures = {
            "TessBaseAPICreate": ([], pointer),
            "TessBaseAPIInit3": ([pointer, ctypes.c_char_p, ctypes.c_char_p], integer),
            "TessBaseAPISetPageSegMode": ([pointer, integer], None),
            "TessBaseAPISetImage": ([pointer, pointer, integer, integer, integer, integer], None),
            "TessBaseAPIRecognize": ([pointer, pointer], integer),
            "TessBaseAPIGetTsvText": ([pointer, integer], pointer),
            "TessBaseAPIClear": ([pointer], None),
            "TessBaseAPIClearAdaptiveClassifier": ([pointer], None),
            "TessBaseAPIDelete": ([pointer], None),
            "TessDeleteText": ([pointer], None),
            "TessMonitorCreate": ([], pointer),
            "TessMonitorSetDeadlineMSecs": ([pointer, integer], None),
            "TessMonitorDelete": ([pointer], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = arguments, result
        self.handle = self.lib.TessBaseAPICreate()
        if not self.handle:
            raise RuntimeError("Cannot create Tesseract engine")
        self._delete = weakref.finalize(self, self.lib.TessBaseAPIDelete, self.handle)
        if self.lib.TessBaseAPIInit3(self.handle, None, b"eng"):
            self.close()
            raise RuntimeError("Cannot initialize English OCR")

    def recognize(self, image: np.ndarray, page_segmentation: int) -> str:
        # The current reader supplies a prepared grayscale uint8 image.
        image = np.ascontiguousarray(image, dtype=np.uint8)
        if image.ndim != 2:
            raise ValueError("OCR input must be grayscale")
        monitor = self.lib.TessMonitorCreate()
        if not monitor:
            raise RuntimeError("Cannot create OCR deadline monitor")
        text = None
        try:
            self.lib.TessBaseAPIClearAdaptiveClassifier(self.handle)
            self.lib.TessBaseAPISetPageSegMode(self.handle, page_segmentation)
            self.lib.TessBaseAPISetImage(self.handle, image.ctypes.data,
                image.shape[1], image.shape[0], 1, image.strides[0])
            self.lib.TessMonitorSetDeadlineMSecs(monitor, 5000)
            if self.lib.TessBaseAPIRecognize(self.handle, monitor):
                return ""  # Timeout/failed recognition supplies no evidence.
            text = self.lib.TessBaseAPIGetTsvText(self.handle, 0)
            return ctypes.string_at(text).decode("utf-8") if text else ""
        finally:
            if text:
                self.lib.TessDeleteText(text)
            self.lib.TessMonitorDelete(monitor)
            self.lib.TessBaseAPIClear(self.handle)

    def close(self) -> None:
        if self.handle:
            self._delete()
            self.handle = None
