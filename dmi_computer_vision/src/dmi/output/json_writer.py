"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.output.json_writer`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.output import json_writer as _implementation

sys.modules[__name__] = _implementation
