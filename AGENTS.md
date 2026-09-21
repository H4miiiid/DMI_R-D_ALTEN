# AGENTS.md — DMI Video Screen Understanding

## Mission

Build a reliable video-processing pipeline that understands the physical two-display interface shown in the recorded webcam videos.

The current videos under `data/videos/dev/` represent the same kind of input the final system must process.

Recorded-video processing comes first. The same core pipeline should later support live webcam frames without requiring a redesign.

Priority order:

1. correctness
2. geometry and detection accuracy
3. recognition and OCR accuracy
4. temporal stability
5. maintainability
6. performance

---

## Documentation

Keep this file short.

Detailed project knowledge belongs in:

- `docs/PROJECT.md` — project goals, inputs, scope, constraints
- `docs/UI_SPEC.md` — displays, UI states, elements, geometry, temporal behavior
- `docs/OUTPUT_SPEC.md` — JSON structure and coordinate conventions
- `docs/EVALUATION.md` — references, metrics, testing, regression rules
- `docs/WORKFLOW.md` — development phases and phase gates
- `docs/STATE.md` — current verified implementation state

When continuing existing work, read `docs/STATE.md` first.

Read only the other documentation relevant to the current task. Do not load every document unnecessarily.

---

## Input Data

Original project data is under `data/`.

Current development videos:

`data/videos/dev/`

Visual examples:

`data/reference/overlays/`

Known icon assets:

`data/icons/`

Do not modify original input assets.

Visual overlays are references only. They are not automatically numerical ground truth.

Do not fabricate annotation files or verified coordinates when ground truth does not exist.

Pipeline predictions must never automatically become ground truth.

---

## Understand Before Implementing

Do not assume a predefined:

- detection method
- alignment method
- tracking method
- OCR method
- stabilization method
- bounding-box strategy

Inspect the actual videos, interface behavior, visual references, and assets before choosing an approach.

Base implementation decisions on observed data and measured results.

Different parts of the interface may use different techniques when justified.

Prefer the simplest solution that provides equivalent reliability.

---

## No Video-Specific Hardcoding

Do not hardcode production behavior only to make the current videos or reference images pass.

Do not embed:

- known OCR answers
- frame-specific expected coordinates
- results based on video filenames
- manually encoded icon assignments
- special cases that exist only for one known reference frame

Reference material is for understanding and evaluation, not for bypassing detection.

When numerical ground truth is incomplete or unavailable, evaluation may also include visual inspection of generated annotated videos or frames. In these cases, ask the user to review the output and provide feedback on alignment, detections, OCR, labels, or other visible issues.

Treat this user feedback as evaluation evidence, not as permission to hardcode fixes for individual frames or videos.

---

## Frame-Source Independence

Keep frame acquisition separate from screen-understanding logic.

Core processing should operate on image frames regardless of whether they come from:

- a prerecorded video
- another future video
- a live webcam

Do not tightly couple detection logic to the current MP4 files.

---

## Code Organization

Production code belongs under:

`src/dmi/`

Scripts under `scripts/` are entry points and utilities.

Current intended entry points are:

- `scripts/run_video.py`
- `scripts/evaluate.py`
- `scripts/benchmark.py`

Keep these scripts focused on orchestration. Do not place the full computer-vision implementation inside them.

`src/dmi/pipeline.py` should coordinate the main processing flow. It must not become a monolithic implementation containing the entire project.

Split substantial responsibilities into focused modules when needed.

Possible responsibilities may include:

- geometry
- right-display processing
- left-display processing
- OCR
- temporal logic
- output formatting
- visualization

These are examples, not required filenames or required architectural choices.

---

## Avoid Monolithic Files

Prefer a small number of cohesive Python modules.

Do not put thousands of lines of unrelated logic into one file.

As a guideline:

- when a production file approaches roughly 400–500 lines, reconsider whether it contains multiple responsibilities
- files substantially above roughly 700 lines should have a clear justification
- do not split code only to satisfy a line-count target

Avoid the opposite extreme as well: do not create dozens of tiny files or unnecessary abstraction layers.

