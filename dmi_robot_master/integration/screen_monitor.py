"""Compatibility import for :mod:`dmi_robot_master.integration.v2.screen_monitor`.

Both paths resolve to one module, including mutable state and patch points.
"""
import sys

from dmi_robot_master.integration.v2 import screen_monitor as _implementation

sys.modules[__name__] = _implementation
