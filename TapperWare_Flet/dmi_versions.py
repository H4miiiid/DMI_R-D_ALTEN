"""Compatibility import for :mod:`dmi_robot_master.integration.shared.provenance`.

Both paths resolve to one module, including mutable state and patch points.
"""
import sys

from dmi_robot_master.integration.shared import provenance as _implementation

sys.modules[__name__] = _implementation
