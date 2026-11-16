"""Compatibility import for :mod:`dmi_robot_master.integration.shared.observation.vision_observer`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.observation import vision_observer as _implementation

sys.modules[__name__] = _implementation
