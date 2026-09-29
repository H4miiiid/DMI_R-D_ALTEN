# AGENTS.md — DMI Detection V2

## Mission

Develop Version 2 of the DMI video-processing pipeline.

V1 is the working baseline. V2 should improve it without unnecessarily rebuilding functionality that already works.

Main V2 goals:

- faster and lighter processing
- compact and useful JSON output
- support for additional right-display screens
- support for additional icon assets
- stronger temporal stability
- maintain or improve detection accuracy

The final target remains reliable real-time webcam processing.

---

## Documentation Routing

Always read:

- `docs/STATE.md` — current phase and verified progress
- the corresponding phase in `docs/WORKFLOW.md`

Read only when relevant:

- `docs/PROJECT.md` — V2 goals and constraints
- `docs/UI_SPEC.md` — screens, UI elements, icons and temporal behavior
- `docs/OUTPUT_SPEC.md` — compact JSON and output conventions
- `docs/EVALUATION.md` — accuracy, stability and performance validation

Do not load every document unnecessarily.

---

## Development Videos

Development videos are stored under:

`data/videos/dev/`

V2 adds these new inputs:

- `train_data_gamma.mp4` — train-data input screens
- `validate_train_data.mp4` — train-data confirmation/validation screens
- `train_numbers.mp4` — train-number input screen with values such as `1`, `12`, and `128`

The pipeline must detect and annotate the relevant buttons, fields, and OCR values in these videos.

Detailed screen behavior and expected elements are defined in `docs/UI_SPEC.md`.

Do not modify the original videos or hardcode behavior from their filenames.

---

## V1 as Baseline

Treat the existing V1 implementation as a verified baseline, not disposable code.

Before changing existing behavior:

1. understand how the current implementation works
2. identify the measured problem
3. make the smallest justified improvement
4. compare V2 against the V1 behavior
5. check for regressions

Do not rewrite working components only to make the architecture look different.

---

## V2 Priorities

Use this general priority:

```text
correctness
↓
stability
↓
speed and efficiency
↓
maintainability
```

Performance improvements must not introduce important detection regressions.

At the same time, avoid unnecessarily expensive processing when a lighter method provides equivalent results.

---

## Compact JSON

The default output should contain the useful information needed by downstream users without repeating large amounts of unchanged frame-level data.

Important information includes:

- screen/state changes
- titles
- buttons and their center points
- fields and their values
- left-display boxes
- icon identities and associations
- relevant geometry
- important timestamps or frame ranges

Avoid storing identical full detection results for every frame when nothing has changed.

Prefer summarized, change-based, or interval-based representation where appropriate.

Detailed per-frame information may remain available as an optional debug output if useful.

The exact format belongs in `docs/OUTPUT_SPEC.md`.

---

## Long Video Processing

Long videos must provide visible progress.

Do not keep all results only in memory until the entire video finishes.

Where practical:

- write output incrementally
- report processing progress
- preserve already completed results if processing stops unexpectedly
- avoid unnecessary accumulation of per-frame data in memory

A user should be able to tell that a long video is actively being processed.

---

## New Right-Display Screens

V2 adds support for additional known screens, including:

- `Train Running Number`
- `Train Data`

New reference images may be stored under:

`data/reference/`

Use them to understand the visual structure of the new screens.

They are references, not fixed coordinate templates.

Detection must continue to support unknown/new screens as defined in `docs/UI_SPEC.md`.

Do not design screen detection so that adding another screen requires rewriting the complete pipeline.

---

## Icons

Additional icon assets may be added under:

`data/icons/`

Icon recognition should be driven by the available asset set where practical.

Adding a new supported icon should require minimal changes to the detection logic.

Do not hardcode icon results for specific videos, frames, or boxes.

---

## Temporal Stability

V2 should reduce visible shaking and unnecessary frame-to-frame variation.

Improve stability of:

- display geometry
- UI boxes
- button borders
- center points
- fields
- OCR values
- state recognition
- icon detection

