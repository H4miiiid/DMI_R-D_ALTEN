# Robot and DMI Vision Integration

## Purpose

Connect the existing DMI detector to the robot's real camera. Detect and annotate
the visible screens, buttons, fields and boxes; convert their image centers to
robot coordinates; then test one physical button press by its label.

Implement one phase at a time. Keep the first integration small and easy to test.
Do not build the future backend or redesign the GUI as part of this work.

## Development from home

Implement all six phases from home before testing on the physical robot.
Use existing recordings through the live processing path, synthetic calibration
points and fake robot/transport objects for development. Hardware availability
must not block implementation or require physical validation between phases.

Keep real camera and robot settings configurable. Ask only for hardware facts
needed to choose an implementation; leave deployment-only settings unresolved
and documented when they are not yet available. Do not guess the final setup.

Distinguish **implemented and tested offline** from **validated on hardware**.
Recorded-video calibration is a development example: it cannot be reused as the
physical robot calibration. Fit and validate a new calibration on the installed
robot camera before enabling movement. Mark offline artifacts as simulation;
hardware execution must reject them.

## Read before working

- Read this file and the files involved in the current phase.
- Read the root `STATE.md` when present to resume integration work from the
  latest handoff. Create it when Phase 1 implementation begins.
- For vision changes, also follow `dmi_computer_vision/AGENTS.md` and read
  `docs/STATE.md`, the relevant workflow section and relevant output requirements
  inside that directory. Its accepted V2 behavior remains the baseline.
- Read `dmi_computer_vision/review.md` for known detector limitations.
- The root README is a GitLab template, not a description of working behavior.
- Check the current code before acting: files and imports may have changed since
  the review. Do not overwrite unrelated user changes.

## Existing responsibilities

- `dmi_computer_vision/`: detection, temporal processing, annotations and logs.
  Reuse `FrameProcessor`, `process_live` and `LatestState` where appropriate.
- `dmi_robot_master/`: PC command handling, GUI, XML scripts and
  `DmiPositions.json` with known robot XY positions in millimeters.
- `dmi_robot_rasp/`: Raspberry Pi GPIO, motors, sensors and command execution.
- `dmi_robot_common/`: configuration loading, logging and existing UDP transport.
- `dmi_robot_config/`: shared PC and Raspberry Pi YAML configuration.

Keep image processing separate from camera acquisition and motor commands.
The intended flow is:

```text
robot camera -> recent frame -> existing detector -> annotated preview
                                           |
                                           v
                              labeled centers in pixels
                                           |
                                           v
                              validated calibration -> centers in mm
                                           |
                                           v
                              fresh target selected by label
                                           |
                                           v
                              existing robot transport -> move and press
                                           |
                                           v
                              new camera observation verifies the result
```

## Code standards

- Reuse working code. Add only the functions needed for the current phase.
- Use clear names, normal formatting, explicit units and type hints at interfaces.
- Prefer straightforward functions and small classes with one responsibility.
- Keep entry points short. Keep calibration math, output conversion and robot
  execution separate, without creating a framework or many tiny wrapper files.
- Add integration helpers under a small `dmi_robot_master/integration/` package
  when needed. Camera-specific hardware code belongs beside its source adapter.
- Avoid duplicated detectors, large controller files, wildcard imports, dynamic
  method dispatch where a simple mapping works, and compressed one-line logic.
- Do not add arbitrary file-length limits or split files merely to meet a number.
  Split when responsibilities become difficult to understand.
- Use one consistent import strategy. Resolve config/assets relative to their
  owning files or explicit configuration, not the current working directory.
- Make device ownership and cleanup explicit. Release cameras, sockets and GPIO.
- Log useful progress and failures. Do not swallow errors or claim success after
  a failed command. Avoid expensive logging inside individual motor steps.
- Keep dependencies minimal and document the exact commands that actually work.
- Do not commit or push without the user's instruction.

