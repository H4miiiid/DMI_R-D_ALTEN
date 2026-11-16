"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.pipeline.frame_processor`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.pipeline import frame_processor as _implementation

sys.modules[__name__] = _implementation
