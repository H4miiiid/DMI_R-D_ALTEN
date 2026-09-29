# EVALUATION.md — V2 Validation

## 1. Purpose

This document defines lightweight evaluation for DMI Detection V2.

Evaluation should answer:

- Are required UI elements detected correctly?
- Are OCR values generally reliable?
- Are annotations stable?
- Is processing faster than V1?
- Is the compact JSONL useful and significantly smaller?
- Did V2 break previously working V1 behavior?

Avoid unnecessarily strict tests or thresholds.

Use measurements, representative videos, and visual review together.

---

## 2. Evaluation Inputs

Use both:

- new V2 development videos
- representative existing V1 videos

New V2 videos include:

- `train_data_gamma.mp4`
- `validate_train_data.mp4`
- `train_numbers.mp4`

Previous videos should remain useful for regression, speed, accuracy, and stability comparison.

There is currently no complete numerical ground-truth dataset, so do not claim exact accuracy when it cannot be measured reliably.

---

# 3. Main Evaluation Areas

Focus V2 evaluation on:

1. detection correctness
2. OCR correctness
3. annotation stability
4. processing performance
5. compact JSONL behavior
6. V1 regression

Do not create complex metrics unless they help diagnose a real problem.

---

# 4. Detection Check

For representative sections of each video, verify that the pipeline detects the elements required by `docs/UI_SPEC.md`.

Check examples such as:

- active screen
- title
- required buttons
- button center points
- required fields
- icons
- existing left-display elements where applicable

A lightweight detection summary may report:

```text
Expected elements: 15
Detected elements: 14
Missing: 1
Unexpected: 0
```

Visual inspection of the annotated video remains important.

Do not require perfect detection on every single frame to consider an improvement useful.

---

# 5. OCR Check

Evaluate only OCR values required by `docs/UI_SPEC.md`.

Examples include:

- screen titles
- `Gamma` / `Lambda`
- `Yes` / `No`
- Train Running Number values
- existing required V1 OCR values

When expected values are known, use simple exact-match checks.

Example:

```text
Expected: 128
Detected: 128
Result: correct
```

Occasional temporary OCR errors may be acceptable if temporal stabilization prevents them from becoming stable incorrect output.

Focus on the final stable result rather than every raw OCR observation.

---

# 6. Stability Evaluation

V2 should reduce unnecessary shaking in:

- display geometry
- boxes
- buttons
- center points
- fields
- OCR values
- screen states

For stable sections of video, measure simple center-point movement.

Useful values include:

```text
mean movement: ...
P95 movement: ...
maximum movement: ...
```

These values are mainly for comparing versions.

For example:

```text
V1 mean center movement: 3.4 px
V2 mean center movement: 1.8 px
```

Lower is generally better when the physical UI is not moving.

Do not use a rigid pixel threshold for every element or resolution.

Visual inspection should confirm that smoothing does not hide real movement.

---

# 7. Transition Check

When the UI genuinely changes, verify that V2 still reacts correctly.

Examples include:

```text
Train Data → Validate Train Data
Train Data → Train Data (1/2)
Train Data (1/2) → Train Data (2/2)
Driver ID → Level
```

Check that:

- the old state is not retained too long
- the new state eventually becomes stable
- annotations follow the new layout
- temporal smoothing does not block real changes

Exact transition timing does not need a strict threshold unless a real problem is observed.

---

# 8. Performance Evaluation

Performance is a major V2 goal.

For representative videos, record:

- total processing time
- processed frames
- average processing FPS
- approximate milliseconds per frame

Example:

```text
Video: train_numbers.mp4

Frames: 2400
Video duration: 240 s
Processing time: 310 s
Processing FPS: 7.7
Average frame time: 130 ms
```

When possible, compare against V1:

```text
V1: 3.9 FPS
V2: 7.7 FPS
```

The purpose is to observe improvement, not enforce an arbitrary FPS threshold too early.

