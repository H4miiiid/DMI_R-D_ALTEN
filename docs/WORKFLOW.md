# WORKFLOW.md — DMI Detection V2

## 1. Purpose

This document defines the development order for Version 2.

V2 must be implemented incrementally. Complete and verify one phase before moving to the next.

Use the other documents as the source of truth:

- project goals → `docs/PROJECT.md`
- UI requirements → `docs/UI_SPEC.md`
- structured output → `docs/OUTPUT_SPEC.md`
- validation and metrics → `docs/EVALUATION.md`
- engineering rules and code organization → `AGENTS.md`
- current progress → `docs/STATE.md`

---

## 2. General Development Cycle

For each phase:

1. read `docs/STATE.md`
2. read the relevant specification
3. inspect the current implementation and data
4. implement only the current phase
5. run focused tests
6. process representative videos
7. compare against previous working behavior
8. request user visual review when needed
9. update `docs/STATE.md`
10. follow the Git workflow in `AGENTS.md`

Do not combine several major V2 improvements into one phase.

---

# 3. V2 Development Phases

## Phase 1 — Project and Code Structure

Reorganize the existing V1 code into the clearer package structure defined in the **Code Organization** section of `AGENTS.md`.

The goal is to separate responsibilities such as:

- pipeline
- detection
- temporal processing
- output
- input/output
- shared utilities

Move and refactor existing files carefully.

Do not intentionally change detection, OCR, temporal behavior, or output results during this phase.

Update imports, tests, and scripts as needed.

### Complete when

- the new structure is clean and understandable
- existing code runs from the new locations
- relevant V1 tests still pass
- representative V1 videos still produce equivalent results

---

## Phase 2 — V2 Baseline

Establish the starting V2 baseline before making functional improvements.

Measure representative V1 behavior using `docs/EVALUATION.md`.

Record useful baseline values such as:

- processing FPS
- frame-processing time
- output size
- JSON record count
- visible geometry stability
- known OCR limitations

Do not spend time creating unnecessarily detailed benchmarks.

### Complete when

There is a simple baseline that later V2 improvements can be compared against.

---

## Phase 3 — Compact JSONL Output

Replace the large repeated frame-level output with the compact incremental JSONL behavior defined in:

`docs/OUTPUT_SPEC.md`

Implement:

- incremental writing
- snapshots
- meaningful updates
- avoidance of unnecessary duplicate records
- optional verbose debug output

Small coordinate jitter should not generate excessive records.

### Complete when

Representative videos produce valid compact JSONL while preserving the important detected information.

---

## Phase 4 — New Train Screens

Add support for the new V2 screens defined in `docs/UI_SPEC.md`.

Use the new development videos:

- `train_data_gamma.mp4`
- `validate_train_data.mp4`
- `train_numbers.mp4`

Implement required detection and OCR for the relevant:

- screen titles
- fields
- values
- buttons
- button center points
- page/navigation controls

Do not extract Train Data values that are explicitly outside the current V2 scope.

### Complete when

The new screens are detected and annotated reliably on representative sections of the new videos.

Request user visual review before completing the phase.

---

## Phase 5 — Additional Icons

Extend icon support using the new assets under:

`data/icons/`

Keep icon detection data-driven where practical so new supported assets can be added without large code changes.

Use existing V1 icon behavior as regression coverage.

### Complete when

New icons are recognized in their intended UI regions without clearly degrading existing icon detection.

---

## Phase 6 — Temporal Stability

Improve the remaining visible shaking and frame-to-frame instability.

Focus on:

- display geometry
- boxes
- buttons
- center points
- fields
- OCR values
- screen states
- icons

Use `docs/UI_SPEC.md` and `docs/EVALUATION.md` for expected behavior.

Do not use smoothing to hide incorrect detection.

### Complete when

Stable UI sections produce visibly steadier results while real UI changes remain responsive.

Request user review of representative annotated videos.

---

## Phase 7 — Performance Optimization

Profile the completed V2 pipeline and improve the expensive stages.

Focus on measured bottlenecks rather than assumptions.

Possible improvements may include reducing unnecessary repeated:

- detection
- OCR
- icon recognition
- transformations
- annotation work
- data copying

Preserve accuracy and stability.

### Complete when

Representative videos show a meaningful processing-speed improvement without important regressions.

---

## Phase 8 — End-to-End V2 Validation

Run the complete V2 pipeline across:

- new V2 videos
- representative previous V1 videos

Verify using `docs/EVALUATION.md`:

- detection
- OCR
- stability
- compact JSONL
- annotation quality
- performance
- V1 regressions

### Complete when

V2 works reliably as one complete pipeline and the important remaining limitations are documented.

User review is required before final approval.

---

## Phase 9 — Real-Time Readiness

Verify that the same V2 processing path remains suitable for live webcam input.

Do not create separate detection logic for recorded and live input.

Check that:

- incremental JSONL works during live processing
- processing does not accumulate unnecessary backlog
- the latest stable DMI state can later be reused by a backend publisher
- long-running processing remains lightweight

Backend communication itself is outside the current V2 scope unless explicitly added later.

### Complete when

The V2 architecture and outputs are ready for later real-time backend integration.

---

# 4. Regression Rule

V1 remains the baseline.

After changes that may affect existing functionality, run a small relevant subset of previous videos.

Full historical regression is not required after every small edit.

Use broader regression before completing major phases.

---

# 5. User Validation

When correctness is primarily visual:

1. generate the annotated output
2. provide it for user review
3. collect feedback
4. fix the general cause
5. rerun the affected video

Do not mark a visually dependent phase complete before approval or explicit acceptance of its limitations.

---

# 6. STATE.md

After completing a phase:

- move it to the completed section
- briefly record files/modules changed
- mention important functions or components added
- record the main verified result
- record only limitations relevant to future work
- set the next phase as current

Keep `STATE.md` concise.

---

## Core Workflow Rule

Build V2 one verified layer at a time.

Do not mix structural refactoring, new UI support, smoothing, output redesign, and performance optimization into one large change.
