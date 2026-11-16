"""Compatibility import for :mod:`dmi_robot_master.integration.shared.acquisition.picamera_source`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.acquisition import picamera_source as _implementation

sys.modules[__name__] = _implementation
