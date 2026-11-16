"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.output.latest_state`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.output import latest_state as _implementation

sys.modules[__name__] = _implementation
