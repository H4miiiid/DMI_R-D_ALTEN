"""Reviewed SENSE extensions; selecting these never authorizes hardware."""
from dmi_computer_vision.src.dmi.v2.settings import SETTINGS
from dmi_robot_master.integration.shared.version_policy import VersionPolicy

POLICY = VersionPolicy(
    vision=SETTINGS, progressive_lock=True, selective_updates=True,
    locked_actions=True, stable_registration=True, recover_alignment=True,
    allow_unverified_left=True,
    enabled_improvements=(
        'sense_field_contrast_fallback', 'sense_progressive_layout_lock',
        'sense_selective_updates', 'sense_stable_coordinates',
        'sense_session_registration', 'sense_locked_action_destination',
    ),
)
