"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.mode_observation`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared import mode_observation as _implementation

sys.modules[__name__] = _implementation
