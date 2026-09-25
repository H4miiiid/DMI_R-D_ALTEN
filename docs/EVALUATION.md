# EVALUATION.md — Validation and Performance

## 1. Purpose

This document defines how the video-processing pipeline is evaluated.

Evaluation should answer:

- Are the detected UI elements correct?
- Are bounding boxes and center points accurate?
- Is OCR correct?
- Are icons assigned to the correct boxes?
- Are results stable across video frames?
- Does the system react correctly to real UI changes?
- Is processing fast and lightweight enough for future real-time use?

A change is not considered successful only because the code runs.

---

## 2. Evaluation Sources

Evaluation may use several types of evidence.

### Development Videos

Current videos are stored in:

`data/videos/dev/`

These are the main inputs used during development, debugging, and repeated testing.

They should be used to evaluate behavior across complete sequences, not only selected easy frames.

---

### Visual Reference Images

Annotated visual references are stored in:

`data/reference/overlays/`

These images help verify expected:

- UI regions
- element identities
- borders
- annotation placement

They are visual references only unless their exact coordinates have been independently verified.

Do not automatically treat them as numerical ground truth.

---

### Verified Reference Annotations

Machine-readable reference annotations may be added later when reliable values are available.

Possible future location:

`data/reference/annotations/`

Only manually or independently verified annotations should be considered ground truth.

Pipeline predictions must never automatically become ground truth.

---

### User Visual Review

When numerical ground truth is missing or incomplete, generate annotated output and ask the user to inspect it.

User feedback may identify problems such as:

- incorrect borders
- shifted boxes
- missing detections
- false detections
- incorrect OCR
- wrong icon assignments
- unstable detections
- incorrect screen states

Use this feedback to investigate the underlying cause and improve the general solution.

Do not create frame-specific hardcoded fixes only to satisfy one reported example.

---

## 3. Evaluation Levels

Evaluation should happen at three levels.

### Static Frame Evaluation

Used to check individual frames for:

- geometry
- bounding boxes
- center coordinates
- screen state
- OCR
- icons
- element identity

This is especially useful when verified reference annotations are available.

---

### Video Sequence Evaluation

Used to check behavior across consecutive frames.

Evaluate:

- geometric stability
- OCR stability
- icon stability
- screen-state stability
- real camera movement
- real UI changes
- temporary detection failures

A system that works on selected frames but fails across the complete video is not considered reliable.

---

### End-to-End Evaluation

Run the complete pipeline on representative videos and verify:

- processing completes successfully
- structured output is valid
- annotated output matches the detections
- all major UI responsibilities work together
- performance remains acceptable

---

## 4. Geometry Evaluation

Geometry evaluation should measure how accurately detected regions match their intended UI elements.

When verified ground-truth coordinates exist, useful metrics include:

- Intersection over Union (IoU)
- border error
- center-point error

Border error should consider:

- left border
- right border
- top border
- bottom border

Useful summary values may include:

- mean error
- median error
- P95 error
- maximum error

Do not rely only on IoU when border alignment is important.

Visual inspection should also be used to confirm that boxes are attached to the correct UI regions.

---

## 5. Right-Display Evaluation

Evaluate the right display for:

### Screen State

Check whether known states such as:

- `Main`
- `Driver ID`
- `Level`

are identified correctly.

Unknown/new screens should remain classified as unknown rather than being incorrectly forced into known states.

Detection of visible elements must continue even when the screen state is unknown.

### Title

Check:

- title localization
- OCR correctness
- temporal stability

### Buttons

Check:

- visible buttons are detected
- false buttons are avoided
- center coordinates are accurate
- button identities remain stable when known

### Data Fields

Check:

- field presence
- field localization
- OCR value
- absence of fabricated values

---

## 6. Left-Display Evaluation

Evaluate:

- all 22 boxes are detected
- box identities remain consistent
- box borders are aligned correctly
- center coordinates are accurate
- geometry follows camera/display movement

For icons, check:

- icon presence
- icon identity
- correct icon-to-box association
- empty boxes remain empty

Also verify that the analog speed indicator remains correctly localized.

Phase 5 checks include:

- independently drawn synthetic layouts with known corners, including exposure
  reduction and perspective changes; the tests allow 5–6 pixels for raster
  border thickness and interpolation, not as a claim about real-video accuracy
- rejection of blank, uniform, and unrelated noisy frames
- original-frame coordinate mapping and enclosing bounding boxes
- motion-backed recovery limited to three consecutive missed measurements,
  immediate loss on unsupported image changes, and reacquisition
- full decoding of all seven development videos, reporting incomplete frames
  explicitly and comparing right-display JSON against the approved Phase 4 run
- visual inspection of original-resolution annotations and enlarged left crops

Full box counts measure coverage, not border accuracy. No real-video IoU,
border-error, or center-error claims are supported without verified annotations.
The review output includes per-video `results.json` and `annotated.mp4`, selected
full frames and left crops, and `verification.json` with coverage, regression,
and end-to-end timing results. End-to-end timing includes decoding, annotation,
encoding, and JSON writing; it is not a core-only inference benchmark.

