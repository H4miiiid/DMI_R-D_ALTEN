"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.actions`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import actions as _implementation

sys.modules[__name__] = _implementation
