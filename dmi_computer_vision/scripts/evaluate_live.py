#!/usr/bin/env python3
"""Entry point for DMI live replay evaluation."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dmi_computer_vision.src.dmi.evaluation.live_replay import main  # noqa: E402


if __name__ == "__main__":
    main()