## Phase 1 — Make the existing robot interface consistent

Preserve the base robot implementation. This phase prepares its existing
interfaces for CV integration; it is not a general cleanup or rewrite. Prefer
small integration adapters that call the existing controller and robot methods.
Small direct changes are allowed when they fix a demonstrated integration
blocker more simply than an adapter, such as an incorrect import, config path or
method call. Explain why each base-code change is necessary and verify that the
existing command behavior is preserved.

Do not change motor timing, movement algorithms, homing, GPIO assignments, the
wire protocol or GUI behavior merely to simplify integration. Report unrelated
problems separately. If a hardware defect prevents a reliable test, identify it
explicitly and propose a focused fix rather than folding it into a broad refactor.

1. Inspect master, slave, robot methods, imports, config paths and dependencies.
2. Fix only the blockers needed for integration. At the initial review:
   - GUI imports reference common modules as local files.
   - Controllers expect YAML files beside themselves, but files are in
     `dmi_robot_config/`.
   - The slave calls `move` and `move_and_click`; the robot implements
     `live_movement` and `click`. Confirm absolute XY semantics and millisecond
     press duration before adapting these calls.
   - Picture capture has no initialized camera; do not assume it is operational.
3. Confirm the intended shared message protocol. Keep the older standalone
   protocol in `DmiRobot.py` out of the integration path.
4. Check command payloads, bounds and failure responses without moving hardware.
   Use a fake robot and fake transport for these checks.
5. Make the smallest import/config corrections needed to start both components.
   Add missing dependency/setup guidance without installing Pi packages on a PC.

Complete when imports/configuration resolve and simulated commands call the
correct robot operations with the correct units. Report remaining hardware
limitations. Do not silently refactor the accepted detector.

## Phase 2 — Implement the robot-camera processing path

1. Identify the actual camera: USB webcam, Picamera2 camera or an existing stream.
   Establish its intended host and interface when known. Keep resolution,
   orientation and connection configurable; confirm actual values during the
   later hardware trial. Ask only when a missing fact affects adapter design.
2. Choose one intended processing host. If the camera and detector are
   on different hosts, use one simple frame transport with bounded buffering.
   Do not assume the current integer-index webcam adapter accepts stream URLs.
3. Reuse the existing camera adapter when compatible. Otherwise implement one
   thin adapter supplying BGR `uint8` frames, increasing capture indices and
   local monotonic receipt times to the existing processing path.
4. Give the camera one owner. Share frames if still images are also needed;
   do not let the robot and detector independently open the same device.
5. At home, replay existing videos through the same live processing interface,
   with local receipt timestamps and a bounded latest-frame buffer. Keep the
   original video time separately for evaluation. Run observation only and show
   or save annotations for every processed frame and the compact detection log.
6. Process the most recent frame when the detector cannot keep up with capture.
   Report capture rate, processed rate, skipped frames and latency. Do not claim
   every camera frame is processed or that every possible screen is supported.
7. Check Driver ID and representative supported screens using existing recordings.
   Unknown screens remain explicitly unknown; report missing recognition.

Complete offline when replay through the live path produces correct annotations,
valid output and bounded buffering, and the intended camera adapter is ready.
Document untested device behavior and proceed to Phase 3. Confirm actual camera
input and image quality after all six implementation phases.

## Phase 3 — Calibrate pixels to robot millimeters

Use `dmi_robot_master/DmiPositions.json` as the reference for
`DMI_SENSE_TOUCHSCREEN.screens.DRIVER_ID_WINDOW.buttons`.
Only this model currently has mapped keys. Verify the coordinates against the
actual installed DMI during the final hardware trial; a JSON entry is a reference,
not proof of physical accuracy.

1. At home, implement and test fitting with synthetic known correspondences and
   stable Driver ID recordings. Treat recorded-coordinate fits as simulation.
   On hardware later, fix the camera, DMI and robot mounting, home the robot and
   establish which robot origin and axis directions the stored coordinates use.
