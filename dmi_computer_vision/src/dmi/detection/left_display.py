"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.left_display`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import left_display as _implementation

sys.modules[__name__] = _implementation
