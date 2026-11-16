"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.visibility`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import visibility as _implementation

sys.modules[__name__] = _implementation
