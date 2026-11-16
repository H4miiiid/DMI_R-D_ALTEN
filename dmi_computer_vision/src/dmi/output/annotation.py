"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.output.annotation`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.output import annotation as _implementation

sys.modules[__name__] = _implementation
