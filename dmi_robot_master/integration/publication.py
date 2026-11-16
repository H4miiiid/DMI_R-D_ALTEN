"""Compatibility import for :mod:`dmi_robot_master.integration.shared.projection.publication`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.projection import publication as _implementation

sys.modules[__name__] = _implementation
