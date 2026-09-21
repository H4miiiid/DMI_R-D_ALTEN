# WORKFLOW.md — Development Process

## 1. Purpose

This document defines the order in which the project should be developed and verified.

It does not repeat detailed requirements.

Use the other project documents as the source of truth:

- project scope and goals → `docs/PROJECT.md`
- UI behavior and elements → `docs/UI_SPEC.md`
- structured output → `docs/OUTPUT_SPEC.md`
- validation, metrics, and performance → `docs/EVALUATION.md`
- current verified progress → `docs/STATE.md`
- general agent and repository rules → `AGENTS.md`

---

## 2. General Development Cycle

For every substantial development step:

1. read `docs/STATE.md`
2. read only the documentation relevant to the task
3. inspect the relevant input data and current code
4. implement the smallest coherent change
5. run relevant tests or evaluation
6. inspect generated output when needed
7. check for regressions
8. request user review when automated verification is insufficient
9. update `docs/STATE.md` after verification
10. follow the Git workflow in `AGENTS.md`

Do not build later stages on top of a known unreliable earlier stage.

---

# 3. Development Phases

## Phase 1 — Understand the Data

Inspect:

- development videos
- reference images
- icon assets
- current repository structure

Use `docs/PROJECT.md` and `docs/UI_SPEC.md` to understand what the system must eventually handle.

### Complete when

The available data, interface structure, and current limitations are understood well enough to begin implementation.

---

## Phase 2 — Basic Processing Pipeline

Create the minimum end-to-end structure required to:

- read input frames
- call the core processing pipeline
- return structured results
- generate visual output

Use `docs/OUTPUT_SPEC.md` for output requirements.

Keep frame acquisition separate from the core processing logic.

### Complete when

Representative development videos can pass through the basic pipeline successfully.

---

## Phase 3 — Display Geometry

Implement and stabilize localization and geometry of the physical displays.

Use:

- `docs/UI_SPEC.md` for expected geometry behavior
- `docs/EVALUATION.md` for verification

### Complete when

Display geometry is reliable enough that later UI-element detection can safely depend on it.

User visual review should be requested when automated verification is insufficient.

---

## Phase 4 — Right Display

Implement the required right-display behavior.

Follow `docs/UI_SPEC.md` for:

- known screen behavior
- unknown/new screens
- titles
- buttons
- fields
- transitions

Follow `docs/OUTPUT_SPEC.md` for returned values.

### Complete when

The right-display functionality satisfies the relevant evaluation checks in `docs/EVALUATION.md`.

---

## Phase 5 — Left Display

Implement the required left-display structure.

Follow `docs/UI_SPEC.md` for expected elements and behavior.

Use `docs/EVALUATION.md` to verify geometry and stability.

### Complete when

The left-display structure is reliable across representative inputs.

---

## Phase 6 — Icon Processing

Implement icon recognition and association using the available assets.

Refer to:

- `docs/UI_SPEC.md`
- `docs/EVALUATION.md`

### Complete when

Icon behavior passes the relevant evaluation checks without introducing unacceptable false detections.

---

## Phase 7 — Temporal Stability

Improve frame-to-frame stability only after single-frame behavior is sufficiently reliable.

Use `docs/UI_SPEC.md` for expected temporal behavior and `docs/EVALUATION.md` for validation.

Do not use temporal logic to hide incorrect underlying detections.

### Complete when

Stable input produces stable output while genuine changes remain detectable.

---

## Phase 8 — Transitions

Validate behavior while the right display changes between states.

Use the transition requirements in:

- `docs/UI_SPEC.md`
- `docs/EVALUATION.md`

### Complete when

State changes are handled without unacceptable flicker, delay, or interruption of element detection.

---

## Phase 9 — End-to-End Integration

Run the complete pipeline with all implemented components enabled.

Verify the full system using `docs/EVALUATION.md`.

Check that:

- components work together
- structured output follows `docs/OUTPUT_SPEC.md`
- visual output represents the same detections
- previously working behavior has not regressed

### Complete when

Representative full videos run reliably through the complete pipeline.

---

## Phase 10 — Performance Optimization

Optimize the verified pipeline for the real-time target defined in `docs/PROJECT.md`.

Measure performance using `docs/EVALUATION.md`.

Optimize based on measured bottlenecks rather than assumptions.

Do not trade away important correctness for minor speed improvements.

### Complete when

The pipeline satisfies the agreed accuracy, stability, and performance expectations.

---

## Phase 11 — Real-Time Readiness

Adapt the input layer for live webcam frames while preserving the same core processing pipeline.

Do not duplicate the detection logic specifically for webcam use.

### Complete when

The core system can operate correctly with live-frame input and remains consistent with recorded-video behavior.

---

# 4. Implementation During Each Phase

Production code belongs under:

`src/dmi/`

Command-line and development entry points belong under:

`scripts/`

Add modules only when a clear responsibility justifies them.

Follow the code-organization rules in `AGENTS.md`.

Do not create speculative folders, modules, abstractions, or placeholder implementations merely because they may be useful later.

---

## 5. Verification Before Moving Forward

A phase should not be considered complete only because implementation exists.

Use the verification rules in `docs/EVALUATION.md`.

When visual correctness cannot be verified automatically:

1. generate the relevant annotated output
2. ask the user to review it
3. address the feedback
4. rerun the affected evaluation

Do not proceed as though a visually unverified result has been approved.

---

## 6. Failed Approaches

If an implementation repeatedly requires special cases or patches:

- investigate the underlying failure
- reconsider the approach
- compare alternatives when appropriate

Do not keep extending a fragile solution only because work has already been invested in it.

---

## 7. STATE.md

After a verified phase or meaningful capability change, update:

`docs/STATE.md`

Keep it as a concise snapshot of:

- current phase
- verified capabilities
- important results
- known limitations
- next step

Do not use it as a development diary.

---

## 8. Phase Completion

Before closing a phase:

- complete its intended scope
- verify it according to `docs/EVALUATION.md`
- check important regressions
- obtain user review when required
- update `docs/STATE.md`
- follow the Git workflow in `AGENTS.md`

Only then move to the next phase.

---

## 9. Core Workflow Rule

Build the project in verified layers.

Do not move forward simply because a phase has code.

Move forward when the current layer is reliable enough for the next one to depend on it.
