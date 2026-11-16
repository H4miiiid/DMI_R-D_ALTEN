"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.io.latest_frames`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.io import latest_frames as _implementation

sys.modules[__name__] = _implementation
