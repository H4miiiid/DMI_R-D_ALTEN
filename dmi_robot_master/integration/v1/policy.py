"""Baseline execution choices; all algorithms and guards remain shared."""
from dmi_computer_vision.src.dmi.v1.settings import SETTINGS
from dmi_robot_master.integration.shared.version_policy import VersionPolicy

POLICY = VersionPolicy(vision=SETTINGS)