2. Observe a stable, visible Driver ID keypad without robot movement or occlusion.
   Match detector `digit_0` through `digit_9` to database `KEY_0` through `KEY_9`.
   Match by identity, never dictionary order or screen position alone.
3. Use centers in the original input image coordinate system. Do not mix them
   with resized preview, cropped or rectified image coordinates.
4. Collect several consistent observations of each matched center. Reject
   missing, ambiguous or unstable matches; summarize accepted centers robustly.
5. Fit a planar pixel-to-robot-XY homography using OpenCV and the matched points.
   This accounts for perspective; a single pixels-per-mm ratio generally does
   not. Use at least four non-collinear matches and preferably all ten keys.
   Reject degenerate fits and insufficient inliers; do not select a complicated
   calibration model unless measured error justifies it.
6. Validate with held-out keys or leave-one-out fits. Report per-key, mean and
   maximum XY error in mm. Training residual alone is not independent validation.
   Set an acceptance tolerance from physical button size and robot positioning
   accuracy before enabling movement; do not invent a universal tolerance.
7. Save a small calibration file containing the transform, model, frame size,
   camera identity/settings, reference coordinate-file hash, matched points,
   origin/axis convention, validation errors and calibration identifier.
8. Apply the transform to a detected center as homogeneous coordinates, divide
   by the third component and reject nonfinite or unstable results.

Calibration maps a point on the calibrated screen plane to absolute robot XY
millimeters. It does not determine Z depth, contact force or press duration.
Keypad-only calibration does not validate distant controls or the other display.
Export their detected pixels, but mark mm coordinates unusable outside the
validated area. Extend validation with measured points before enabling them.
Separate planes need separate calibration.

Invalidate calibration after camera/DMI/robot mount movement, changes to image
size/crop/orientation, reference coordinates or robot origin. Resolution matching
alone cannot detect camera movement. Recheck known key correspondences before
each physical test and whenever a relevant change is suspected.

Complete offline when fitting, conversion, held-out error reporting and invalid
calibration rejection pass focused tests. Review recorded examples, then proceed.
Physical accuracy and the final tolerance must be verified on the installed robot
before any physical movement based on vision.

## Phase 4 — Export a simple current target file

Keep the existing rich vision logs. Add a small projection for robot consumers;
do not replace the detector contract or make the robot parse annotation images.
Use `LatestState` or an equally small current-state interface, not a historical
JSONL record that may no longer describe the visible screen.

Prefer an atomically replaced `targets.json` containing only the latest snapshot.
Optional JSONL history may use the same full snapshot format; keep it separate
from the file used to select current targets. Minimal proposed format:

```json
{
  "session_id": "camera-session-id",
  "frame_index": 42,
  "observed_at": "2026-10-07T13:00:00.000Z",
  "screen": "Driver ID",
  "calibration_id": "calibration-id",
  "targets": [
    {
      "label": "KEY_1",
      "kind": "button",
      "display": "right",
      "pixel": [640, 360],
      "mm": [100.0, 300.0],
      "usable": true
    }
  ]
}
```

The example pixel position is illustrative, not a known detection. Specify:

- `pixel`: original-image `[x, y]`; `mm`: absolute robot `[x, y]`, or `null` when
  calibration is absent, invalid or outside its validated area.
- `observed_at`: source-frame receipt time expressed in UTC, not export time.
  Enforce receipt age with a monotonic clock in the live process. Across hosts,
  account for clock synchronization and transport delay; a file's modification
  time is not evidence of fresh camera input.
- `label`: stable, unique within the snapshot. Map keypad digits to `KEY_n`;
  qualify other detector labels by display/kind where needed to avoid ambiguity.
- Export detected buttons, fields and boxes with their centers and labels.
  Keep optional field values out of the first schema unless needed for the test.
