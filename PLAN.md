# PLAN.md — SENSE Event-Driven Detection, Stable Screen Geometry, and Monitor Homography

**Status:** Incremental roadmap; see `STATE.md` for accepted implementation and remaining validation.

**Prepared:** 2026-11-09.  
**Reviewed repository:** `H4miiiid/DMI_R-D_ALTEN`, `main` at `c5b4e642601a8bb4b7c2b16d19f66d78e08649b1` (verify HEAD and working tree before editing).  
**Primary scope:** The **upper, connected SENSE DMI monitor**: robust Driver ID / Level recognition, efficient screen-state observation, stable pixel centers, and reusable pixel-to-millimeter mapping. Extend to other SENSE screens only by independently describing and validating their layouts.  
**Out of scope:** New ML/YOLO model, second vision backend, GUI redesign, robot GPIO/motion/controller/protocol rewrite, automatic robot operation, TWIN detector retuning.

---

## 0. Instructions to the implementation agent

Read `AGENTS.md`, `STATE.md`, the current source and tests **before making changes**. `AGENTS.md` is the repository's governing working procedure. Follow its per-step approval, reviewer, artifact, calibration, and TWIN regression requirements. **This plan is not permission to implement every phase in one request or to commit/push.** Implement only the phase explicitly authorized by the user; provide evidence, request acceptance, and proceed to the next phase only after permission. If a recommendation below conflicts with current `AGENTS.md` or an accepted runtime contract, preserve the contract, report the conflict, and seek a decision rather than silently weakening it.

1. `git status --short`, `git rev-parse HEAD` and inspect local diffs; preserve unrelated work and ignored recordings. Do not assume remote `main` equals the operator's local branch.
2. Reproduce failures from actual **raw SENSE** recordings where available. Do not treat annotated preview overlays or previous annotations as ground truth. Do not invent missing raw recordings.
3. Maintain **one camera acquisition owner, one latest-frame slot**, a single `VisionSession`/`FrameProcessor` path, and separate analysis, preview, and action evidence. Do not create a second end-to-end pipeline or persist unbounded frames.
4. Target SENSE only. Preserve accepted TWIN detector behavior, schemas, and outputs; test TWIN as a frozen regression baseline. Never infer SENSE identity from camera index alone: the connected monitor must be established from current image evidence.
5. Keep existing title/field/button identities, `active` semantics, output geometry and **original camera-image pixel coordinates**. Predicted/default layouts may propose searches or check coverage, **never fabricate measured borders, button identities or coordinates**.
6. Preserve the existing 1.5 s direct-evidence lifetime, 4 px publication/evidence matching contracts unless independently validated and explicitly approved, rejection of invalid calibration, and 3 mm numerical error requirement. Do **not** make old detection observations appear fresh or treat a cached annotation/locked coordinate as authorization for motion.
7. Keep normal detection mode for diagnosis and matched benchmarks. Report exactly what was implemented, unit/replay/physical evidence, remaining uncertainty, and performance numbers; never claim unperformed hardware testing.
8. Use the repository's `code_review` and `step_checker` review procedure as defined in `AGENTS.md`. Do not publish, mark accepted in `STATE.md`, or start the next phase without authorization.

### User's accepted design decisions

- The camera and SENSE monitor are intended to be fixed. UI controls have static physical positions on each unchanged screen. Per-frame coordinate jitter is mostly measurement noise.
- Acquire a screen from approximately **3–5 consistent full detections**; compare observed identities/coverage to a **screen-specific expected layout**, then **lock** measured boxes and median centers.
- Stop repeated full detection/OCR of the entire screen while its layout is confirmed and unchanged. Continue inexpensive, bounded checks for screen/context changes, relevant field values and dynamic icons.
- Known **digit/keypad / same-page selection** actions often change the grey field's value, _not the title or layout_. After these actions, **keep locked geometry**, re-read the existing grey field region from current pixels, and update only the value/activity/icon information that changed.
- A click on the **grey field (confirmation)** or **X / close** can navigate to a new page; enter transition monitoring and perform complete acquisition when a new title/layout is observed. Other controls may also change page or appearance in other workflows; do not hardcode the claim that only these two controls can ever change the screen.
- Compare saved **title and field crops** with current crops as change indicators, rather than running title or field OCR on every frame. Prefer time-based scheduling (e.g. ~1 s for title checks), not counting every N camera frames.
- Keep one physically meaningful SENSE **monitor-plane** homography across Driver ID, Level and other coplanar states when camera geometry/origin is unchanged; validate across independent physical positions before claiming accepted accuracy.

### Essential distinction: three kinds of retained information

| Kind                                                                                                             | May remain locked?                                                 | Can alone authorize a click?                                      |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Static screen model: identities, reference ROIs/quads, median centers, monitor registration                      | Yes, while the context remains verified; invalidate on loss/change | **No**                                                            |
| Dynamic state: grey field value, Level active status, blinking mode identity                                     | Must be updated from current pixels; unknown on ambiguity          | **No**                                                            |
| Fresh action evidence: observation of the intended control, visibility, active state, source/geometry and timing | No; expire under current contract                                  | May contribute to authorization **only** with all existing guards |

**Design rule:** Avoid full-screen detection for every action where a safe, cheap, independently verified current target-region check can be introduced. Until such a check is implemented and validated, retain the existing on-demand full-detection requirement for physical actions. Never replace it with an unchecked historical cache.

---

## 1. Code map and verified starting point

The following references were inspected at the source revision above. Re-read local HEAD before editing.

