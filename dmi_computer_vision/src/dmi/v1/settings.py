"""Version 1 uses the existing shared detector without the SENSE fallback."""
from dmi_computer_vision.src.dmi.shared.settings import VisionSettings

SETTINGS = VisionSettings(contrast_fallback=False)
