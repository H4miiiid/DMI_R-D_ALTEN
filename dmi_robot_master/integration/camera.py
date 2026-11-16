"""Compatibility import for :mod:`dmi_robot_master.integration.shared.acquisition.camera`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.acquisition import camera as _implementation

sys.modules[__name__] = _implementation
