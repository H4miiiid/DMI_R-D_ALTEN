"""Shared comparison provenance for the selected, explicitly configured version."""
from hashlib import sha256
import json
from pathlib import Path

from dmi_robot_master.integration.version_selection import VERSIONS, resolve_version, validate_version
# Accepted Phase 0 source snapshot, not a runtime dependency on local evidence.
BASELINE_SOURCE_FINGERPRINT = "c44696f4d50a43c35ae58c4fbc93cbd1a09c4d001eb136c4fd13979184334578"
ROOT = Path(__file__).resolve().parents[3]


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
    policy = resolve_version(version)
    files = []
    for directory in ("TapperWare_Flet", "dmi_computer_vision/src/dmi",
                      "dmi_robot_master/integration", "dmi_robot_common"):
        files.extend(p for p in (ROOT / directory).rglob("*.py")
                     if "tests" not in p.relative_to(ROOT).parts)
    files.extend(p for p in (ROOT / "dmi_computer_vision/data/icons").rglob("*")
                 if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"})
    files.append(ROOT / "TapperWare_Flet/DmiPositions.json")
    files.append(ROOT / "dmi_robot_master/integration/v2/screen_profiles.json")
    hashes = {str(p.relative_to(ROOT)): file_fingerprint(p) for p in sorted(files)}
    fingerprint = sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"selected_version": version, "source_fingerprint": fingerprint,
            "source_fingerprint_scope": "GUI/integration/vision/common Python, icon images, DmiPositions.json, screen_profiles.json; excludes tests/local data",
            "source_files_sha256": hashes,
            "source_fingerprint_complete": all(value is not None for value in hashes.values()),
            "baseline_source_fingerprint": BASELINE_SOURCE_FINGERPRINT,
            "enabled_improvements": list(policy.enabled_improvements),
            "improvement_scope": "SENSE connected geometry only; TWIN retains baseline in both versions",
            "settings": {"optimize": True, "max_gap_seconds": 1.0, "stable_preview": True,
                         "processing": ("ROI checks with bounded full audits" if policy.selective_updates
                                        else "full detection per consumed frame"), "rotation_clockwise": 0,
                         "mirror_horizontal": False, "contrast_fallback": policy.vision.contrast_fallback,
                         "progressive_layout_lock": policy.progressive_lock,
                         "lock_confirmation_frames": 3, "lock_window_observations": 5,
                         "lock_scope": "JSON-profiled SENSE geometry; experimental destinations require independent full evidence",
                         "selective_updates": policy.selective_updates, "full_audit_seconds": 1.,
                         "stable_coordinates": policy.progressive_lock, "movement_confirmation_frames": 3,
                         "stable_registration": policy.stable_registration, "registration_confirmation_frames": 3,
                         "registration_scope": "experimental recorded SENSE mapping; no calibration promotion",
                         "alignment_recovery": policy.recover_alignment,
                         "experimental_monitor_tolerance_px": 20 if policy.recover_alignment else 4,
                         "experimental_allow_unverified_left": policy.allow_unverified_left,
                         "locked_actions": policy.locked_actions,
                         "experimental_action_match_px": 10 if policy.locked_actions else 4,
                         "experimental_action_evidence_seconds": 2. if policy.locked_actions else 1.5,
                         "movement_reference": "original lock baseline; presentation only",
                         "partial_retry_seconds": .5, "field_refresh_seconds": 1.}}
