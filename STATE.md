# Robot/CV integration handoff

## Current status

**Phase 3: Completed offline — accepted.** User approved Phase 3 on 2026-10-08,
authorizing its commit and push.
Phase 1 accepted/pushed as `e95e274`; Phase 2 accepted/pushed as `bd99ef6` to
`origin/main` (`https://github.com/H4miiiid/DMI_R-D_ALTEN.git`). Phase 3 commit/push are being
performed to verified `origin/main`; Phase 4 not started. No hardware validation or robot commands.

User reports two webcams, probably on Raspberry Pi; actual type/cabling and which
sees the DMI remain unknown. Intended processing is on PC via one selected Pi
OpenCV-compatible camera/latest-JPEG bridge; local-PC camera is configurable.
Confirm backend/index/settings/network later; Picamera2 still needs an adapter if
required by the installed devices. Compare deployed PC/Pi files during the trial.

User clarification: both display regions belong to one large monitor. A single
monitor-wide homography may be suitable if the surface is planar, but remains
unvalidated beyond the keypad. Robot travel extends beyond the monitor. User
states origin at bottom right, +X leftward, +Y upward; actual origin location in
the image remains unmeasured. Stored KEY_1 X=100 and KEY_3 X=200 appear to conflict
with +X leftward in the current unmirrored recordings. User will check physical
coordinates/axis direction later. No coordinate, axis or homography changes were
requested during consultation; keep simulation reference convention unchanged.

## Phase 1 — Completed offline, accepted

- Fixed package imports/config paths and slave live_movement/click mapping.
  Added explicit bounds/payload validation and master command adapter: absolute
  integer XY mm, press duration ms. Monotonic timeout, immediate ERROR failure,
  UDP packet validation/error propagation and resource cleanup; wire/motors unchanged.
- 12 fake-only tests passed, including startup from another working directory and
  real method unit/math checks with motor calls replaced. Phase 1's pre-existing
  vision test namespace failures were corrected in Phase 2 tests only.

## Phase 2 — Completed offline, accepted

- camera.py: bounded paced replay, local camera wrapper, remote latest-JPEG source
  with capture/session identity and upstream age/RTT checks. frame_bridge.py owns
  one camera and one JPEG. observe.py saves each processed annotation and compact
  log plus receipt/source-time metadata using existing process_live/LatestState.
- Minimal live EOF handling; fixed mock paths in vision tests. Detector unchanged.
- 27 integration/129 vision tests passed. Driver ID, Level/Main and Train Number
  replay checks passed contracts, compact reconstruction and annotation counts;
  fake-HTTP JPEG replay recognized Driver ID. Unknowns/obstruction and misplaced
  Level controls remain detector limitations. Offline rates/commands in README.

## Phase 3 — Implementation and checks

- New integration/calibration.py: identity matching digit_n → KEY_n against
  DmiPositions.json, bounded complete/clear stable observations, robust median
  centers, OpenCV pixel-to-absolute-XY-mm planar homography and leave-one-key-out
  validation. At least five keys for independent validation (four training keys);
  collector requires all ten. Collinear/duplicate/outlier fits fail.
- Saves content-derived ID, provenance, model/plane, actual frame size, camera
  identity/settings/mount revision, robot origin/axes, reference SHA256, matched
  points, observation summary, keypad convex hull, inliers and independent errors.
- Load/conversion reject malformed/changed/unaccepted artifacts, inconsistent
  correspondences/errors/matrix/hull, changed image/settings/mount/reference/origin,
  nonfinite/singular/unstable division, other display/screen or outside-hull points.
  Simulation/unverified artifacts cannot pass hardware=True; fresh keypad recheck
  helper is provided. No physical calibration certification or motion added.
- New integration/calibrate.py CLI accepts only successful explicitly simulated
  Phase 2 replay output. Physical tolerance remains unset; example tolerances are
  simulation-only. Base robot, detector and reference JSON unchanged.
- Added tests/test_calibration.py; startup/API/limitations documented in integration/
  README.md. **41 integration tests passed** (14 new calibration tests) and **129
  vision tests passed**. Compile/whitespace checks passed. Tests include noisy
  held-out errors versus training residual, shuffled identities, invalid fits,
  expiry/context/reference changes, malformed files, rechecks and simulation gate.

Run from repository root in existing Python 3.13.3 pyenv environment (PyYAML,
numpy/OpenCV, Tesseract; no Pi packages or devices required):

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
python3 -m compileall -q dmi_robot_master/integration tests
git diff --check
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 3 --max-frames 12 --debug \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase3/driver12_NEW
python3 -m dmi_robot_master.integration.calibrate \
  --observation-dir dmi_computer_vision/outputs/robot_integration/phase3/driver12_NEW \
  --output dmi_computer_vision/outputs/robot_integration/phase3/driver12_NEW/calibration.simulation.json \
  --observations 5 --max-spread-px 3 --ransac-threshold-mm 5 \
  --simulation-tolerance-mm 5
```

## Recorded simulation evidence

- Initial moving Driver ID samples failed the 3-pixel stability limit. No detector
  thresholds changed. Selected steadier recording sections for fresh live-path
  replay (source times retained; slower pacing preserves nearby source frames).
- driver_id_12.mp4 at 2.5 seconds: five stable observations/all ten keys;
  leave-one-out mean **0.658 mm**, max **1.031 mm**. Calibration ID starts 0e3a0185.
- driverID_to_level.mp4 at 13.5 seconds (visible Driver ID portion): five stable
  observations/all ten keys; mean **0.248 mm**, max **0.363 mm**. ID starts 54f510ce.
- Each example: 12 replay results passed contract/compact reconstruction, 12 video
  annotations decoded; all matched centers converted; hardware execution rejected
  simulation; final Driver ID annotations inspected. These errors measure fit to
  stored JSON positions, not physical accuracy. Replay observations are stabilized
  detector output, not independently confirmed fresh hardware measurements.
- Review files are inside the project: dmi_computer_vision/outputs/robot_integration/
  phase3/{driver12,driver_to_level}/ with calibration.simulation.json,
  calibration_verification.json, annotated.mp4, last_annotated.png and live logs.
  Already ignored by Git; do not stage recordings/generated outputs.
- Logs: /private/tmp/dmi_phase3_integration_tests.log and _vision_tests.log.

## Deferred physical checks and next step

After all six phases: confirm installed camera/mounts, homing, robot origin/axes,
reference key positions and physical tolerance from button/tool size plus robot
accuracy. Fit a NEW live hardware calibration; certify it only after physical
review. Recheck fresh stable/direct key evidence before every action. Settings or
resolution matching alone cannot detect movement; update mount/origin revisions.
Keypad hull does not validate distant controls/other display. No Z/force/duration
inference or integer-protocol rounding in calibration. Current validators refit
small point sets to check stored errors; future target code should avoid needless
repeated validation work without bypassing context changes.

Inherited hardware issues: legacy camera slots None; click success does not prove
contact; Z contact accounting appears to overcount retraction. Lower bounds,
blocking homing/sensor waits, nonzero-Z scaling, partial GPIO startup cleanup and
late UDP response correlation need focused review. GUI stop is not emergency stop.
Remote target age must include Pi age/RTT; tracked item freshness remains limited.

Next: complete approved Phase 3 commit/push to verified `origin/main`, staging
only its helpers/tests/README/root STATE.md and preserving unrelated/ignored files.
Report commit ID/push result in chat; record at the next natural handoff update.
Phase 4 is current target projection. Physical axis/reference checks are deferred.
