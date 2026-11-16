"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.icons`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import icons as _implementation

sys.modules[__name__] = _implementation
