"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.pressing`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import pressing as _implementation

sys.modules[__name__] = _implementation
