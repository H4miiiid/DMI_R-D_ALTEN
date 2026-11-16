"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.robot_session`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import robot_session as _implementation

sys.modules[__name__] = _implementation