---

### Phase 6 icon checks

- Asset-derived synthetic cases cover scale, exposure, blur, local perspective,
  placement in differently named boxes, simultaneous icons in separate boxes,
  ambiguous multiple icons in one box, and immediate appearance/change/removal.
- Empty regions, noise, isolated digits/bars, circles, and triangles must not
  receive a known level-icon identity. Annotation labels use the JSON identity.
- Run all development recordings and compare every non-icon JSON value with
  the approved baseline; icon recognition must preserve earlier behavior.
- Inspect sampled source crops and annotated sequences, including abstentions.
  Prediction counts and visual checks are not independent per-frame ground
  truth or holdout accuracy. Thresholds are development settings, not calibrated
  probabilities; new cameras and unseen symbols need further evaluation.

Historical Phase 6 runs are documented in Git history. Their generated output
folders were removed after Phase 8 approval; use the retained Phase 8 baseline
for the current transition-video regression command below.

The script generates JSON, annotated MP4s, first/middle/last review images,
regression comparisons, left-region integrity checks, complete annotated-video
frame counts, icon-association counts, and end-to-end timing. It refuses to
overwrite existing video results. It does not claim recognition accuracy from
filenames or from previous predictions.

---

## 7. OCR Evaluation

When verified expected text exists, compare OCR output against the expected value.

Useful measures include:

- exact match
- normalized match where appropriate

Normalization may handle harmless differences such as surrounding whitespace or justified formatting cleanup.

Do not normalize uncertain OCR into a value that was not actually detected.

For important failures, inspect the source frame and OCR region visually.

---

## 8. Temporal Stability

Evaluate consecutive frames for unnecessary changes.

Look for:

- bounding-box jitter
- center-point oscillation
- OCR flickering
- icon flickering
- screen-state flickering

Stable visual input should normally produce stable output.

At the same time, the system must remain responsive to real changes.

A stabilization method is not successful if it hides genuine:

- state changes
- value changes
- icon appearance/disappearance
- button changes
- physical screen movement

---

### Phase 7 temporal checks

The initial Phase 7 change bounds right-field OCR history and resets it on
physical-display loss. Seven sequence tests cover short/prolonged OCR loss,
interrupted confirmation (including an uncertain state), a genuine sustained
value change, field removal, display loss/reacquisition, and explicit reset.
Existing geometry, left optical-flow, state-debounce, and icon-change tests
remain part of regression validation.

Default behavior for an unchanged recognized screen:

- Up to three unreadable field observations retain the previous value; the
  fourth returns `null`. This is a short grace period, not verified current OCR.
- Changed numeric values require 15 consecutive supporting observations;
  missing OCR or an uncertain screen state breaks that candidate sequence.
- Missing fields clear field history; missing display geometry clears all
  right-display history immediately. Initial/reacquired values are accepted
  from current recognition without comparison against stale history.

The five-observation state debounce is separate from field-value expiry.
Phase 8 replaces replay of prior content with current-frame regions during
confirmation; see the transition checks below. The limits are frame counts (three frames are about 0.1 s and
15 frames about 0.5 s at 30 FPS), not elapsed-time guarantees for sparse input.

A labeled synthetic sequence repeats a real frame, masks its field digits,
restores them, removes the image, and restores it. This checks end-to-end
expiry/recovery where development recordings lack controlled evidence loss.
The mask uses predicted geometry only to place the perturbation; it creates no
real-video ground-truth annotations. Full original-video results must also be
compared against the approved Phase 6 output, including icon assignments.

---

## 9. Screen Transitions

Transition evaluation may be added after stable individual-screen processing works reliably.

Possible transitions include:

```text
Main → Driver ID
Driver ID → Level
Level → Main
Known → Unknown
Unknown → Known
```

When transition references are available, evaluate:

- whether the previous state remains stable before the change
- whether the new state is eventually recognized
- response delay
- state flickering during the transition
- whether element detection continues while the state is uncertain

Detailed per-frame bounding-box annotations are not required for every transition frame unless they are useful for a specific evaluation.

### Phase 8 implementation and checks

Phase 8 video validation uses only `driverID_to_level.mp4` and
`level_to_main.mp4`, per user instruction. The seven original recordings are
steady-state inputs and are not counted as transition evidence.

- State selection now requires confident title OCR; title width, field presence
  and glyph counts no longer guess the screen. Test readable unsupported titles
  and unreadable titles as well as the three supported states.
- Test obstruction at startup, pause with empty right content, immediate reset,
  and fresh detection on the first clear frame. Verify early-frame alignment
  after startup occlusion and shifted Main close-button border pairs.
  Include neutral tool shapes in
  synthetic checks; do not claim robot validation without robot recordings.
- Unknown-screen buttons require image edges as well as blue border color on
  all four sides, with bright glyph neighborhoods excluded. Uniform blue
  background and text edges cannot validate extrapolated cells.