Use Git history instead of keeping files such as:

- `detector_v2.py`
- `pipeline_new.py`
- `final_fixed.py`

---

## Development Style

Work incrementally.

For each substantial step:

1. inspect the relevant data
2. understand the requirement or failure
3. implement the smallest coherent change
4. test representative cases
5. inspect structured output
6. inspect visual output when geometry is involved
7. check previously working behavior
8. measure performance when relevant
9. update `docs/STATE.md`

Do not build later stages on top of unreliable earlier stages.

If a solution requires repeated special-case patches, reconsider the underlying design.

---

## Evaluation and Regression

Do not consider a change successful only because:

- the program runs
- one frame looks correct
- one video works
- the overlay looks visually good

Use measurable evaluation whenever verified references are available.

After significant changes, recheck previously working cases.

Do not accept an improvement for one case that creates larger unexplained regressions elsewhere.

Detailed metrics and acceptance criteria belong in `docs/EVALUATION.md`.

---

## Geometry and Uncertainty

Do not assume that screen elements always remain at identical pixel coordinates.

The final system must eventually tolerate reasonable variation in:

- screen position
- scale
- camera position
- small rotation
- perspective
- lighting

When reliable information is unavailable, prefer an explicit unknown or `null` result over a fabricated detection.

Do not produce confident:

- text
- coordinates
- icons
- field values
- UI states

without sufficient evidence.

Detailed geometry and output rules belong in `docs/UI_SPEC.md` and `docs/OUTPUT_SPEC.md`.

---

## Generated Outputs

Keep generated results separate from original data.

Do not overwrite files under `data/`.

Generated JSON, annotated videos, debug images, benchmarks, and temporary artifacts should go into dedicated output locations when those outputs are introduced.

Do not allow temporary debugging files to accumulate permanently in the repository.

---

## STATE.md

`docs/STATE.md` must remain a concise snapshot of the current verified state.

It should contain only useful continuation context such as:

- current development phase
- implemented functionality
- latest verified results
- known problems
- important architectural facts
- next task

Do not use it as a chronological diary.

Replace outdated information rather than continuously appending history.

Git already preserves history.

---

## Documentation Ownership

When project knowledge changes, update the document that owns that information.

- project scope → `PROJECT.md`
- UI behavior → `UI_SPEC.md`
- output structure → `OUTPUT_SPEC.md`
- evaluation rules → `EVALUATION.md`
- development process → `WORKFLOW.md`
- current progress → `STATE.md`

Avoid duplicating the same rule across multiple documents.

---

## Performance

The final target is real-time webcam processing.

Keep the pipeline fast and lightweight while preserving correctness and accuracy. Consider computational cost when choosing techniques, avoid unnecessary repeated work, and do not run expensive operations on every frame when an equally reliable lighter approach is possible.

Measure performance rather than assuming an approach is fast. Detailed performance targets belong in `docs/EVALUATION.md`.

---

## Git Workflow

After each completed and verified development phase:

1. review the changes
2. update `docs/STATE.md`
3. commit with a clear message
4. push the commit to the remote repository

Do not commit or push incomplete, broken, temporary, or unverified work.

If a phase requires visual user validation, commit and push only after the user approves the result or accepts the remaining limitations.

---

## Definition of Done

A substantial development step is complete only when:

- the intended behavior is implemented
- relevant checks pass
- representative input has been processed
- geometry is visually inspected when applicable
- user review is requested when visual correctness cannot be fully verified automatically
- user feedback is addressed when provided
- important regressions are checked
- limitations are reported honestly
- `docs/STATE.md` is updated when the verified state changes

Do not declare a task complete only because code was written or automated checks passed.

When user validation is required for a visual result, do not mark the step complete until the user has reviewed and approved the output or explicitly accepted the remaining limitations.

---

## Core Rule

The objective is not to demonstrate a particular computer-vision technique.

The objective is to build the most reliable, maintainable, and efficient pipeline possible for understanding the real interface shown in the input videos.
