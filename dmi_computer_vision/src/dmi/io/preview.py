"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.io.preview`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.io import preview as _implementation

sys.modules[__name__] = _implementation