Temporal smoothing must not hide genuine movement or UI changes.

Fix incorrect single-frame detection before attempting to hide it with smoothing.

---

## Performance

Performance is a core V2 requirement.

Measure where processing time is spent before optimizing.

Avoid unnecessary work such as:

- repeating expensive detection when the scene has not meaningfully changed
- repeated image transformations
- repeated OCR without new evidence
- repeated icon recognition on unchanged regions
- unnecessary copies or conversions
- processing data that is not needed for the final output

Reuse reliable information across frames when justified.

Do not assume an optimization is faster; measure it.

Performance results belong in `docs/EVALUATION.md`.

---

## Frame-Source Independence

Core detection logic must remain independent from frame acquisition.

The same processing components should support:

- recorded video
- live webcam

Do not create separate detection implementations for video and webcam.

---

## No Video-Specific Hardcoding

Do not embed:

- known OCR answers
- coordinates copied from a reference frame
- results based on video filenames
- manually assigned icon results
- special cases created only for one known video

Reference material is for understanding and evaluation.

Fix general causes rather than individual examples.

---

## Code Organization

Production code belongs under:

`src/dmi/`

Organize related modules into a small number of clear subpackages based on responsibility.

Recommended structure:

```text
src/dmi/
├── __init__.py
├── pipeline/
│   ├── frame_processor.py
│   └── orchestration.py
├── detection/
│   ├── display_geometry.py
│   ├── left_display.py
│   ├── right_display.py
│   ├── right_layout.py
│   ├── icons.py
│   └── ocr.py
├── temporal/
│   ├── smoothing.py
│   └── state_tracking.py
├── output/
│   ├── json_writer.py
│   ├── summary_builder.py
│   └── annotation.py
├── io/
│   ├── video_reader.py
│   ├── webcam_reader.py
│   └── video_writer.py
└── utils/
    ├── geometry.py
    ├── image_ops.py
    └── timing.py
```

Use this structure as guidance, not as a requirement to create every file immediately.
Create or move modules only when their responsibility clearly belongs to one of these areas.

Keep:

- pipeline/ for orchestration and frame processing
- detection/ for computer-vision, OCR, screen, layout and icon detection
- temporal/ for smoothing, tracking and frame-to-frame state
- output/ for compact JSON, annotations and output generation
- io/ for video and webcam input/output
- utils/ only for genuinely shared helpers

Avoid:

- keeping all production files directly under src/dmi/ as the project grows
- deep directory hierarchies
- unnecessary subpackages
- dozens of tiny files
- duplicated V1/V2 implementations
- files named new, final, v2_final, or similar

Prefer moving existing working code into the appropriate structure rather than rewriting it unnecessarily.
Entry-point scripts remain under:
scripts/
Scripts should stay lightweight and call the production code under src/dmi/.

---

## Evaluation

Do not consider an improvement successful only because the program runs.

Use `docs/EVALUATION.md` to compare:

- accuracy
- temporal stability
- processing speed
- regressions
- output correctness

When visual correctness cannot be verified automatically, generate annotated output and ask the user to review it.

User feedback is evaluation evidence, not permission for frame-specific fixes.

---

## Documentation Ownership

Each document owns its topic.

Do not duplicate detailed requirements between markdown files.

Update the document responsible for the changed behavior.

Keep `docs/STATE.md` as a concise technical handoff, not a development diary.

---

## Git Workflow

After completing each phase the user approve is needed, after confirmation you can:

1. update `docs/STATE.md`
2. review the changes
3. commit with a clear message
4. push to the remote repository

Do not commit a phase as complete before user visual validation.

---

## Definition of Done

A V2 phase is complete only when:

- its intended improvement is implemented
- relevant tests pass
- representative videos are processed
- V1 regressions are checked
- visual output is reviewed when applicable
- performance is measured when relevant
- limitations are reported
- user approval is obtained when required
- `docs/STATE.md` is updated

Do not declare completion only because code was written.
