"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.temporal.left_tracking`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.temporal import left_tracking as _implementation

sys.modules[__name__] = _implementation
