"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.pipeline.preview_worker`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.pipeline import preview_worker as _implementation

sys.modules[__name__] = _implementation
