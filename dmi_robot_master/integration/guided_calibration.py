"""Compatibility import for :mod:`dmi_robot_master.integration.shared.calibration.guided_calibration`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.calibration import guided_calibration as _implementation

sys.modules[__name__] = _implementation
