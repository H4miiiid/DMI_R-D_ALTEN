# STATE.md — Current Project State

## Current Phase

**Phase 6 — Icon Processing**

Phase 5 — Left Display is complete. The user visually approved the annotations
and accepted the reported limitations, then authorized committing and pushing.
Follow the Phase 6 requirements and completion conditions in `docs/WORKFLOW.md`.
Icon recognition has not yet been implemented.

## Previously Approved Functionality

Phases 1–4 are complete:

- all seven development recordings, reference overlays, and level-icon assets
  were inspected; UI and output requirements are documented
- source-independent `process_frame()` and recorded-video processing produce
  per-frame JSON and original-resolution annotated MP4s with overwrite protection
- both physical displays have perspective localization and causal stabilization;
  the user approved their annotations across all 1,708 development frames
- the right display recognizes Main, Driver ID, and Level, localizes titles,
  buttons, and data fields, reads numeric fields, and stabilizes geometry/OCR;
  the approved reference runs are in `outputs/phase4_final/`

Right-display OCR remains a numeric template matcher, not general text OCR.
There are no verified machine-readable real-video coordinates or holdout sets.

## Phase 5 — Completed and Approved

- `src/dmi/left_layout.py`: exposure-normalized blue-border evidence, suppression
  of bright glyphs, local line fitting, sidebar topology and geometry checks
- `src/dmi/left_display.py`: 22 stable identities and the speed panel, individual
  perspective borders, shared boundaries, and original-frame corners/centers
- `src/dmi/left_tracking.py`: display-relative smoothing and motion-verified
  optical-flow recovery for at most three missed frames, with loss/reset rules
- `pipeline.py`, `video.py`: integrated left processing and matching annotations
- `tests/test_left_display.py`: known synthetic corners, perspective, exposure,
  source-coordinate mapping, abstention, motion/loss, annotation consistency,
  and a real blurred-sequence regression

The physical identity mapping belongs to `docs/UI_SPEC.md`. Search priors encode
UI topology; reported borders require image evidence. No filenames, known OCR
answers, or reference-frame coordinates control production detections.
`icon` remains null until Phase 6; this is not proof that a box is empty.

## Latest Verification

- all **42 tests**, Python compilation, and `git diff --check` pass
- all **1,708 frames in seven complete videos** processed and decoded
- **1,701/1,708 frames** contain all 22 boxes and the speed panel
- every emitted region passed finite/convex geometry, enclosing-bbox, and
  center-inside-region checks; JSON and annotated-video frame counts match
- right-display JSON is unchanged from the approved Phase 4 runs in every frame
- full end-to-end processing averaged **6.01 FPS** on this run,
  including decode, annotation, encoding, and JSON writing; not yet real-time
- representative first/middle/last annotations and difficult frames were
  inspected by the agent; the user approved the visual output and accepted
  the remaining limitations

Review artifacts: `outputs/phase5_validation/` (see `README.md`).
`verification.json` records coverage/regression/timing; `integrity.json` records
geometry consistency and full-video decoding checks. Coverage is not measured
border accuracy: no real-video IoU or border-error claims are supported.

## Known Gaps and Next Task

Brief gaps during/after blur or weak border evidence remain in these frames:

- `driver_id_12`: 36, 37, 38 (zero-based frames)
- `level_0`: 26, 27, 28, 34 (zero-based frames)

Unsupported regions are omitted instead of retaining unreliable coordinates.
These brief gaps and the current performance were accepted for Phase 5.

Next: inspect the known icon assets and their video appearances, then implement
Phase 6 icon recognition and box association while preserving the approved
geometry and right-display behavior.