| File                                                                        | Current responsibility / relevant behavior                                                                                                                                                                                                                                     | Intended change                                                                                                                                                       |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dmi_computer_vision/src/dmi/detection/right_display.py`                    | `analyze_right_display()` rectifies to `RECTIFIED_SIZE=(600,960)`; `_detect_data_field()` uses HSV thresholds and contour/size/location filters; `_read_digits()` works _after_ a field is found; Level `_recognize_level_buttons()` reads measured cells and active state     | Add measured, brightness-resilient **field** fallback; optionally scoped contrast preprocessing for demonstrated weak controls; leave OCR logic initially untouched   |
| `dmi_computer_vision/src/dmi/detection/right_layout.py`                     | `detect_button_quads()` measures current border geometry; Level `_level_button_cells()` requires supporting borders; Level semantic identities are read from current content                                                                                                   | Reuse; small SENSE-only improvements only after a reproduced lighting failure; never replace measured cells with nominal grid coordinates                             |
| `dmi_computer_vision/src/dmi/detection/left_display.py`, `left_layout.py`   | Speedometer/sidebar/box geometry vs left train workflow content; `BorderEvidence` already uses relative blue contrast                                                                                                                                                          | Reuse; do not globally change shared thresholds merely to improve right field                                                                                         |
| `dmi_computer_vision/src/dmi/detection/title_ocr.py`                        | Tesseract title/field OCR and exact supported title classification                                                                                                                                                                                                             | Reuse in acquisition, plus **targeted** OCR on changed title/field ROIs; no new OCR engine                                                                            |
| `dmi_computer_vision/src/dmi/pipeline/frame_processor.py`                   | Existing single-frame full detector and geometry/content temporal stabilizers; `max_gap_seconds=1.0` normally resets history after longer processed-frame gaps                                                                                                                 | Preserve full detection semantics. Controller/cache must not depend on its temporal state surviving long locked periods                                               |
| `dmi_computer_vision/src/dmi/temporal/smoothing.py`                         | Right-display stabilization; Level buttons intentionally publish current measured geometry rather than ordinary smoothing                                                                                                                                                      | Do not immediately change this for all screens. Lock centers at the **screen controller** layer instead; diagnose Level misses independently                          |
| `dmi_computer_vision/src/dmi/api.py`                                        | `VisionSession`, `Observation` (frame index, receipt/upstream time, direct evidence, context)                                                                                                                                                                                  | Preserve API and the meaning of fresh observations                                                                                                                    |
| `dmi_robot_master/integration/vision_observer.py`                           | One acquisition, detector and render worker. `_detect()` currently calls `session.process(packet)` on each consumed frame, projects pixels and updates mode history. Holds only latest packet and bounded history; `snapshot()` expires full detector observations after 1.5 s | Add screen controller and selective work in this owner; maintain a separate display-only locked cache; expose safe action-trigger notifications if needed             |
| `dmi_robot_master/integration/processing_policy.py`                         | `DetectionPolicy` uses 160x120 blurred grayscale differences, detection cap, burst, refresh and forced event                                                                                                                                                                   | Reuse/adapt cheap change-check logic; existing settings are not a drop-in “stop full detection” policy because it still forces regular detection                      |
| `dmi_computer_vision/src/dmi/mode_observation.py`, `dmi/detection/icons.py` | Existing template/mode reading of measured `box_14` and `box_16`; `ModeHistory` tracks blinking/steady with timed observations                                                                                                                                                 | Reuse for **dynamic icons** using locked, image-evidenced ROIs; do not freeze modes or infer them from click labels                                                   |
| `dmi_computer_vision/src/dmi/output/preview_state.py`                       | Display-only annotation hold/deadband, at most 2 missed detections / 1.5 s; cached overlay explicitly cannot authorize actions                                                                                                                                                 | Do not confuse preview caching with an authoritative screen lock; preserve preview freshness contracts                                                                |
| `dmi_robot_master/integration/publication.py`, `targets.py`                 | Original-pixel targets, 4 px publishing tolerance, evidence checks/expiry                                                                                                                                                                                                      | Preserve original outputs, freshness, identity and numerical policy; do not silently change public schema                                                             |
| `dmi_robot_master/integration/recorded_test.py`                             | Experimental `RecordedTestProjector`: reused saved SENSE homography plus **current** `getPerspectiveTransform(current, recorded)` registration. `_view_anchor` bounds monitor drift but registration is recomputed from noisy current corners                                  | Establish one robust session registration, check continued agreement; keep whole-monitor extrapolation explicitly experimental and unverified                         |
| `dmi_robot_master/integration/sense_calibration.py`, `calibration.py`       | Offline affine/homography fitting, validated provenance/geometry, independent control holdouts, reference mappings and error bounds                                                                                                                                            | Reuse fitting/inspection; no new per-screen homography or altered acceptance standard                                                                                 |
| `TapperWare_Flet/dmi_runtime.py`, `dmi_physical_press.py`                   | Existing call sites/press-result lifecycle; UI already invokes `VisionObserver`                                                                                                                                                                                                | **No GUI redesign**. If necessary, add only an explicit observer notification of successful/failed completed action; never assume movement guarantees a UI transition |

**Known current contracts:** `VisionObserver.experimental_press_sample()` uses recent direct detections (at most three, up to two misses, max 1.5 s) and matching screen/geometry; `recorded_test._xy()` checks direct center agreement within 4 px; `snapshot()` doesn't expose an expired observation as fresh. **A forever-locked coordinate therefore cannot make the existing press action immediately eligible by itself.** Address the gap in a separate, evidence-preserving integration phase; do not make stale observations “fresh.”

**Current calibration qualification:** `STATE.md` reports physically successful experimental clicks at specific Driver ID keys but **no ordinary recorded calibration satisfying the 3 mm limit** and no validated whole-screen coverage. Do not describe this as a fully validated SENSE homography; independent Level/edge holdouts remain required.

---

## 2. Target architecture (incremental; no parallel detection engine)

### States

Use three simple screen-lock states:

- **ACQUIRING:** Detecting a new screen; no controls confirmed yet.
- **PARTIAL_LOCK:** Some controls confirmed and locked.
  Continue bounded searches for missing required controls.
- **LOCKED:** All required static controls confirmed.
  Stop continuous full detection and use lightweight monitoring.

Dynamic updates (field values, icons, button activity) do not
require a separate state. Update them while keeping the lock valid.

On screen change or significant monitor movement, reset to ACQUIRING.

The controller should be a small **session-owned object**, ideally one new file `dmi_robot_master/integration/screen_lock.py`, with a small profile/configuration block there initially. Avoid a new service or modifying every analyzer. Proposed interfaces (names may adapt to local conventions):

```python
class ScreenLock:
    def observe_full(self, observation) -> LockTransition: ...
    def check_frame(self, packet, now) -> CheckDecision: ...
    def notify_action(self, label, *, completed: bool, at: float) -> None: ...
    def invalidate(self, reason: str) -> None: ...
    def cached_layout(self) -> dict | None: ...  # presentation/coordinate data; not direct evidence
