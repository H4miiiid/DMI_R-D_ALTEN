"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.detection.analysis_session`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.detection import analysis_session as _implementation

sys.modules[__name__] = _implementation