- `usable` means fresh enough and within validated calibration/geometry limits.
  It does not mean every exported field or box is an approved pressing target.
  Do not invent confidence scores or observation ages the detector does not supply.
- Remove vanished targets on every snapshot. On loss/failure/stop publish an empty
  target set where possible; consumer expiry must also handle abrupt process death.
- Never act on a retained center unless its recent supporting evidence is checked.
  A fresh frame alone does not establish that every tracked element was observed.

Complete when the file follows live screen changes, is small and readable, and
consumers reject missing, stale, duplicate and uncalibrated targets.
At home, use live-path replay and simulation calibration. Simulation coordinates
may be displayed and sent to a fake robot only; keep that distinction explicit.

## Phase 5 — Test one button by label

Provide one small interactive terminal program. Start it once; run acquisition
and detection in the background while the terminal accepts one label at a time,
for example `KEY_1`. The user does not need to start a second command or enter
coordinates. Resolve the label from the latest in-memory snapshot when entered;
continue exporting `targets.json` for inspection and future external consumers.

Select an explicit session mode: dry run, simulated press, move-only or physical
press. Default to dry run and display the active mode clearly. In press mode,
entering a valid label requests exactly one press after validation. Do not trigger
movement merely because an output file was written. Reject additional actions
while one is outstanding; do not build a queue of labels.

Support `quit`, end-of-input and Ctrl-C with coordinated shutdown. Keep the prompt
readable by routing frequent progress logs away from terminal input. Prefer the
smallest concurrency arrangement that keeps detection independent of blocking
input and robot communication. If an annotated GUI preview requires the main
thread, respect that requirement rather than moving it blindly into a worker.

At home, implement all modes and test their command payloads using a fake robot
and transport. Simulate DONE, ERROR, timeout and disconnect; do not open GPIO or
send packets to the actual robot. The following physical sequence is deferred
until all six implementation phases are finished.

1. Read a fresh live target and require the expected screen, unique label,
   validated calibration and stable visible geometry.
2. Dry run prints the selected pixel center, converted mm center and rejection
   reason if unusable. It sends no motor command.
3. Before hardware tests, verify homing, actual XY travel limits, Z retraction,
   contact sensing and the available physical stop mechanism. Use configured
   nonnegative XY bounds and a conservative existing press routine.
4. Test move-only with the pressing tool retracted. Inspect alignment before
   authorizing a first physical press. Recheck the current target immediately
   before sending a command; never queue old targets.
5. Send one action through the existing master/slave protocol. Require DONE;
   ERROR, timeout or disconnect ends the test and prevents further commands.
   Do not automatically retry a timed-out press: it may already have executed.
6. After pressing, observe a newer frame and verify the expected UI change or
   field update. DONE establishes command completion, not successful UI input.
   If recognition cannot establish the result, report it as unconfirmed.
7. Record the label, source frame, calibration identifier, commanded mm position,
   response and observed outcome in one small test log.

The GUI stop flag currently stops future script iterations; it is not an immediate
hardware stop during a blocking movement. Do not label it an emergency stop.
Motor/network waits must not block live detection. Permit at most one outstanding
physical action and require explicit operator control for this first test.

Complete offline when a label can be selected from replay, converted, previewed
and dispatched to the fake robot with correct units and failure handling.
Later validate alignment and pressing with physical-camera evidence. Start with
one known keypad button; do not automatically run multi-button XML sequences.

## Phase 6 — Verify the complete integration offline

Run the full path with recordings, simulation calibration and a fake robot.
Repeat a few individually selected keypad tests and one supported screen change.
Verify annotations, mm conversion, label selection and command results. Test
post-action verification with controlled observations; prerecorded UI changes
are not evidence that a robot action caused them.
Exercise loss of camera, stale file, wrong screen, invalid calibration, target
outside travel limits, robot ERROR and timeout without uncontrolled movement.
Measure offline processing delay and report the environment and simulation limits.

