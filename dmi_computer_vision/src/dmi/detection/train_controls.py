"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.train_controls`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import train_controls as _implementation

sys.modules[__name__] = _implementation
