# STATE.md — Current Project State

## Purpose

This file records the current verified development phase and a short technical summary of completed phases.

Keep it concise and update it as the project progresses.

Do not use it as a detailed development diary.

---

## Current Phase

**Phase 4 — Right Display**

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

For each completed phase, briefly record:

- phase name
- status: `Completed`
- main files created or modified
- important functions, methods, or components implemented
- key verified result
- important remaining limitation, only if the next phase needs to know it

Example:

```text
### Phase 2 — Basic Processing Pipeline — Completed

Files:
- src/dmi/pipeline.py
- scripts/run_video.py

Implemented:
- process_frame()
- video frame loop
- JSON result generation
- annotated video output

Verified:
- representative development videos process from start to finish

Limitation:
- UI detection is not implemented yet
```

Keep each completed-phase summary short.

---

## After Completing a Phase

When the current phase is verified:

1. move it to `Completed Phases`
2. mark it as `Completed`
3. briefly record the important files, functions, methods, or components added or changed
4. record the main verified result and any important limitation
5. set the next phase from `docs/WORKFLOW.md` as the new `Current Phase`
6. keep this file concise
7. follow the Git workflow in `AGENTS.md`

Do not advance to the next phase until the current phase satisfies its completion conditions.
