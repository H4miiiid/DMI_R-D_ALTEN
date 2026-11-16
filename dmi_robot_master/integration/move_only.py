"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.move_only`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import move_only as _implementation

sys.modules[__name__] = _implementation
