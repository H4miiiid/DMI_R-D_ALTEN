"""Reviewed SENSE extensions; selecting these never authorizes hardware."""
from dmi_computer_vision.src.dmi.v2.settings import SETTINGS
from dmi_robot_master.integration.shared.version_policy import VersionPolicy

CONFIRMATION_SCREENS = frozenset({'Driver ID', 'Level', 'Train Running Number'})

POLICY = VersionPolicy(
    vision=SETTINGS, progressive_lock=True, selective_updates=True,
    freeze_on_lock=True, locked_actions=True, stable_registration=True, recover_alignment=True,
    allow_unverified_left=True,
    enabled_improvements=(
        'sense_field_contrast_fallback', 'sense_progressive_layout_lock',
        'sense_selective_updates', 'sense_stable_coordinates',
        'sense_session_registration', 'sense_locked_action_destination',
        'sense_level_activity_colour_cast', 'sense_train_measured_controls',
        'sense_freeze_until_action', 'sense_driver_id_confirmation_press', 'sense_level_trn_confirmation_press',
    ),
)
