"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.title_ocr`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import title_ocr as _implementation

sys.modules[__name__] = _implementation
