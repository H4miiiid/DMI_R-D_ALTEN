# STATE.md — Current Project State

## Current Phase

**Phase 10 — complete and verified.** The CLI now runs the full pipeline with
only an input video path and creates source-named JSON and annotated MP4 files
in the repository's `outputs/<video-stem>/` directory. Optional output directories and
overwrite protection remain available. See `docs/OUTPUT_SPEC.md` for usage.

Phase 9 remains user-approved, including the documented remaining limitations.
All nine development videos were processed and reviewed in that phase.

The user expanded validation to all nine development videos on 2026-09-28.
Review deliverables: `outputs/phase9_final/README.md`. The approved two-video
Phase 8 baseline remains in `outputs/phase8_revision_final/`. Generated outputs
are local, Git-ignored; original inputs are unchanged.

## Implemented Functionality

- Frame-source-independent pipeline with perspective display localization,
  tracking, per-frame JSON and annotated video.
- Right display: general Tesseract 5 English title OCR selects Main, Driver ID
  or Level. Border-based title, field and button geometry; template numeric OCR.
  Foreground appearance gate pauses right content under obstruction and clears
  history; outer display geometry and left processing continue.
- Five-frame state confirmation, 15-frame changed numeric-value confirmation,
  and at most three missing observations retaining a field value. Unknown
  states use current regions with neutral semantics, not old screen geometry.
- Left display: 22 boxes, speed panel, motion-verified recovery up to three
  frames, and level-0/1/2 asset matching without temporal icon persistence.
- Phase 9 adds output-contract validation, exact JSON regression classification,
  annotation comparisons, finite metadata/JSON checks and video failure tests.
- Serialized outer-display bboxes now enclose both reported fitted outlines.
  Internal tracking bounds and all recognition/rendering behavior are unchanged.
  Video header frame counts are informational; these recordings' headers exceed
  their actual decoded frame counts.
- Phase 10 changes only execution/output naming; evaluation and benchmark API
  callers keep their existing per-run filenames. Recognition is unchanged.

## Latest Verification

- All 86 tests pass, including the test using an older development video and
  new CLI integration checks for directory creation, source names with spaces,
  multiple inputs, custom output directories, overwrite and missing inputs.
  Compilation and Git whitespace checks pass.
- Phase 10 path-only command processed the complete `driver_id_12.mp4`:
  233 source/annotation/JSON frames, output-contract validation passed, JSON
  exactly matches Phase 9 and annotated MP4 is byte-identical to the approved
  baseline. Outputs: `outputs/driver_id_12.json` and
  `outputs/driver_id_12_annotated.mp4`. No new visual approval is needed for
  identical annotations; existing recognition limitations remain accepted.
- The default-directory revision passes the CLI integration checks with each
  input in its own folder; explicit `--output-dir` still uses the exact supplied
  directory. The full-video evidence above predates this path-only revision.
- The following full-dataset results are retained Phase 9 evidence:
- All nine full videos processed: **3,457 frames**. Independently decoded source
  and annotation lengths match JSON. Contract validation checked 6,914 display
  geometries, 79,219 left regions and 41,912 right regions.
- Two transition videos: 1,749 frames; annotated MP4s are byte-identical to
  approved Phase 8. JSON differs only by the exact outer-display bbox correction.
- Seven steady-state videos: 1,708 frames. No retained approved JSON baseline
  exists for these seven, so comparison is explicitly unavailable, not a claim
  of zero regressions. Source/annotation samples and left icon strips inspected.
- Selected-level icon detections: level 0 in 262/264 frames, level 1 in 262/262,
  level 2 in 239/239, all associated with box_4. Counts are predictions, not
  numerical recognition ground truth.
- Right visibility pauses in 465 frames; 19 frames have incomplete left output.
  Aggregate run throughput approximately 4.24 FPS, including I/O/OCR/encoding;
  not a controlled benchmark and not real-time.

## Limitations / Review Findings

- Existing numeric matcher/temporal retention can emit incorrect text: in
  `driver_id_235`, frames 229–243 report `275` while the visible value is `235`.
  The approved transition baseline also has `275` readings; recognition code
  is unchanged. Accepted for Phase 9; remains a potential follow-up correction.
- Title uncertainty suppresses buttons for the last 20 frames of `driver_id_5`.
  `level_0_selected` frame 263 has a misplaced thin title outline above the text.
  These visual limitations were disclosed and accepted with Phase 9 approval.
- Blur can trigger conservative obstruction pauses. The gate detects appearance,
  not hand/robot identity; actual robot footage is untested (synthetic coverage
  only). Screen-colored or bright foreground objects may be missed.
- Only three layouts and three supplied icon assets are supported. General field
  OCR is unimplemented; brief numeric entries may be filtered out.
- No numerical real-video geometry ground truth or holdout set exists. Contract
  checks establish structural validity, not localization or OCR accuracy.

## Next Task

Await user instruction before starting Phase 11 — Real-Time Readiness, using
the current definition in `docs/WORKFLOW.md`.
