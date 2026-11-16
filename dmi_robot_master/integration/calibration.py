"""Compatibility import for :mod:`dmi_robot_master.integration.shared.calibration.calibration`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.calibration import calibration as _implementation

sys.modules[__name__] = _implementation
