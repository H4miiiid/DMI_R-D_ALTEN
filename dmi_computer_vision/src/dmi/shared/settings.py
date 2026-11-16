"""Immutable vision choices; source geometry still determines applicability."""
from dataclasses import dataclass


@dataclass(frozen=True)
class VisionSettings:
    contrast_fallback: bool = False
