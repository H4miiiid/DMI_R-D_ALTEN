# DMI Hardware Test Feedback

## Context

I completed an initial hardware test using the existing Flet GUI, live camera, CV detection pipeline, homography calibration and robot.

Overall, the detection and robot positioning accuracy were encouraging. The following observations and improvements should be addressed incrementally.

**Important:** Do not implement all improvements at once. Investigate one item at a time, explain your findings, and wait for my approval before making changes.

## 1. Homography calibration — Preserve accuracy across different setups

**Observation:**
The existing homography performed accurately during physical tests with Key 1 and Key 4.

During each testing session, the camera and DMI monitor remain fixed. However, when setting up the equipment for another session, their positions may change slightly by a few millimeters or centimeters.

**Request:**

- Preserve the existing homography implementation and the successful calibration behavior.
- Investigate how to make calibration robust to small camera or monitor repositioning between sessions.
- Prefer reusing stable DMI reference points and updating the transformation when necessary, rather than requiring complete manual calibration every time.
- Check whether setup changes can be detected reliably and whether the homography can be recalculated using current observations and previously measured physical references.
- Ensure the transformation remains accurate for different buttons and DMI screens, within their validated calibration regions.
- Do not silently reuse an outdated transformation or introduce complex calibration methods without evidence.

**Expected outcome:**
Reliable pixel-to-mm conversion across testing sessions, even when the camera or monitor is repositioned slightly, while maintaining the accuracy already observed with Keys 1 and 4.

**For now:** Investigate possible solutions and recommend the simplest reliable approach before implementing changes.

## 2. Annotated video flickering — Keep the video continuously visible (Completed)

**Observation:**
The GUI has two separate video sections:

- The raw live camera video, which renders correctly and remains visible.
- The annotated video, which frequently flickers or disappears when detections are temporarily missing.

The main problem is not small changes in detected coordinates or individual annotations appearing and disappearing. The problem is that the entire annotated video preview appears and disappears, making it uncomfortable to use.

**Request:**

- Investigate why the entire annotated video disappears or flickers between detection updates.
- Keep the annotated video continuously visible, independently of whether the current frame contains successful detections.
- If no detections are available for a frame, continue displaying the video without annotations rather than hiding or clearing the entire preview.
- Update annotations independently and smoothly as new detection results become available.
- Allow individual annotations to appear, disappear or change coordinates when appropriate, without resetting the whole video.
- Avoid unnecessary image-widget recreation, blank frames or preview-state resets if they are causing the issue.
- Preserve the existing raw live preview and avoid introducing a separate detection pipeline.
- Do not retain stale annotations for robot-action authorization.

**Expected outcome:**
The annotated video remains continuously visible and visually smooth, even when detections temporarily fail or individual annotations change.

**Completed — software implementation accepted 2026-11-04:** SENSE and TWIN use
the same live overlay helper, with the existing four-pixel display deadband and
button/title retention for at most two missed updates and 1.5 seconds. Geometry,
content changes, expiry and Stop invalidate retained annotations; robot actions
continue using fresh validated observations independently of the display.
TWIN viewing is observation-only and does not load SENSE calibration. Offline and
recorded-camera checks are complete; live-camera/native GUI smoothness remains an
office check. See [STATE.md](STATE.md) for accepted evidence, results and limits.

## 3. Robot returning home after pressing (Completed)

**Observation:**
After clicking a button, the robot does not return to its initial home position `(0, 0)`.

**Request:**

- Investigate the existing `MOVE_AND_CLICK` command sequence and robot controller behavior.
- After a successfully completed press, ensure the tool is retracted and implement a safe return to the defined home position `(0, 0)`.
- Verify the coordinate convention, allowed travel bounds and appropriate command ordering.
- Do not automatically move home after an uncertain or failed press unless the controller's safety behavior explicitly supports it.
- Prevent new pressing commands while the robot is still completing the current action.

**Expected outcome:**
After a successful press, the robot returns safely to home and is ready for the next operator command.

**Completed — software implementation accepted 2026-11-05:** The receiver reuses
the existing return-to-zero option. After contact and confirmed Z retraction, XY
returns to `(0, 0)` before DONE; the GUI stays busy throughout. Missing contact or
failed retraction prevents the XY return. Offline tests pass; both Pi files must
be updated and physical return validation remains pending. See [STATE.md](STATE.md).

## 4. Display detected OCR field values in the GUI (Completed)

**Observation:**
OCR seems to read values from the DMI fields, but the results are not conveniently visible in the GUI.

**Request:**

- Add a small section in the existing GUI showing the latest OCR-recognized field names and values.
- Reuse the OCR output already produced by the detection pipeline.
- Clearly indicate missing or stale values.
- Avoid introducing a separate OCR processing pipeline.

**Expected outcome:**
I can easily compare the detected values with the actual DMI display during hardware testing.

**Completed — software implementation accepted 2026-11-05:** A read-only OCR
section below the preview displays existing field names and values, with explicit
missing, unreadable/unconfirmed and stale states. Stop and screen/session changes
clear old values. No extra OCR or robot-action changes were added. Offline and
recorded-sample checks passed; native GUI/live-camera readability remains an office
check. See [STATE.md](STATE.md) for evidence and limits.

## 5. Stabilize and round displayed coordinates (Completed)

**Observation:**
Displayed pixel and millimeter coordinates change frequently, sometimes by very small amounts, and the floating-point precision makes the GUI difficult to read.

**Request:**

- Round displayed millimeter coordinates to one decimal place.
- Round displayed pixel coordinates to whole pixels.
- Apply an approximately 2 mm deadband to GUI coordinate updates to suppress small visual fluctuations.
- Preserve full-precision coordinates for calibration and robot commands.
- Do not use display smoothing to authorize movement or hide genuine target changes.
- Reset the displayed coordinate baseline when the selected target or screen changes.

**Expected outcome:**
Cleaner, more readable and visually stable coordinates without affecting actual robot positioning.

**Completed — software implementation accepted 2026-11-05:** GUI pixels use whole
numbers and millimeters one decimal. Live XY updates when either axis moves at
least 2 mm from the last displayed baseline. Identity/context changes, loss,
expiry, Stop and unavailable mapping reset it. Action dialogs use current values;
calibration and robot commands retain full precision. Offline checks passed;
native GUI/live-camera readability remains an office check. See [STATE.md](STATE.md).

## Implementation rules

- Address one issue at a time. Issue 1 is deferred and Issues 2–5 are completed.
- First inspect the current implementation and report findings.
- Do not modify code until I approve the proposed correction.
- Make minimal, targeted changes and avoid unrelated refactoring.
- Preserve the accepted TWIN detection baseline and existing safety mechanisms.
- Run relevant regression tests after each change.
- Clearly distinguish offline verification from physical hardware validation.
- Wait for my next instruction before proceeding to another issue.

## Current status

Initial hardware testing is encouraging, particularly homography accuracy for Keys 1 and 4. Further physical validation is required for other controls and screens.

Issue 1 remains deferred at the user's request. Issues 2–5 are completed and
accepted as software implementations (Issue 2 on 2026-11-04; Issues 3–5 on
2026-11-05). Their physical/native-GUI checks remain pending as documented.
The user withdrew the additional pre-initialization nudge extension and requested
retaining the existing raw-step/manual workflow. Its new GUI/API/protocol and
movement-helper changes have been removed; GUI 5 mm movement still requires
initialization. Issues 2–5 remain accepted and Issue 1 stays deferred.
