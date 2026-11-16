"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.shared.utils.image_ops`; implementation is shared."""
import sys

from dmi_computer_vision.src.dmi.shared.utils import image_ops as _implementation

sys.modules[__name__] = _implementation
