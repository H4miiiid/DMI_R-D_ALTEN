"""Compatibility import for :mod:`dmi_robot_master.integration.shared.projection.targets`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.projection import targets as _implementation

sys.modules[__name__] = _implementation
