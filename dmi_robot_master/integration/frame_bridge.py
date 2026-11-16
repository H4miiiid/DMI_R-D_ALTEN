"""Compatibility import for :mod:`dmi_robot_master.integration.shared.acquisition.frame_bridge`; implementation is shared."""
import sys

from dmi_robot_master.integration.shared.acquisition import frame_bridge as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
