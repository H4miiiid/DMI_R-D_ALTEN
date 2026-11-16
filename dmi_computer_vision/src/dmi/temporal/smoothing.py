"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.temporal.smoothing`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.temporal import smoothing as _implementation

sys.modules[__name__] = _implementation