---

## 8.1 Bottleneck Timing

When performance is poor, measure major stages such as:

```text
display detection
right-display analysis
left-display analysis
OCR
icon recognition
annotation
output writing
```

Only optimize stages that measurements show are important.

Avoid adding detailed timing instrumentation everywhere unless needed.

---

# 9. JSONL Evaluation

The compact JSONL should be evaluated separately from detection accuracy.

Check:

- file is valid JSONL
- records are written incrementally
- required information is present
- unchanged states are not repeatedly written
- small geometric jitter does not create excessive records
- important semantic changes do create records

Useful simple measurements include:

```text
processed frames: 2400
JSONL records: 37
JSONL size: 28 KB
```

The record count should normally be far smaller than the processed frame count when the interface remains stable.

Do not enforce a fixed compression ratio because videos may contain very different amounts of UI activity.

---

## 9.1 Small Geometry Changes

A few pixels of movement should normally not create a new compact JSONL record.

Test representative stable sequences and check whether small variations such as:

```text
[1200, 600]
[1202, 599]
[1201, 602]
```

are treated as the same stable geometry for logging purposes.

Compaction tolerance should remain moderate and should not hide real UI movement.

---

# 10. Regression Evaluation

V2 must not unnecessarily break previously accepted V1 behavior.

After important changes, run a small representative subset of previous videos.

Check:

- display detection still works
- known states still work
- existing OCR has not clearly worsened
- left-display detection remains usable
- existing icons still work
- annotations remain valid

Full processing of every historical video is not required after every small code change.

Use broader regression runs before completing major phases.

---

# 11. Lightweight Automated Tests

Automated tests should focus on useful contracts rather than reproducing every video frame.

Useful tests include:

- output schema validity
- JSONL records can be parsed independently
- original-frame coordinate conversion
- known state names
- expected button identities
- compact logger does not duplicate unchanged state
- meaningful state/value change creates an update
- temporal state resets correctly
- existing icon assets can be loaded
- video pipeline can process a short sample without error

Prefer small focused tests that run quickly.

Avoid large brittle tests based on exact coordinates from individual frames unless verified ground truth exists.

---

# 12. Smoke Tests

Before a major phase is considered complete, run at least one representative video related to that phase.

Examples:

```text
new screen work
→ train_data_gamma.mp4

validation screen work
→ validate_train_data.mp4

Train Running Number work
→ train_numbers.mp4
```

Also run at least one relevant older V1 video when the change could affect existing behavior.

---

# 13. Visual Review

Annotated output remains an important evaluation method.

Check visually for:

- misplaced borders
- missed buttons
- wrong labels
- incorrect OCR
- shaking
- delayed state changes
- false icon assignments
- incorrect center points

When automated evidence is insufficient, ask the user to review the annotated output.

User feedback should be used to improve the general pipeline rather than hardcode the reviewed video.

---

# 14. V1 vs V2 Comparison

For major V2 milestones, keep a small comparison summary.

Example:

```text
Metric                  V1       V2
------------------------------------
Processing FPS          3.9      7.5
Mean center jitter      3.1 px   1.7 px
JSON records            2400     42
JSON size               1.8 MB   31 KB
Required OCR result     128      128
```

Only report values that were actually measured.

The purpose is to understand whether V2 improved the intended areas.

---

# 15. Acceptance Style

V2 evaluation should be practical rather than overly strict.

A phase can be considered successful when:

- the intended feature works on representative input
- no important regression is observed
- annotations are visually reasonable
- relevant tests pass
- measured performance is acceptable or improved
- known limitations are documented

Minor imperfections may remain if they do not significantly affect the intended use.

---

## Core Rule

Use **lightweight measurements + representative videos + visual review**.

Do not build a complex evaluation framework just for the sake of testing.

Evaluation should help improve the pipeline without becoming heavier than the pipeline itself.
