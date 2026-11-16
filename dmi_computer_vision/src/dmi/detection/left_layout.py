"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.left_layout`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import left_layout as _implementation

sys.modules[__name__] = _implementation
