"""Resolve explicit version choices without importing CV, GUI or hardware."""
from dmi_robot_master.integration.shared.version_policy import VersionPolicy
from dmi_robot_master.integration.v1.policy import POLICY as VERSION_1
from dmi_robot_master.integration.v2.policy import POLICY as VERSION_2

VERSIONS = ('1', '2')


def validate_version(version: str) -> None:
    if version not in VERSIONS:
        raise ValueError('Choose Version 1 or Version 2')


def resolve_version(version: str) -> VersionPolicy:
    validate_version(version)
    return VERSION_1 if version == '1' else VERSION_2
