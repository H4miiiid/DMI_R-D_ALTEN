"""One live, explicitly confirmed short press using current calibrated coordinates.

No preceding move or alignment form is required. Calibration, source, freshness,
identity, geometry and movement limits are revalidated by the existing move plan.
Command completion never certifies physical contact or successful UI input.
"""
from dataclasses import dataclass

from dmi_robot_master.integration.move_only import MOVE_CHECKS, MovePlan

PHYSICAL_PRESS_CHECKS = MOVE_CHECKS + ('contact_sensing_checked', 'contact_routine_reviewed')
PRESS_DURATION_MS = 100


@dataclass(frozen=True)
class PhysicalPressPlan:
    target: MovePlan

    @property
    def token(self):
        return self.target.token

    @property
    def kind(self):
        return 'single_press'

    @property
    def duration_ms(self):
        return PRESS_DURATION_MS

    def preview(self):
        return {**self.target.preview(), 'action_kind': self.kind,
                'duration_ms': self.duration_ms, 'simulation_only': False,
                'commissioning_only': True, 'hardware_press_enabled': True,
                'calibration_hardware_verified': False}

    def resolve(self, observer, *, origin_epoch, limits, position=None):
        return self.target.resolve(observer, origin_epoch=origin_epoch, limits=limits,
                                   simulation=False, position=position)
