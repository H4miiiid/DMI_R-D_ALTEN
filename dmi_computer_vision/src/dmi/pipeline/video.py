"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.pipeline.video`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.pipeline import video as _implementation

sys.modules[__name__] = _implementation
