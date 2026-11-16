"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.pipeline.live`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.pipeline import live as _implementation

sys.modules[__name__] = _implementation
