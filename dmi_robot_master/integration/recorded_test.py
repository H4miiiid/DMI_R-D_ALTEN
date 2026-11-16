"""Compatibility import for :mod:`dmi_robot_master.integration.shared.projection.recorded_test`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.projection import recorded_test as _implementation

sys.modules[__name__] = _implementation