```

State data must be bounded and explicitly separated:

```text
screen/profile, session_id, source_info/camera signature, frame_size,
monitor connected-region geometry + coordinate basis, calibration identity,
required observed identities and measured quads, locked median pixel centers,
reference ROI images or inexpensive image descriptors (bounded, memory-only),
last full-detection time/index, last cheap check time/index,
field: last directly read value + its own evidence timestamp,
icons/Level activity: last directly observed status + timestamps,
lock generation and invalidation reason; *no synthetic detector observation*.
```

Keep a single pending acquisition frame and native receipt timestamps. Store no unbounded image list; keep a maximum of five center/geometry samples and bounded crop references for a few small regions.

### State transitions

| Event/evidence                                                                                                                                        | New state / work                                                                                       | Geometry reused?                          |
| ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| Session start or frame-size/source/rotation change                                                                                                    | ACQUIRING; discard lock and source-bound calibration context                                           | No                                        |
| 3–5 consistent full detections satisfy the profile                                                                                                    | LOCKED; median measured centers, save current ROI references                                           | Yes                                       |
| Driver ID digit pressed; title/monitor unchanged                                                                                                      | UPDATING: refresh **grey field value** from current crop, then LOCKED                                  | Yes                                       |
| Level selection changed; same title/geometry                                                                                                          | UPDATING: refresh field **and relevant Level activity/icon states**; then LOCKED                       | Yes, if independently confirmed unchanged |
| Grey field/confirmation or X/close pressed                                                                                                            | UPDATING: watch title / page and transition; ACQUIRING if state/layout changes                         | Only if page demonstrably stays same      |
| Other button whose outcome is not explicitly modeled                                                                                                  | UPDATING with broad change check; ACQUIRING if uncertain                                               | Conditionally                             |
| Cheap title crop differs                                                                                                                              | Title OCR on **current** image; if recognized new title, ACQUIRING; if uncertain, retry/reacquire      | No on unresolved transition               |
| Title unchanged but field crop differs                                                                                                                | Targeted value OCR from current pixels; no full geometry detection if field is still present           | Yes                                       |
| Same-title button label/enable state changes                                                                                                          | Targeted validation if supported, else ACQUIRING                                                       | Only static verified geometry             |
| Blink toggles in box_16                                                                                                                               | Targeted existing mode observation and temporal logic; avoid full screen detection                     | Yes                                       |
| Monitor border/camera drift beyond locked tolerance, occlusion, frame loss, stale source, unknown title, configuration/calibration invalidation, Stop | Invalidate relevant lock/evidence and ACQUIRING when visibility returns                                | No                                        |
| No changes for a prolonged interval                                                                                                                   | Periodic bounded structural **audit** and/or full detection, configurable using measured failure rates | Yes only while audit confirms it          |

**Do not treat `title unchanged` as proof that all state is unchanged.** Same-title field values, Level enabled/disabled states, button/overlay changes and blinking modes are separate monitored regions. External/manual touchscreen interactions are possible even without an app-generated click event; cheap visual checks must detect unexpected change.

**Movement is not identical to a completed click.** Start/stop of a robot movement may temporarily occlude/shake the camera; keep the source live but withhold actions until the view stabilizes. Only a successfully completed press event should predict UI state change; timeout/error/outcome unknown means revalidate conservatively rather than infer the result.

---

## 3. Implementation phases — do one reviewed phase at a time

### Phase 0 — Establish a real SENSE baseline and an accurate contract

**Files read; only focused test/benchmark additions if required:** `AGENTS.md`, `STATE.md`, `right_display.py`, `right_layout.py`, `left_display.py`, `frame_processor.py`, `vision_observer.py`, `recorded_test.py`, current tests.

1. Record current SHA/working tree, Python/OpenCV/Tesseract versions, camera source/rotation/resolution and source hashes. Identify available **unannotated** Driver ID and Level runs. Required evidence from `AGENTS.md`: `runs/level_raw_01/raw.mp4` (Level); `dmi_computer_vision/data/videos/dev/dmi_capture_quality_01`–`_04` (Main/Driver ID); accepted TWIN videos as regression only. These paths may exist only locally, not in the tracked Git tree. Use the operator's newer real-office captures if supplied. Do not claim the newest office session was reviewed when its raw footage is absent.
2. Compare images with/without successful right field detection and annotate the exact failure cause: no candidate / incorrect HSV mask / wrong position or size / incorrect contour / correct field but failed value OCR / display geometry error.
3. Record native **original-frame** ground-truth center/border points for a small representative set of target keys, Level controls and the grey field; add independent held-out examples and controlled lighting variations. Record true screen state and field/active values, not merely model predictions.
4. Measure on identical source frames: field detection recall/false positives; control identity/active-state recall and correctness; Level misses; monitor-corner and key-center jitter (median, P95, max); end-to-end receipt-to-result age; mean/P95 analysis time; OCR calls/time; overwritten/latest frames; processed FPS. Separate acquisition FPS from detection FPS.
5. Capture post-movement frames and compare camera alignment, focus, field exposure and detector `temporal_reset` reasons. Avoid attributing every failure to coordinate jitter before measuring.
6. Add fixture tests that reproduce at least the known grey-field failure and Level dropout where raw data is available. Report unavailable evidence as a gap.

**Exit criterion:** Reproducible baseline and known failure signatures; no runtime detector change.

### Phase 1 — Lighting-robust grey field and control localization (first actual implementation)

**Primary file:** `dmi_computer_vision/src/dmi/detection/right_display.py`.  
**Possible helper:** `dmi_computer_vision/src/dmi/utils/image_ops.py`.  
**Optional only after evidence:** localized `right_layout.py` / `left_layout.py` changes, SENSE-gated to avoid TWIN regressions.

1. Extract current `_detect_data_field()` into a clearly named HSV primary helper without changing its accepted output shape: `(bbox, measured_contour) | None`. Preserve `analyze_right_display()` and `_read_digits()` behavior for successful primary detections.
2. Implement a **second independent fallback** on the **rectified right display** if HSV fails or yields a demonstrably invalid field. Constrain the search to the observed upper-field portion of the display, not a whole-frame arbitrary rectangle.
   - Use grayscale/luminance **local contrast** against surrounding dark blue, not a single absolute threshold. Candidate tools: grayscale adaptive threshold or local-background difference; small morphological closing to join a pale bar; `Sobel`/Canny horizontal-and-vertical boundary support; rectangularity/aspect/relative width-height and in-frame validation.
   - Optional CLAHE on a **separate luminance copy** for edge detection only; do not blindly apply contrast enhancement to the BGR colors used for Level active-state classification or to OCR that already works.
   - Rank multiple candidates using **measured** local brightness contrast, aspect ratio, border support and spatial consistency; reject ambiguity rather than selecting a plausible but unproven rectangle.
   - Convert the winning measured contour/quad to the existing original-image output. The fallback must not return a rectangle inferred exclusively from layout defaults. If the existing `field_quad_from_contour()` expects actual contour geometry, provide it with a valid current-image contour, not artificial corners.
3. Only after the field is located, call **unchanged existing OCR**. Preserve the distinction between field detected/value unknown and field absent.
4. Test brightness gain/offset/gamma, mild white-balance/color-temperature shifts, JPEG compression and real low-contrast Level states. Identify ranges from the real sensor rather than choosing permissive thresholds solely to inflate recall. Never make a pale summary row or title background into a false grey field.
5. If real recordings demonstrate that buttons also fail due to illumination, add one **scoped** local-contrast fallback for their border evidence (prefer the existing relative-gradient `BorderEvidence` approach). Do not globally relax OCR or button activity thresholds. Exact identities still need current glyph evidence and duplicate/ambiguous identities must stay unknown.
6. Add field-fallback tests in `dmi_computer_vision/tests/test_right_display.py` and Level/geometry regressions. Check both bright and dark images, empty field, wrong-sized region, several competing pale rectangles, known positive examples, and TWIN outputs.

**Exit:** Higher field-region recall on held-out real SENSE samples, no new false positives on supported screens, existing OCR value accuracy preserved, and bounded measured processing overhead. Log/debug which detector (`primary`/`fallback`) succeeded without changing public output schemas unnecessarily.

### Phase 2 — Progressive Screen Locking

**Goal:** Detect each button, box, and field several times, save its stable position, and progressively build a complete screen layout.

**Files:**

- New: `dmi_robot_master/integration/screen_lock.py`
- Update: `dmi_robot_master/integration/vision_observer.py`

**Implementation:**

1. Create a simple screen-lock module that stores:
   - Current screen name (Driver ID, Level, etc.).
   - Confirmed buttons, boxes, and fields.
   - Stable pixel centers and bounding boxes.
   - Recent detection positions for unconfirmed elements.

2. For Driver ID and Level, define which elements are required and which are optional.
   - Use existing detector identities and real screen recordings.
   - Do not require every possible button or all 22 left boxes unless they are actually expected on that screen.
   - Other screens continue using the existing detection pipeline until supported.

3. When a screen appears, start collecting detections:
   - Each button, box, and field is checked independently.
   - Confirm an element after **3 consistent detections** from different frames.
   - The 3 detections do not need to be consecutive.
   - Check that the detected positions are reasonably close to each other.
   - Save the median center and detected bounding box.

4. Implement two simple locking states:
   - **PARTIAL LOCK:** Some elements are confirmed, while others are still being detected.
   - **COMPLETE LOCK:** All required static elements are confirmed.

5. During PARTIAL LOCK:
   - Immediately annotate confirmed elements using their saved positions.
   - Keep those annotations fixed.
   - Continue searching for missing elements.
   - Add each newly confirmed element to the annotations.
   - Do not restart detection for elements already confirmed.
   - Limit repeated expensive searches if an element cannot be found.

6. During COMPLETE LOCK:
   - Stop continuous full-screen detection.
   - Keep all confirmed annotations fixed.
   - Switch to the lightweight monitoring implemented in Phase 3.

7. Reset the lock when:
   - The screen changes.
   - The camera or monitor moves significantly.
   - The video source or resolution changes.
   - The current screen geometry becomes unreliable.
   - The vision session stops.

8. Important restrictions:
   - Never invent coordinates for missing elements.
   - Never mix detections from different screens.
   - Keep the original detector results separate from cached coordinates.
   - Cached annotations alone cannot authorize robot actions.
   - Do not change existing TWIN detection behavior.

**Expected Result:**
The detector builds a partial lock, progressively adds confirmed elements,
and eventually reaches a complete lock. Annotations stop flickering and
remain stable even when individual detections temporarily fail.

---

### Phase 3 — Lightweight Monitoring and Smart Updates

**Goal:** Avoid running expensive detection and OCR on every frame when the screen has not changed.

**Files:**

- `dmi_robot_master/integration/screen_lock.py`
- `dmi_robot_master/integration/vision_observer.py`
- Reuse existing OCR and icon-detection functions.

**Implementation:**

1. While the screen is completely locked, reuse its saved button
   and box positions instead of detecting them again.

2. Monitor the screen using inexpensive image comparisons:
   - Check the title area periodically (initially about once per second).
   - Check the grey field for changes.
   - Check relevant button appearance and left-side mode icons.
   - Check that the monitor position remains stable.

3. Only run OCR when needed:
   - If the title area changes, run title OCR to identify the screen.
   - If the grey field changes, run field OCR to read its new value.
   - Avoid repeated OCR when these regions remain unchanged.
   - If a changed field cannot be read, report an unknown value
     instead of presenting the previous value as current.

4. Handle button clicks intelligently:
   - **Digit click:** Keep locked positions and update only the field value.
   - **Level selection:** Keep positions and update relevant field/button states.
   - **Confirm / Close:** Check whether the screen has changed.
   - **New screen:** Clear the old lock and start Phase 2 again.

5. Continue checking dynamic elements:
   - Enabled/disabled Level buttons may change without a new screen.
   - Blinking icons must continue updating using the existing logic.
   - Do not freeze dynamic information just because positions are locked.
   - Manual screen interactions must also be detected.

6. If the screen appears different or its geometry becomes unreliable:
   - Run the existing full detector again.
   - Rebuild the lock if necessary.
   - Keep occasional full checks if real tests show they are needed.

7. During PARTIAL LOCK:
   - Continue checking for missing elements at a limited frequency.
   - Keep confirmed annotations stable.
   - Avoid repeatedly processing the entire screen at maximum frequency
     when the same elements remain missing.

8. Keep the live camera preview running normally:
   - The video continues updating.
   - Static annotations use saved positions.
   - Field values, button states, and icons update when needed.

**Expected Result:**
The system performs much less full detection and OCR while the
screen is unchanged, resulting in better processing speed and
more stable annotations.

---

### Phase 4 — Stable Coordinates and Movement Detection

**Goal:** Keep confirmed button centers fixed until a real screen or camera movement requires new coordinates.

**Files:**

- `dmi_robot_master/integration/screen_lock.py`
- `dmi_robot_master/integration/vision_observer.py`

**Implementation:**

1. Use the median pixel center calculated in Phase 2 for each
   confirmed button, box, or field.

2. After confirmation, do not continuously update that center
   using every new detector result.

3. Ignore small detection variations caused by normal image noise.

4. Periodically check whether the monitor or screen geometry
   has genuinely changed.
   - Small detection noise: keep the locked coordinates.
   - Confirmed significant movement: invalidate the affected lock
     and detect the coordinates again.
   - Use simple pixel-distance checks with thresholds determined
     from real recordings, not arbitrary fixed values.

5. During PARTIAL LOCK, adding a newly confirmed element must not
   move the centers of previously confirmed elements.

6. During COMPLETE LOCK, keep all static annotation positions fixed
   while the screen remains valid.

7. Keep raw detector coordinates available for debugging and comparison.

8. Use the locked pixel centers with the appropriate validated
   pixel-to-millimeter mapping, but do not modify calibration logic here.

9. Keep robot safety checks unchanged:
   - A cached center is not fresh detection evidence.
   - Current target identity and eligibility must still be verified.
   - Existing calibration and action-safety requirements remain mandatory.

**Expected Result:**
Buttons have stable pixel centers and stable annotations.
Minor detection noise no longer causes coordinate movement.
Real camera or monitor movement triggers reacquisition.

**Note:**
Homography improvement and the existing 3 mm held-out calibration
accuracy requirement belong in Phase 5, not Phase 4.

---

### Testing Strategy for Phases 2–4

Keep testing simple, focused, and token-efficient.

1. Check that an element detected in 3 different consistent frames
   becomes locked, even when the frames are not consecutive.
2. Check that confirmed elements remain stable while missing elements
   continue being detected.
3. Check that partial lock becomes complete lock when all required
   elements are confirmed.
4. Check that missing elements never receive invented coordinates
   and that retries do not continue indefinitely.
5. Check that annotations remain fixed despite temporary detector misses.
6. Check that digit clicks update the field without restarting
   full-screen detection.
7. Check that screen changes and real monitor movement reset the lock.
8. Check that dynamic icons and Level button activity still update.
9. Check that cached coordinates cannot bypass fresh-evidence checks.
10. Verify that existing TWIN behavior remains unchanged.

Run focused tests during implementation. Run the full regression
suite at the end or whenever a change makes broader testing necessary.

---

### Phase 5 — One SENSE monitor-plane homography and stable registration

**Primary:** `dmi_robot_master/integration/recorded_test.py`; reuse `sense_calibration.py`, `calibration.py`, relevant calibration tests. No change to motion driver.

1. Treat the homography as belonging to the **physical SENSE touch plane**, not Driver ID as a UI title. For coplanar right/left areas and same camera/source/crop/origin, an independently validated map may be reused by Driver ID, Level and train-workflow controls. Screen-specific calibration remains unnecessary **only if** held-out point accuracy and coverage support reuse. Do not assume left-region coverage from a right keypad fit.
2. `RecordedTestProjector.registration()` currently saves `_view_anchor` but **recomputes** `cv2.getPerspectiveTransform(current, recorded)` from each noisy set of monitor corners. Gather 3–5 consistent, image-evidenced monitor geometries, derive a robust session anchor, compute **one** registration matrix `R_session`, then reuse it. If current camera basis already exactly equals the recorded basis, the registration may be the identity; do not force identity merely because camera/monitor were reported fixed.
3. Use the existing saved `H_calibration` and session registration: `p_reference ~ R_session * p_current`; `p_mm ~ H_calibration * p_reference`. Compose the transforms if helpful, but preserve clear provenance. All calculations must use the exact same native frame size, source transforms and origin convention.
4. Continue cheap/bounded **monitor-alignment checks** using current measured edges/corners or independently validated stable image anchors. If camera/monitor shifts, occludes, loses framing, changes zoom/focus/crop or fails registration tolerance, **invalidate the locked mapping and dependent target eligibility**; do not silently refit it during an action. Camera autofocus/auto-exposure may alter image appearance but must not be mistaken automatically for physical camera movement.
5. Avoid `R_session` invalidation on a one-frame noisy corner fit unless evidence genuinely indicates movement; require robust agreement with the fixed reference while failing closed when image geometry is ambiguous. Preserve existing left/right joined-geometry validations; do not use a fabricated shared border.
6. Preserve calibration/source identity, file digest/origin epoch/geometry contracts, finite projective domain, bounds, and normal rejection of numerically unacceptable calibration. The current **experimental recorded** path explicitly bypasses ordinary 3 mm acceptance; do not promote it to normal validated or lower the requirement.
7. Quantify independent **held-out physical errors** (mm) at multiple Driver ID and Level positions, spread across upper/lower/left/right edges of the actual touch plane, with repeated measurements to isolate detection jitter. Compare an affine and homography only using existing fit/inspection logic and independent control-level holdouts. Choose/claim validated coverage only when the prescribed maximum held-out error ≤3 mm; report failures honestly.
8. Do not change the robot reference database or introduce another motor offset in this step. Test mapping with **read-only predicted XY**, no physical command side effects.

**Exit:** One stable mapping per fixed-camera session; independent physical error table and map coverage; pixel-to-mm output remains consistent across same-plane screen changes. Physical acceptance stays pending unless the actual held-out measurements pass.

### Phase 6 — Minimal guarded action integration (requires explicit authorization)

**Why this is a separate phase:** User wants immediate reuse of locked coordinates. Currently the GUI/experimental press route requires a **fresh `VisionSession` observation and direct center match**, which expires at 1.5 s. A persistent cache alone cannot satisfy that contract; disabling the guard would make the system less safe.

1. First support locked screen presentation and **read-only XY inspection** while expensive detection is idle. Do not claim click readiness from cache freshness.
2. Evaluate a **fast, fresh, direct ROI verification** for the selected button, run against the newest real camera packet when a click is requested (or against an already-verified sufficiently recent packet): check correct screen/context, monitor anchor, measured target border, image label/active state where needed, unoccluded region, and locked vs measured geometry. Use the original algorithm's measured-border/identity principles or a validated equivalent. Do not use only a thumbnail hash or an old screenshot as proof of button identity. Limit image age to the current contract.
3. This ROI verification may be cheaper than full-screen OCR. It must emit **its own genuinely current evidence with source frame index and original capture timestamp**, without modifying old `Observation` timestamps. An action adapter may then use the locked center only if current direct proof and calibrated mm accuracy/uncertainty/bounds all agree.
4. Before such a verifier is formally tested and approved, fall back to a **single on-demand full detection** for the specific click. Never skip current evidence entirely, forge a recent observation, or increase existing 1.5 s lifetime to make the button enable.
5. Maintain the 4 px direct-match requirement until a new physically bounded tolerance/uncertainty rule is independently measured and explicitly approved. The user-suggested ±10 X/±5 Y is a hypothesis, **not** action authorization. Any policy adjustment must be justified with real pixel-to-mm uncertainty and new negative tests.
6. An action event hook (if authorized) may minimally tell `VisionObserver` that a press **finished** and which semantic control was attempted. Reuse the existing runner callback/result path. It must not assume the DMI accepted the press. Unknown outcome, failed return, missed contact or timeout means more conservative visual revalidation. Don't modify the robot UDP/controller, physical press duration, safety limits or GPIO code.
7. `right/field/input` is currently exported as `kind='field'`, and the existing experimental `RecordedTestProjector` maps only `kind='button'` targets for pressing. The grey confirmation field being visually button-like does **not** authorize making that field physically pressable in this plan. Support its **visual transition semantics** now; adding an action type/eligibility for it requires separate explicit review.
8. Preserve action readiness, busy/no queue, no automatic retries, origin/calibration verification, frame source, and movement envelopes. Successful on-screen observation does not certify physical movement/contact/retraction.

**Exit:** Cached geometry gives stable preview and fast selection; where a fresh independent ROI check is validated, on-demand full detection is avoided. All negative/expiry/occlusion/identity tests still block unsafe actions. If exact required evidence cannot be obtained cheaply, keep the on-demand full detector.

### Phase 7 — Full evaluation, optimization and acceptance

1. Compare four matched modes **on the same sources and hardware**:
   - A. Existing baseline full detection.
   - B. Lighting/fallback improvements with full detection.
   - C. Screen lock + targeted updates (no physical action changes).
   - D. C plus locked homography and any separately approved action ROI guard.
2. Report per-screen accuracy: title recognition, grey-field detection/value exact match, each button/box identity presence, Level active status, mode blink/steady state, false positives and false retention; count missed and delayed transitions; compare results to manually checked native frames.
3. Report performance: source FPS/bridge FPS separately, processed full-detector FPS, full-detector call count per minute idle vs transition, title OCR/field OCR calls and time, cheap-check time, mean/P95 analysis time, total receipt→published age, GUI preview delivery, CPU load where available, overwrites and skipped frames. A reduction in full calls is not proof of better overall latency unless measured.
4. Report stable geometry: original-frame center median/P95/max variation, corner jitter, repeated cross-screen converted XY variance, mm residual table, held-out max error, bad calibration rejection. Do not interpret a fixed displayed center as evidence of physical accuracy.
5. Prove failure/recovery: same-title digit-value change; Level activity change with identical title; confirmation/close title transition; unexpected manual touch; new screen without prior workflow; 1–5 frames of missing buttons; prolonged blank/occluded/overexposed video; camera restart/loss/recovery; post-motion vibration; source/frame size change; photo/brightness change; unknown/partial title; 1.5 s action-evidence expiration; stale locked cache; invalid/nonaccepted homography.
6. Run existing SENSE tests plus frozen TWIN regressions. Recheck compact JSONL, annotations, targets, and live preview outputs for compatibility. Compare against the exact current branch baseline and document any intentional SENSE-only output addition.
7. Review both correctness and performance, using the required two-reviewer cycle. Produce one concise canonical evidence package per approved step, as defined by `AGENTS.md`. Physical validation remains explicitly distinct from software/replay completion.

---

## 4. Detailed technical decisions and edge cases

### 4.1 Crop comparison design

- Reference ROIs come from **accepted measured screen geometry**, transformed consistently to the latest native frame. Keep small grayscale/edge descriptors in memory; do not store image files per frame.
- Difference must tolerate sensor noise, compression and **global exposure fluctuations** without allowing real character changes to disappear. Compare normalized local contrast and/or edges, not just absolute RGB. Calibrate threshold against stationary real-camera sequences and held-out value changes. A heavily changed ROI with low OCR confidence is **uncertain**, never “unchanged.”
- Use independent ROIs for title, grey-field **text interior**, grey-field **border**, Level active-state glyphs, relevant buttons and `box_14/16`; avoid one global mean difference masking a small digit/icon change.
- A changed title crop triggers OCR; the title OCR result must be an exact supported state before committing a new identity. Unknown does not mean “keep old title forever.” Add a bounded retry/transition timeout and full reacquisition on uncertainty.
- OCR frequency should be driven by change/events plus bounded audits. An initial **~1 s title-crop check** does not mean mandatory OCR every second. Icons that blink faster need more frequent separate visual sampling.
- If locked ROI registration becomes invalid due to monitor movement, cropped OCR cannot safely establish continuity; reacquire geometry.

### 4.2 Action-to-refresh matrix (initial proposal, refine from actual UI recordings)

| Known action/event                                                         | Prediction                                                                            | Cheapest follow-up                                                       | When to unlock                                                      |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Driver ID `digit_0..9`, `delete`                                           | Field text changes, same Driver ID page                                               | Compare grey field; call `_read_digits()` on **current** crop if changed | Title/geometry/field border changes unexpectedly or state uncertain |
| Driver ID `decimal` / other visible actions                                | Could change text or state                                                            | Title + field + relevant button-region comparison                        | If expected effect is not confirmed, or new title/layout appears    |
| Level `level_*` or other selection                                         | Grey field value and/or button `active` state and icons change, page may remain Level | Field crop/OCR + changed Level glyph/activity ROIs + left modes          | New page, changed cell layout, unresolved activity or title         |
| Confirming **grey field** (when an external/authorized action is observed) | Often page navigation                                                                 | Title crop check immediately after view settles                          | New title or layout ⇒ ACQUIRING                                     |
| `close` / X                                                                | Often page navigation                                                                 | Title crop check + structural context                                    | New title or layout ⇒ ACQUIRING                                     |
| Train workflow navigation / unmodeled action                               | Unknown or page navigation                                                            | Broad cheap change detection; full acquire on ambiguity                  | Any transition or insufficient evidence                             |
| Robot movement _without confirmed click_                                   | Possible occlusion/vibration, **no presumed UI effect**                               | Wait for clear/stable current image, check source/anchor                 | If monitor geometry altered / state uncertain                       |
| Manual touch / unexpected change                                           | Unknown                                                                               | Cheap ROI/global change detector, title and affected ROI checks          | New/unknown screen, invalid geometry or unexplained layout          |

Make these rules **proposals**, not robot-driving instructions. The application may not currently support clicking field targets; this table describes observation reactions only. Never infer UI state from the intended action label without checking the actual image.

### 4.3 Lock acceptance / recovery policy (recommended starting assumptions)

- Confirm each required control independently after at least 3 consistent detections from different frames.
- Use a recent, bounded history (initially around 5 observations per control). Frames do not need to be consecutive.
- Add each confirmed control immediately to PARTIAL_LOCK.
- Enter LOCKED only when all required static controls are confirmed.
- If controls remain missing, use bounded retries rather than
  running full detection indefinitely.
- Never combine evidence from different screens or camera geometries.
- Profile coverage is _screen specific_. Distinguish required static, optional static and dynamically visible. Do not require `box_16` to contain an icon, or an inactive Level button to be bright. Static **box geometry** may be present while icon content is absent.
- Use **median** native centers; require a small, justified raw dispersion threshold. Do not reuse one frame's outlier corner to initialize the lock. Center stability cannot compensate for an incorrect identity.
- Initial pilot: allow cached display geometry to remain visible during short uncertain intervals, **marked as cached**; drop its action usability. Do not increase previously accepted `LivePreviewState` display hold or direct evidence lifetime as a shortcut.
- Every lock/relock gets a generation ID and reason; selection and calibration registration must refer to the same generation. Invalidate on source/calibration/origin change, verified monitor movement, new page, or shutdown.
- If a screen remains visually static, full detector calls should be rare; **bounded refresh** is still required to discover undetected drift/state changes. Tune intervals from actual misses, not arbitrary FPS claims.

### 4.4 Registration and coordinate reference

```text
native camera frame pixel (x,y)
    -> session registration R_session into recorded reference image
    -> recorded H_SENSE into robot millimeters (X,Y)
