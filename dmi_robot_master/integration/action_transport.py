"""Compatibility import for :mod:`dmi_robot_master.integration.shared.actions.action_transport`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.actions import action_transport as _implementation

sys.modules[__name__] = _implementation
