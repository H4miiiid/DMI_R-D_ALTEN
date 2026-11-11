"""GUI comparison provenance and the implemented Version 2 feature selection."""
from hashlib import sha256
import json
from pathlib import Path

VERSIONS = ("1", "2")
# Accepted Phase 0 source snapshot, not a runtime dependency on local evidence.
BASELINE_SOURCE_FINGERPRINT = "c44696f4d50a43c35ae58c4fbc93cbd1a09c4d001eb136c4fd13979184334578"
ROOT = Path(__file__).resolve().parent.parent


def validate_version(version: str) -> None:
    if version not in VERSIONS:
        raise ValueError("Choose Version 1 or Version 2")


def file_fingerprint(path: str | Path | None) -> str | None:
    """Diagnostic only: unavailable mappings must not prevent pixel observation."""
    if path is None:
        return None
    try:
        digest = sha256()
        with Path(path).expanduser().open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def comparison_diagnostics(version: str) -> dict:
    """Fingerprint portable implementation and assets once per explicit start.

    This manifest has its own documented scope, distinct from Phase 0's complete
    tracked-source manifest. It never reads runs, tests or local calibration data.
    """
    validate_version(version)
    files = []
    for directory in ("TapperWare_Flet", "dmi_computer_vision/src/dmi",
                      "dmi_robot_master/integration", "dmi_robot_common"):
        files.extend(p for p in (ROOT / directory).rglob("*.py")
                     if "tests" not in p.relative_to(ROOT).parts)
    files.extend(p for p in (ROOT / "dmi_computer_vision/data/icons").rglob("*")
                 if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"})
    files.append(ROOT / "TapperWare_Flet/DmiPositions.json")
    files.append(ROOT / "dmi_robot_master/integration/screen_profiles.json")
    hashes = {str(p.relative_to(ROOT)): file_fingerprint(p) for p in sorted(files)}
    fingerprint = sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"selected_version": version, "source_fingerprint": fingerprint,
            "source_fingerprint_scope": "GUI/integration/vision/common Python, icon images, DmiPositions.json, screen_profiles.json; excludes tests/local data",
            "source_files_sha256": hashes,
            "source_fingerprint_complete": all(value is not None for value in hashes.values()),
            "baseline_source_fingerprint": BASELINE_SOURCE_FINGERPRINT,
            "enabled_improvements": ["sense_field_contrast_fallback", "sense_progressive_layout_lock",
                                     "sense_selective_updates", "sense_stable_coordinates"] if version == '2' else [],
            "improvement_scope": "SENSE connected geometry only; TWIN retains baseline in both versions",
            "settings": {"optimize": True, "max_gap_seconds": 1.0, "stable_preview": True,
                         "processing": ("ROI checks with bounded full audits" if version=='2'
                                        else "full detection per consumed frame"), "rotation_clockwise": 0,
                         "mirror_horizontal": False, "contrast_fallback": version == '2',
                         "progressive_layout_lock": version == '2',
                         "lock_confirmation_frames": 3, "lock_window_observations": 5,
                         "lock_scope": "JSON-profiled SENSE presentation only; action evidence requires full detection",
                         "selective_updates": version=='2', "full_audit_seconds": 1.,
                         "stable_coordinates": version=='2', "movement_confirmation_frames": 3,
                         "movement_reference": "original lock baseline; presentation only",
                         "partial_retry_seconds": .5, "field_refresh_seconds": 1.}}
