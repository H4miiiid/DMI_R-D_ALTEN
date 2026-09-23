# STATE.md — Current Project State

## Purpose

This file records the current verified development phase and a short technical summary of completed phases.

Keep it concise and update it as the project progresses.

Do not use it as a detailed development diary.

---

## Current Phase

**Phase 5 — Left Display**

Read and follow the corresponding phase in:

`docs/WORKFLOW.md`

Use the related project documents referenced there for requirements and completion conditions.

---

## Completed Phases

### Phase 1 — Understand the Data — Completed

Files:

- `docs/PROJECT.md`
- `docs/UI_SPEC.md`

Implemented:

- documented the development-video inventory and observed UI layouts
- reconciled the annotated left-display regions with the 22-box requirement

Verified:

- all 7 development videos open and representative frames were inspected
- all 3 reference overlays and all 3 level-icon assets were inspected
- current code and entry-point files are empty scaffolds

Limitation:

- no machine-readable ground truth or verified coordinate annotations exist

---

### Phase 2 — Basic Processing Pipeline — Completed

Files:

- `src/dmi/pipeline.py`
- `src/dmi/video.py`
- `scripts/run_video.py`
- `tests/test_pipeline.py`
- `tests/test_video.py`

Implemented:

- source-independent `process_frame()` result contract and annotation rendering
- recorded-video frame loop with JSON and annotated MP4 output
- atomic output replacement and overwrite protection

Verified:

- all 6 automated tests pass
- representative `Driver ID`, `Level`, and `Main` videos process end to end
- JSON and annotated-video frame counts match at original frame resolution

Limitation:

- display geometry and UI detections are intentionally unknown until Phase 3

---

### Phase 3 — Display Geometry — Completed

Files:

- `src/dmi/geometry.py`
- `src/dmi/temporal.py`
- `src/dmi/pipeline.py`
- `src/dmi/video.py`
- `docs/OUTPUT_SPEC.md`
- `tests/test_geometry.py`

Implemented:

- evidence-based localization of both physical displays in original-frame coordinates
- perspective quadrilaterals for rectification and detected rotated rectangles for annotation
- causal geometry stabilization with responsive reset for genuine movement

Verified:

- both displays detected in all 1,708 frames across all 7 development videos
- user approved the rotated, temporally smoothed annotations
- all 11 automated tests pass

Limitation:

- right-display state, elements, and OCR remain unknown until Phase 4

---

### Phase 4 — Right Display — Completed

Files:

- `src/dmi/right_display.py`
- `src/dmi/right_layout.py`
- `src/dmi/temporal.py`
- `src/dmi/pipeline.py`
- `src/dmi/video.py`
- `docs/OUTPUT_SPEC.md`
- `tests/test_right_display.py`

Implemented:

- `analyze_right_display()` rectifies the detected display to `600 x 960`,
  recognizes `Main`, `Driver ID`, `Level`, or `unknown`, and maps detected
  quadrilaterals back to original-frame coordinates
- button geometry uses Canny/Hough line evidence filtered by blue-border color,
  dominant orientation, length, and expected screen topology; each Main border
  keeps its directly detected slope, while Driver ID and Level use coherent
  repeated-line fitting to infer temporarily occluded grid members
- Driver ID treats the keypad and action row as separate topologies, preserving
  the distinct X, empty, TRN, and wrench divisions; Level similarly treats its
  X button separately from the 3-by-3 level grid and More button
- title geometry is fitted from its own blue/black transition bands, including
  local slope and the visible right endpoint; data fields use bright,
  low-saturation contour detection and a rotated minimum-area rectangle
- `RightDisplayStabilizer` debounces state and OCR changes, smooths the header
  separately, and tracks Driver ID/Level layouts with a robust screen-relative
  projective transform, RANSAC inlier checks, motion limits, and adaptive EMA;
  Main retains its locally detected border geometry with display-relative EMA
- numeric OCR thresholds the field, extracts connected glyph components,
  normalizes them to a fixed canvas, and correlates them with cached OpenCV
  digit templates spanning several fonts and stroke widths; Driver ID returns
  a digit sequence and Level returns the last reliable digit as `Level N`
- annotations draw perspective-aware quadrilaterals and labels, with center
  points on every right-display button and field but not on the title or the
  overall right display; unknown screens emit only border-supported cells

Verified:

- all 32 automated tests and Python compilation pass
- all 1,708 frames across the 7 development videos produce the expected stable
  state and topology: 16 buttons for Driver ID and 11 for Level/Main
- Main geometry retains the previously accepted zoom-precision behavior, while
  Driver ID and Level follow zoom and perspective without frame-specific or
  filename-specific rules
- the user visually approved the final annotated videos in
  `outputs/phase4_final/`

Limitation:

- OCR is a numeric template matcher rather than general text OCR; the supplied
  overlays are visual references rather than numerical ground truth, so new
  holdout camera conditions still require regression and visual validation
