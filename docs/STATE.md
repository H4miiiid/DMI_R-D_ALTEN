# STATE.md — Current Project State

## Current Phase

**Phase 7 — Temporal Stability**

Phases 1–6 are complete and visually approved. The user approved Phase 6,
accepted its reported limitations, and authorized committing and pushing.
Approved review artifacts: `outputs/phase6_validation/README.md`.

## Implemented Functionality

- Source-independent `process_frame()` and recorded-video processing produce
  per-frame JSON and original-resolution annotated MP4s with overwrite protection.
- Both physical displays have perspective localization and causal stabilization.
- The right display recognizes Main, Driver ID, and Level, localizes titles,
  buttons, and fields, reads numeric values, and stabilizes geometry/OCR.
  Title text comes from state classification; OCR is not general text OCR.
- The left display detects 22 stable box identities and the speed panel using
  exposure-normalized border evidence and UI topology. Motion-verified optical
  flow bridges at most three missed region measurements.
- `icons.py` rectifies each detected left box independently and compares bright
  foreground shapes with supplied level-0/1/2 assets and generic stroke-width
  variants. Match strength and separation govern abstention. No box identity,
  filename, reference-frame coordinates, or previous icon supplies the answer.
- Icon labels appear in JSON and the corresponding box annotations. `null`
  means no confident known-icon match, not verified emptiness. There is no icon
  temporal persistence, so genuine changes are not delayed by a history buffer.
- `scripts/evaluate.py` runs full-video validation against an approved baseline.

## Latest Verification

- **48 tests pass**, including synthetic icon scale/exposure/blur/perspective,
  association, negatives, multiplicity, changes/removal, and annotation checks.
  Python compilation and `git diff --check` pass.
- All **1,708 frames in seven complete videos** processed; all annotated videos
  fully decoded with frame counts matching JSON.
- **Every non-icon JSON value exactly matches the approved Phase 5 baseline**:
  display geometry, left boxes/speed panel, and all right-display results.
- All emitted left regions pass finite/convex geometry, enclosing-bbox, and
  center-inside-region checks. Complete left layouts remain **1,701/1,708**.
- Selected-level recordings: level 0 recognized in **262/264** frames, level 1
  in **262/262**, level 2 in **239/239**; each association is `box_4`.
  No known level-icon assignments occur in the other four recordings or boxes.
- Average end-to-end throughput: **5.96 FPS**, including decode, annotation,
  encoding, and JSON writing. The system is not yet real-time.
- Agent inspected first/middle/last annotations for all recordings and periodic
  source icon crops, including the uncertain opening frames. The user approved the visual output and accepted the limitations.

These are development prediction counts and regression/consistency results,
not holdout accuracy or real-video border-error measurements. There are no
verified machine-readable real-video coordinates or holdout sets.

## Known Limitations and Next Task

- Level-0 selected frames **0–1** return `icon: null` because blur makes the
  asset scores insufficiently distinct. Recognition starts at frame 2.
- Previously accepted left-layout gaps remain: `driver_id_12` frames 36–38;
  `level_0` frames 26–28 and 34. Unsupported regions are omitted.
- Only the three supplied level assets are recognized. Power/scroll symbols
  remain unsupported; low exposure, heavier blur, and unseen symbols may cause
  abstention or need additional validation. Real icon transitions are not in
  the current recordings; change/removal tests are synthetic.

Next: inspect existing stabilization and implement the smallest evidence-based
Phase 7 improvement, preserving approved geometry and recognition behavior.
