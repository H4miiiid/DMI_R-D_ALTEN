# PROJECT.md — DMI Video Screen Understanding

## Project Goal

Build a reliable computer-vision pipeline that understands a physical two-display interface recorded by a webcam.

The system must process video frames, detect and recognize the relevant UI elements, extract required text and coordinates, and produce structured results together with visual annotations.

Recorded videos are the first development target.

The same core pipeline should later support live webcam frames without requiring a redesign.

---

## Real Input

Current development videos are stored under:

`data/videos/dev/`

These videos represent the real type of input the final system must process.

Future recorded videos and live webcam input are expected to show the same physical interface under similar real-world conditions.

The pipeline must not assume:

- identical pixel coordinates
- perfectly fixed camera position
- identical scale
- identical lighting
- perfectly stable perspective

Reasonable webcam variation should be expected.

---

## Interface Scope

The interface contains two main display regions.

### Right Display

The right display is stateful and may switch between screens such as:

- `Main`
- `Driver ID`
- `Level`
- other screens discovered later

Depending on the active screen, it may contain:

- a title
- buttons
- a data field
- changing text or values

Detailed behavior belongs in:

`docs/UI_SPEC.md`

### Left Display

The left display contains:

- 22 logical UI boxes
- optional icons inside the boxes
- one analog speed indicator

Element identities should remain consistent across frames even when the camera or screen position changes.

Detailed behavior belongs in:

`docs/UI_SPEC.md`

---

## Required Result

The pipeline should ultimately provide structured information describing the visible interface.

Typical results include:

### Right Display

- active UI state
- title text
- visible buttons
- button center coordinates
- data-field presence
- data-field value

### Left Display

- box identities
- box positions
- box center coordinates
- icon presence
- icon identity
- icon-to-box association
- speed-indicator position

The exact JSON structure and coordinate conventions belong in:

`docs/OUTPUT_SPEC.md`

---

## Visual Output

The system should also generate annotated frames or videos during development and evaluation.

These outputs help verify:

- geometry
- alignment
- detections
- OCR
- labels
- icon associations

Visual output is a validation aid and does not replace structured evaluation when verified ground truth is available.

---

## Existing Data

Project data is stored under:

`data/`

Current sources include:

- development videos in `data/videos/dev/`
- visual reference overlays in `data/reference/overlays/`
- known icon assets in `data/icons/`

Visual reference overlays are examples only and are not automatically numerical ground truth.

---

## Ground Truth

The project may initially have incomplete or no machine-readable ground-truth annotations.

This is acceptable.

Do not fabricate annotation files or exact verified coordinates.

The project must distinguish between:

- input data
- visual references
- generated predictions
- verified ground truth

When verified annotations become available, they may be used for numerical evaluation and regression testing.

Evaluation rules belong in:

`docs/EVALUATION.md`

---

## Engineering Priorities

Use this general priority:

1. correctness
2. geometry and detection accuracy
3. OCR and recognition accuracy
4. temporal stability
5. maintainability
6. performance

Do not sacrifice major correctness or accuracy for small performance improvements.

---

## Real-Time Performance

The final pipeline is intended for real-time webcam processing.

The implementation should therefore remain **fast, lightweight, and efficient** while preserving the required accuracy and stability.

Design choices should consider computational cost from the beginning. Avoid unnecessarily expensive processing, repeated work, or operations that provide little measurable benefit.

Not every operation must run on every frame if a lighter strategy can provide equivalent accuracy and responsiveness.

Recorded-video development should use the same core processing design intended for future real-time operation.

Exact performance targets and benchmarks are defined in `docs/EVALUATION.md`.

---

## Implementation Principle

Do not assume a specific computer-vision technique before inspecting the data.

Choose methods based on:

- actual video behavior
- observed failure cases
- measurable results

Different parts of the interface may use different techniques when justified.

Prefer simpler solutions when they provide equivalent reliability.

---

## Library Guidance

Use OpenCV as the default library for general computer-vision and video-processing operations where appropriate.

Do not treat OpenCV as a mandatory solution for every task. Other libraries or models may be used when they provide a clear advantage in accuracy, robustness, or maintainability.

---

## Generalization

Do not optimize the implementation only for the currently available videos.

Avoid video-specific or frame-specific shortcuts.

The pipeline should remain useful on new recordings of the same physical interface under reasonable variations.

---

## Frame-Source Independence

Core processing should operate on frames independently of their source.

Conceptually:

```text
Recorded Video ─┐
                ├─> Frame → Screen Understanding → Structured Result
Live Webcam ────┘
```

Video reading and webcam capture should remain separate from the core detection logic.

---

## Project Structure

Detailed information is split across dedicated documentation:

- `AGENTS.md` — agent behavior and engineering rules
- `docs/PROJECT.md` — project scope and objectives
- `docs/UI_SPEC.md` — UI structure and behavior
- `docs/OUTPUT_SPEC.md` — output and coordinates
- `docs/EVALUATION.md` — testing and metrics
- `docs/WORKFLOW.md` — development phases
- `docs/STATE.md` — current verified project state

Avoid duplicating the same requirement across multiple documents.

---

## Final Objective

Transform real webcam-style video into stable structured information describing the physical interface:

```text
Video Frame
    ↓
Screen Understanding
    ↓
Right Display + Left Display
    ↓
Text + Buttons + Fields + Boxes + Icons + Coordinates
    ↓
Structured Output
```

The final system should be accurate, stable, maintainable, reasonably efficient, and reusable for future live webcam processing.
