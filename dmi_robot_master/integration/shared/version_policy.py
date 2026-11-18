"""Version choices passed to the single existing observer and projector."""
from dataclasses import dataclass

from dmi_computer_vision.src.dmi.shared.settings import VisionSettings


@dataclass(frozen=True)
class VersionPolicy:
    vision: VisionSettings
    progressive_lock: bool = False
    selective_updates: bool = False
    freeze_on_lock: bool = False
    locked_actions: bool = False
    stable_registration: bool = False
    recover_alignment: bool = False
    allow_unverified_left: bool = False
    enabled_improvements: tuple[str, ...] = ()

    def observer_options(self) -> dict[str, bool]:
        return dict(contrast_fallback=self.vision.contrast_fallback,
                    progressive_lock=self.progressive_lock,
                    selective_updates=self.selective_updates,
                    locked_actions=self.locked_actions, freeze_on_lock=self.freeze_on_lock)

    def projector_options(self) -> dict[str, bool]:
        """Options for the existing experimental recorded route only."""
        return dict(stable_registration=self.stable_registration,
                    recover_alignment=self.recover_alignment,
                    allow_unverified_left=self.allow_unverified_left)
