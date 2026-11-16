"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.display_geometry`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import display_geometry as _implementation

sys.modules[__name__] = _implementation
