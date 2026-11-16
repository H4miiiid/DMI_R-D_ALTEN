"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.right_display`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import right_display as _implementation

sys.modules[__name__] = _implementation
