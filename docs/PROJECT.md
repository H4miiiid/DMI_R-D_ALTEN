# PROJECT.md — DMI Detection V2

## Project Goal

Version 2 improves the existing DMI video-processing pipeline while keeping V1 as the working baseline.

The system must continue to process webcam-style video of the physical DMI interface and produce reliable structured results together with annotated output.

V2 focuses on:

- faster and lighter processing
- more compact and useful JSON output
- support for additional right-display screens
- support for additional icons
- stronger temporal stability
- preserving or improving detection accuracy

The final target remains real-time webcam processing using the same core pipeline.

---

## V1 Baseline

V1 already provides the main end-to-end pipeline for:

- display localization
- right-display detection
- left-display detection
- OCR
- button and field detection
- icon recognition
- temporal handling
- annotated video output
- structured JSON output
- recorded-video and webcam input

V2 should improve this existing implementation rather than rebuild working components unnecessarily.

Changes should preserve verified V1 behavior unless there is a clear reason to replace it.

---

## Development Input

Development videos are stored under:

`data/videos/dev/`

V2 adds new videos including:

- `train_data_gamma.mp4`
- `validate_train_data.mp4`
- `train_numbers.mp4`

These videos extend the current development set and introduce additional right-display states and values.

Previous V1 development videos should also remain part of V2 validation. Use them to compare detection accuracy, annotation stability, regressions, and processing speed before and after V2 changes.

Detailed UI behavior is defined in:

`docs/UI_SPEC.md`

Reference images are stored under:

`data/reference/`

Known icon assets are stored under:

`data/icons/`

Original input data must not be modified.

---

## V2 Scope

### Additional Screens

V2 should support additional right-display screens related to:

- Train Data
- Train Data validation
- Train Running Number

The pipeline must detect and annotate the relevant visible elements such as:

- titles
- buttons
- fields
- OCR values

Detailed screen definitions belong in `docs/UI_SPEC.md`.

---

### Additional Icons

New icon assets may be added to the existing icon set.

The pipeline should be extendable so that additional supported icons can be introduced without redesigning the complete icon-recognition system.

---

### Compact Output

V1 may produce large frame-level JSON output because similar information is repeated across many consecutive frames.

V2 should provide a more compact default representation while preserving the important information required by downstream users.

The exact JSON structure is defined in:

`docs/OUTPUT_SPEC.md`

Detailed per-frame output may remain available when useful for debugging or evaluation.

---

### Faster Processing

V2 should reduce unnecessary processing and improve execution speed.

The implementation should be designed for real-time-oriented use and should avoid repeatedly performing expensive operations when they are not required.

Performance improvements must be based on measurement rather than assumptions.

Performance evaluation belongs in:

`docs/EVALUATION.md`

---

### Improved Stability

V2 should reduce unnecessary frame-to-frame movement in detected UI geometry.

This includes improving stability of:

- displays
- boxes
- buttons
- fields
- center points
- OCR values
- screen states
- icons

Stabilization must still react correctly to genuine movement and UI changes.

Detailed temporal behavior belongs in:

`docs/UI_SPEC.md`.

---

## Real-Time Requirement

The final system is intended for live webcam processing.

The implementation should therefore remain:

- fast
- lightweight
- accurate
- stable

Recorded-video processing should use the same core detection logic intended for live operation.

Video and webcam input should remain separate from the screen-understanding logic.

---

## Implementation Principle

Do not choose or replace techniques only because they appear more advanced.

For every important V2 change:

- understand the current V1 behavior
- identify the actual limitation
- measure the problem when possible
- implement the simplest reliable improvement
- verify that previous behavior has not regressed

Different parts of the pipeline may use different methods when justified by the data.

---

## Generalization

V2 must not be optimized only for the currently available videos.

Avoid:

- filename-specific behavior
- frame-specific coordinates
- hardcoded OCR answers
- special cases created only to pass one reference example

The system should remain useful on future recordings of the same physical DMI interface under reasonable camera and lighting variation.

---

## Generated Outputs

Normal video processing should produce the required structured output and annotated video without overwriting source data.

Generated outputs should be stored separately from `data/`.

Long processing jobs should provide visible progress and should avoid unnecessary memory usage.

Output requirements are defined in:

`docs/OUTPUT_SPEC.md`.

---

## Engineering Priorities

Use this general priority:

1. correctness
2. stability
3. speed and efficiency
4. maintainability

A faster pipeline is not an improvement if it introduces significant detection errors.

Likewise, unnecessary expensive processing should not be kept when a lighter method provides equivalent reliability.

---

## Documentation

Detailed requirements are separated into dedicated documents:

- `AGENTS.md` — engineering and agent rules
- `docs/PROJECT.md` — V2 scope and objectives
- `docs/UI_SPEC.md` — screens, UI elements and temporal behavior
- `docs/OUTPUT_SPEC.md` — structured output format
- `docs/EVALUATION.md` — validation, regression and performance
- `docs/WORKFLOW.md` — V2 development phases
- `docs/STATE.md` — current verified project state

Avoid duplicating detailed requirements across these files.

---

## Final Objective

V2 should provide a more efficient and extensible version of the existing DMI pipeline that:

- supports the expanded UI
- produces compact structured output
- generates stable annotations
- processes videos faster
- remains accurate
- is suitable for later real-time webcam use

V1 provides the baseline; V2 should improve it through measured, verified changes.
