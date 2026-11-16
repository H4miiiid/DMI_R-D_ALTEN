"""Compatibility import for :mod:`dmi_computer_vision.src.dmi.v2.detection.field_contrast`.

Both paths resolve to one module, including mutable state and patch points.
"""
import sys

from dmi_computer_vision.src.dmi.v2.detection import field_contrast as _implementation

sys.modules[__name__] = _implementation