Leave a small documented interface that a future application/backend can call:
get current targets, preview a label and request one validated action. Keep backend
transport, autonomous navigation and broader DMI models outside this first scope.

Complete when all six phases are implemented, offline checks pass and documented
startup commands are ready for the later physical trial.

## Physical validation — After all six phases

1. Confirm the installed camera, network settings and hardware dependencies.
2. Start observation only; inspect annotations on the real camera and supported
   screens. Measure capture/processing rate, buffering and latency.
3. Verify reference key positions, mounting, homing and robot coordinate axes.
   Fit a new hardware calibration and validate its held-out error.
4. Inspect the live target output. Run a dry run, then move-only alignment, then
   one operator-controlled press as described in Phase 5.
5. Confirm the expected UI response using newer camera observations. Repeat a few
   selected keys and a screen transition, then check recovery and latency.

Report hardware failures separately and fix them incrementally. Final acceptance
requires this trial; completion of offline implementation does not establish
physical calibration accuracy, camera compatibility or successful pressing.

## Validation and phase handoff

- Run relevant existing vision tests after import or detector-path changes.
- Add focused tests for calibration identity matching/held-out error, target
  expiry/removal and fake-transport command success/failure. No hardware in tests.
- Preserve recorded-video regression behavior. Do not alter detection thresholds
  or temporal behavior merely to make calibration examples pass.
- Report what changed, offline verification evidence and deferred hardware checks
  after each phase. Request implementation review before the next phase; do not
  require physical-camera review while development is taking place at home.
- Do not declare integration working from mocks, saved videos or valid JSON alone.
  Final acceptance requires the real camera and a reviewed physical button test.

## Integration state and model handoff

Maintain one short root `STATE.md` for robot/CV integration. It is separate from
`dmi_computer_vision/docs/STATE.md`, which records the accepted detector work.
Update the integration file after each phase and at meaningful checkpoints during
unfinished work so another model can resume without repeating completed steps.

Include only useful handoff information:

- Current phase and status: not started, in progress or completed offline.
- A short summary of the implementation and the important files changed.
- Tests/checks actually run, their results and useful reproduction commands.
- Remaining issues, deferred physical checks and the next concrete step.
- User decisions that affect implementation, plus approval and commit/push status.

Keep a concise entry for each completed phase so progress remains visible.
Mark a phase **Completed offline — awaiting approval** only when its implementation
and required offline checks are finished. Record user acceptance separately when
it arrives. Do not mark unfinished work completed, and do not imply that an offline
phase has been validated on the robot. If work stops mid-phase, record what is done
and what remains before handing off. This file is a technical handoff, not a diary
of every tool call or a duplicate of detailed project specifications.

## Phase report, approval, commit and push

After completing each phase:

1. Run the relevant checks and review the final changes.
2. Update root `STATE.md` with the completed offline phase and pending approval.
3. Give the user a short report explaining what was implemented, why any base
   robot code changed, what passed verification and what remains untested.
4. Ask the user to review and approve that phase for commit and push. Wait for
   explicit approval; do not commit, push or start the next phase beforehand.
5. After approval, record acceptance in `STATE.md`, review Git status and stage
   only that phase's changes and handoff update. Preserve unrelated user changes;
   do not accidentally include recordings, generated outputs or local settings.
6. Commit with a clear phase-specific message and push to the intended remote
   and branch. Verify the destination; do not force-push or rewrite history.
   Ask only if the destination or scope is ambiguous.
7. Report the commit identifier and push result. If either operation fails,
   report it accurately and retain a useful handoff; never claim it succeeded.

If the user requests corrections, make them, rerun affected checks, update
`STATE.md` and present the revised report before committing. One phase approval
authorizes its commit and push only; it is not blanket approval for later phases.
Do not create extra commits merely to record the final commit identifier in the
same handoff file. Report it in chat and include it at the next natural update.