- State confirmation continues for five supporting observations. A new known
  candidate yields an unknown state with current-frame, neutral region labels;
  a later uncertain frame cannot temporarily restore the obsolete state label.
- Short raw-unknown intervals can retain the last confirmed state label, but
  never its old regions. Unknown screens retain supported field geometry with
  unknown value. Confirmed state changes reset geometry/OCR history.
- New-screen OCR must be consistent across state confirmation or pass the normal
  numeric confirmation window before a value is emitted.
- Synthetic sequence tests cover current geometry under motion, field removal,
  interrupted state confirmation, unknown screens, noisy reacquisition, absence
  of old-state flashes, conservative title mapping, obstruction recovery, and
  rejection of extrapolated cells on blue background without edges.
- Inspect original and annotated frames around the source-observed boundaries
  in UI_SPEC.md and through hand occlusions. Report transition delay relative to
  those observations, current button/field availability, state runs, abstentions,
  and geometry consistency. Prediction traces are diagnostics, not ground truth.

Run both complete recordings into a fresh directory:

```sh
python3 scripts/evaluate.py --output-dir outputs/phase8_validation_new --baseline outputs/phase8_revision_final --video driverID_to_level --video level_to_main
```

Missing approved baselines are explicitly reported as unavailable (`null`
comparison lists), not as zero regressions. `--allow-changes` records existing
baseline differences without stopping, for investigation only; it does not
approve them. All-field comparisons include icons. The retained Phase 8 JSON
is the visually approved baseline; generated files remain local and Git-ignored.

---

## 10. Regression Testing

Every significant improvement should be checked against previously working cases.

A change should not be accepted only because it improves one frame or one video.

After meaningful changes:

1. rerun relevant reference cases
2. rerun representative development videos
3. compare important metrics when available
4. inspect annotated output when geometry changed
5. investigate any new regression

Whenever a verified failure case is useful and reproducible, consider adding it to the reference set.

---

## 11. Holdout Evaluation

Future unseen videos may be stored separately as holdout data.

Holdout videos should represent the same real interface but should not be repeatedly used to tune the implementation.

They may include variations such as:

- slightly different camera position
- different scale
- different lighting
- different UI sequences
- different displayed values
- different icon states

Use holdout videos near later stages of development to test whether the pipeline generalizes beyond the recordings used during implementation.

Do not copy existing development videos into the holdout set merely to create the folder.

---

## 12. Performance Evaluation

The final target is real-time webcam processing.

Measure performance on representative videos rather than assuming an approach is fast.

Track at least:

- average processing time per frame
- effective FPS
- major expensive stages

When useful, also report:

- median frame time
- P95 frame time
- maximum frame time

The implementation should remain fast and lightweight while preserving required accuracy and stability.

Avoid unnecessary repeated computation.

Not every expensive operation must run on every frame if a lighter strategy provides equivalent correctness and responsiveness.

Do not optimize only for FPS while introducing significant detection errors.

---

## 13. Baselines and Thresholds

Do not invent strict acceptance thresholds before the available data has been measured.

First establish reliable baselines.

For example:

```text
Geometry:
Mean IoU: ...
Mean border error: ...
P95 border error: ...

OCR:
Title accuracy: ...
Data-field accuracy: ...

Icons:
Recognition accuracy: ...
Association accuracy: ...

Performance:
Average ms/frame: ...
Effective FPS: ...
```

Once realistic performance is understood, meaningful acceptance thresholds may be defined and updated here.

---

## 14. Evaluation Output

`scripts/evaluate.py` should eventually produce a concise summary of available evaluation results.

For example:

```text
Evaluation Summary

Reference cases: 18

Geometry
Mean IoU:              0.94
Mean border error:     3.2 px
P95 border error:      7.8 px

OCR
Title accuracy:        97.0%
Data-field accuracy:   95.0%

Icons
Recognition accuracy: 98.0%

Performance
Average frame time:    42 ms
Effective FPS:         23.8
```

Only report metrics that are actually supported by available verified references.

Do not present estimated or visually guessed values as measured results.

---

## 15. Phase Approval

Before a development phase is considered complete:

- relevant checks should pass
- representative videos should be processed
- important regressions should be checked
- performance should be measured when relevant
- generated annotated output should be reviewed when visual correctness matters

When automated verification is insufficient, ask the user to inspect the annotated output.

If user approval is required, the phase should not be marked complete until:

- the user approves the result, or
- the user explicitly accepts the remaining limitations

After approval, update `docs/STATE.md` and follow the Git workflow defined in `AGENTS.md`.

---

## 16. Core Evaluation Rule

Use the strongest available evidence.

Prefer:

```text
verified ground truth
        ↓
measured comparison
        ↓
full-video behavior
        ↓
visual inspection
        ↓
user feedback
```

These methods may be used together.

Never claim higher confidence than the available evaluation evidence supports.

Crossed or degenerate title-border fits must be omitted rather than emitted as
regions. Validate the final rounded output polygons, including occluded intervals.
