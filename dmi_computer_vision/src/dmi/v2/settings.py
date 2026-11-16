"""Version 2 enables the reviewed, image-gated SENSE field fallback."""
from dmi_computer_vision.src.dmi.shared.settings import VisionSettings

SETTINGS = VisionSettings(contrast_fallback=True)
