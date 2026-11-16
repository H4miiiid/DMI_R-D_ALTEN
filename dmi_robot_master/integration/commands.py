"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.commands`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import commands as _implementation

sys.modules[__name__] = _implementation