```

- Never combine already registered and raw coordinates in one median sample. Persist the reference basis, camera transforms and calibration provenance beside the lock.
- If the recorded calibration is rejected or only experimentally authorized, continue to show predictions with truthful status but do not mark them ordinary action-ready.
- Source scene coordinates, right/left logical region coordinates, rectified crops, and calibrated absolute millimeters must remain distinct. Do not invent a universal pixel-per-mm scale.

### 4.5 No hidden GUI/robot scope expansion

The objective is computer vision and mapping. Do not rebuild Flet screens, add autonomous robot sequences, modify homing/motion code, change press durations or bypass physical-action validation. A tiny **completed-action notification** may be necessary to optimize observation; otherwise the passive cheap visual change checks must work independently of robot integration. A press-result event does not prove the DMI changed states.

---

## 5. Explicit test matrix for the agent

Add focused unit/replay tests in appropriate existing files (`dmi_computer_vision/tests/`, `tests/test_robot_integration.py` or one new `tests/test_screen_lock.py`) rather than a separate test framework. **Do not run real robot hardware in automated tests.**

| Test ID | Input/scenario                                                            | Expected                                                                                                            |
| ------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| F1      | Grey field brighter/darker, cooler WB, JPEG noise                         | Same measured field region and OCR as baseline; no field if evidence absent                                         |
| F2      | Large bright title/summary patch or two competing rectangles              | No false grey-field lock; ambiguity explicit                                                                        |
| F3      | Level dim/inactive glyphs                                                 | Identity and `active` remain evidence-based; null when uncertain                                                    |
| L1      | 1 good full frame then ambiguous frames                                   | No lock                                                                                                             |
| L2      | Different controls detected in different subsets of frames                | Confirm each independently; progressively build PARTIAL_LOCK; enter LOCKED when all required controls are confirmed |
| L3      | One outlier center / different screen / duplicate control                 | Reject outlier; no false lock across states                                                                         |
| L4      | Driver ID left 22-box expected view vs Train workflow replacing it        | Profile doesn't invent missing boxes or prevent valid workflow                                                      |
| S1      | Unchanged title, digit changes grey field                                 | Only current field OCR/value update; no full-screen relocalization                                                  |
| S2      | Level unchanged title, selection toggles activity/mode                    | Update dynamic status correctly; geometry remains locked                                                            |
| S3      | Grey confirmation / close causes new title                                | Old lock invalidated; full acquisition on new state                                                                 |
| S4      | Manual touch changes state without application event                      | Cheap change detector still discovers transition                                                                    |
| S5      | Blinking box_16 on/off/steady, 5 s holds                                  | Existing mode history remains correct; no false frozen mode                                                         |
| S6      | Camera drops frames; frame source stale >1.5 s                            | Freshness expires; cached layout cannot renew action evidence                                                       |
| S7      | Partial/unknown/occluded image, monitor reposition                        | Lock/action support invalidated; recovery reacquires before new approval                                            |
| S8      | Long idle > `FrameProcessor` 1 s temporal gap                             | Controller lock remains logically separate; triggered full scan handles reset correctly                             |
| H1      | Jittered 1–3 px corners/centers on same physical setup                    | Stable locked R/centers; low converted XY variation                                                                 |
| H2      | Real camera/monitor shift, resize/rotation/source change                  | Registration/lock invalidated; no silent recenter                                                                   |
| H3      | Independent Level and screen-edge physically measured targets             | Held-out mm error reported; ≤3 mm required for normal acceptance                                                    |
| A1      | Cached locked button, no fresh independent target proof                   | **No action**, even though preview still shows center                                                               |
| A2      | Fresh correct target ROI and valid calibration/context                    | Read-only eligible status / optional authorized action if existing guards pass                                      |
| A3      | Wrong label, inactive Level control, stale view, large shift, invalid map | Action blocked; no retry or substituted old coordinate                                                              |
| R1      | Frozen TWIN Main/Driver ID/Level/train records                            | Same accepted detections/output contracts; no SENSE leakage                                                         |
| P1      | Matched baseline vs optimized replay                                      | Exact accuracy, mean/P95 age, OCR calls, full calls, skips/overwrites documented                                    |

Provisional success goals to establish after baseline (avoid inventing achieved numbers): substantially improve field **recall** on the failure captures with no increased false positives, correct screen changes and same-title updates on all representative test sequences, no lock on ambiguous frames, stable locked centers, significantly fewer full-detector/OCR calls during steady state, and no increase in stale or unsafe action eligibility. For homography, unchanged **≤3 mm maximum held-out error** is non-negotiable for normal acceptance.

### Run commands (adapt to the repository's actual environment)

```bash
# From repository root; prerequisites: current project deps and Tesseract where tests need OCR
python -m unittest discover -s dmi_computer_vision/tests -v
python -m unittest discover -s tests -v
# Locate and run the existing Flet/GUI-focused tests if modified by an authorized phase.
# Use recorded/replay scripts for matched SENSE timing; do not infer hardware FPS from MP4 FPS.
```

If optional deps are missing or some original raw fixtures are absent, report **what was actually run** and what remains unverified; never mark the full matrix as passed from mocked-only tests. Preserve developer source videos, accepted run folders and reference measurements.

---

## 6. Suggested small change sets and review gates

| Review gate                      | Preferred production files                                                        | Deliverable / approval criterion                                                                         |
| -------------------------------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **G0 Baseline**                  | No runtime edits                                                                  | Failure clips, ground-truth definitions, baseline summary                                                |
| **G1 Lighting**                  | `right_display.py`; optional image helper                                         | Field primary/fallback correctness; SENSE improvement; TWIN unchanged                                    |
| **G2 Screen lock**               | New `screen_lock.py`, narrow `vision_observer.py` hook                            | 3–5 frame lock, expected profiles, invalidations; read-only cache only                                   |
| **G3 Selective detection**       | `screen_lock.py`, `vision_observer.py`, optional `processing_policy.py` reuse     | Same-title field update, transition/title checks, Level activity, blinking, bounded audits, reduced cost |
| **G4 Stable coordinates**        | `screen_lock.py`, observer projection/presentation; optional SENSE-only smoothing | Median locked original-pixel targets, no jitter/drift, explicit evidence separation                      |
| **G5 SENSE homography**          | `recorded_test.py` and existing calibration inspection/tests                      | Fixed session registration and independent cross-screen error report; unchanged 3 mm criterion           |
| **G6 Physical-action readiness** | Minimal action bridge only after independent approval                             | Fresh ROI direct proof OR on-demand full scan, no cache-only clicks, expiry/safety preserved             |
| **G7 End-to-end evaluation**     | Mostly tests/benchmark harness                                                    | Matched accuracy/latency comparison, complete regressions, hardware gaps stated                          |

Avoid scattering screen-lock state across `FrameProcessor`, preview worker, GUI widgets and robot controller. Keep the state machine cohesive and its integration small. A single new module plus focused edits/tests is preferable to many premature abstractions. Retain existing file names/contracts unless necessary.

### Agent completion checklist for each gate

- [ ] Confirmed local HEAD/status and honored existing `AGENTS.md`/`STATE.md` requirements.
- [ ] Reproduced real failure and noted exact source/ground truth or acknowledged unavailable raw evidence.
- [ ] Made only the authorized SENSE-scoped change; no GUI/motor/TWIN behavioral scope creep.
- [ ] Added and ran positive, negative, source-change, stale, unknown and regression tests relevant to the gate.
- [ ] Measured accuracy **and** processing cost against the same frames and hardware/environment.
- [ ] Confirmed no fabricated geometry/identity, stale-evidence renewal, changed schema or calibration bypass.
- [ ] Obtained the repository-mandated `code_review` + `step_checker` final-version verdicts (or disclosed unavailable review).
- [ ] Produced one canonical concise review/evidence package and a chat summary; no per-step extra Markdown reports.
- [ ] Requested explicit acceptance before updating `STATE.md`, committing/pushing or starting the next step.

---

## 7. Things **not** to implement prematurely

- No YOLO/CNN or learned UI detector until the stronger rule-based/fallback + lock baseline is measured and shown insufficient.
- No repeated whole-screen detection for a confirmed unchanged layout purely to obtain more averaged centers.
- No using a screen title alone as proof that field values, active labels or mode icons cannot change.
- No using a default layout to **generate** a missing key or infer an unreadable Level identity from fixed slot order.
- No screenshot-template matching to classify screen identity; current OCR and image-supported geometry remain the evidence source. Small crop comparison is allowed **only as a temporal change flag**.
- No unchecked indefinitely reused button coordinates for actions; preserve genuinely fresh proof and bounded recovery.
- No generic **±10/±5 px** click permission, no relaxation of 4 px direct evidence or ≤3 mm calibration requirements without a separate validated, explicitly authorized change.
- No repeated camera clients, growing frame queues, per-frame disk crops, automatic robot retries, new GUI, or calibration-rejection override.
- No claim that a working Driver ID press validates a whole SENSE touch plane; do not silently extend experimental calibration authorization to grey fields or previously unsupported actions.

---

## 8. Definition of complete success

The upgraded SENSE system should, **based on measured real-camera results**, (a) detect grey fields and supported controls reliably over normal lighting variation; (b) recognize Driver ID/Level from a cold start and lock a correct measured layout from a small consistent observation window; (c) retain fixed button centers until actual geometry/screen invalidation; (d) stop expensive full detection/OCR while static, yet correctly recognize same-title field/activity/icon changes and new title/layout transitions through cheap checks/events; (e) reuse one fixed validated camera-to-SENSE-plane homography across coplanar UI states without per-frame registration jitter; and (f) keep cached presentation separate from fresh action evidence, preserving existing physical safeguards.

**No implementation is complete merely because annotations look stable.** Completion requires measured recognition precision/recall, transition coverage, latency/cost improvement, independent mm accuracy evidence, unchanged frozen TWIN outputs, reproducible negative tests, and a clear statement of what has **not** been physically validated.
