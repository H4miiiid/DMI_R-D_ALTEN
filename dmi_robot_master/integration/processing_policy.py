"""Compatibility import for :mod:`dmi_robot_master.integration.shared.observation.processing_policy`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.observation import processing_policy as _implementation

sys.modules[__name__] = _implementation
