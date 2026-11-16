"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.physical_press`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import physical_press as _implementation

sys.modules[__name__] = _implementation
