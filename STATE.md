# Robot/CV integration handoff

## Current status

**Phase 2: Completed offline — accepted.** User approved the reviewed phase on
2026-10-08, authorizing its commit and push.
Phase 1 accepted and pushed as `e95e274` to `origin/main`
(`https://github.com/H4miiiid/DMI_R-D_ALTEN.git`). Phase 2 commit/push are being
performed to verified `origin/main`; Phase 3 not started. No physical camera/robot validation; no robot packets or GPIO accessed.

User reports two webcams, probably connected to the Raspberry Pi; camera type,
cabling and which camera sees the DMI remain unconfirmed. Intended processing
host is the PC, with one selected Pi OpenCV-compatible camera and a latest-JPEG
HTTP bridge. Local-PC USB camera is also configurable. Do not claim actual USB
compatibility: if installed cameras require Picamera2, add that source adapter
when confirmed. Actual index, resolution, orientation and addresses are deferred
settings. User will compare deployed PC/Pi files during the later robot trial.

## Phase 1 — Completed offline, accepted

- Fixed robot/GUI package imports and shared configuration paths; slave calls
  existing live_movement/click. Added command_validation.py and integration/
  commands.py for absolute integer XY mm, explicit bounds and press duration ms.
- Master uses monotonic timeout and fails on ERROR. UDP validates packet length,
  propagates receive errors and exposes cleanup; entry points release resources.
- 12 fake-only tests passed, including startup from another directory and real
  robot method math with motor calls replaced. Wire format/motor code unchanged.
- Phase 1 found pre-existing vision test mock namespace mismatches; Phase 2 fixes
  those test paths and restores all 129 vision checks without detector changes.

## Phase 2 — Implementation

- integration/camera.py: paced ReplayCamera with one pending frame, local receipt
  UTC/monotonic time, separate original video time, configurable orientation and
  EOF/stale/error cleanup; RobotCamera wraps existing LatestCamera.
- RemoteCamera requests only the latest bridge JPEG, bounds reply size/time,
  rejects duplicate/stale captures, source restart/session change and disconnect.
  Uses local PC receipt time plus separately recorded Pi capture age and request
  round-trip for conservative arrival-age validation. No host clock sync needed.
- integration/frame_bridge.py: one camera owner and one latest encoded JPEG;
  source capture session ID, index and monotonic age in HTTP metadata. No motors.
- integration/observe.py: observation-only module CLI using existing process_live,
  FrameProcessor and LatestState; full-size annotation for every processed frame
  in annotated.mp4, compact log, receipt/source-time sidecar and session metrics.
- Minimal vision change: clean EOF only when source.read() raises EOFError.
  Detector EOFError still fails. Test_live.py/test_video.py mocks now patch their
  actual imported namespace. Detection/temporal thresholds and behavior unchanged.
- Setup/commands and limits in integration/README.md. Local ignored vision
  docs/OUTPUT_SPEC.md updated for live EOF; do not force-add the ignored docs tree.

## Verification actually run

Environment: macOS, Python 3.13.3 (pyenv), PyYAML 6.0.3, existing numpy/OpenCV,
Tesseract at /opt/homebrew/bin/tesseract. Pi/backend/network compatibility untested.
Run from repository root with the configured Python environment:

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
python3 -m compileall -q dmi_robot_master/integration tests
git diff --check
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --replay-fps 8 --max-frames 12 --debug \
  --output-dir /private/tmp/dmi_robot_observation_NEW
```

- **27 integration tests passed** (12 Phase 1 + 15 Phase 2); **129 vision tests
  passed** after correcting existing mock paths. Compile and whitespace checks
  passed. Tests use fake camera/HTTP, covering buffering, final-frame EOF,
  expiry/loss, rotation, annotation count, repeated remote replies, RTT age,
  source session restart and cleanup. No actual network service/device opened.
- Actual recordings through the live path: full decoded Driver ID (38 processed,
  195 skipped); full decoded Level-to-Main (260 processed, 634 skipped); Train
  Running Number sample (16 processed). Every result passed output-contract and
  compact reconstruction (zero semantic mismatches); annotation counts matched.
- Source/session rates: Driver ID 24.76 capture / 4.04 processed FPS, mean/max
  receipt-to-result 243/510 ms; Level-to-Main 18.26/5.31 FPS, 201/1051 ms.
  These are offline session averages, some runs overlapped with other checks;
  not a deployment benchmark. Input container frame counts exceed decoded counts.
- Additional fake-HTTP quality-95 JPEG Driver ID replay: 16/16 recognized Driver
  ID, valid contract/compact reconstruction, 16 decoded annotated frames.
- Reviewed Driver ID, Main, Level, Train Number and obstructed final annotations.
  Full Driver ID has 21 recognized and 17 unknown observations; Level-to-Main has
  64 Level, 57 Main and 139 unknown observations. Inspected final unknown frames
  contain a hand; not all unknowns are manually classified. One Level annotation
  has visibly misplaced controls despite correct screen recognition. Preserve
  these detector limits; do not use valid logs as proof of pressing accuracy.
- Temporary evidence: /private/tmp/dmi_phase2_driver_smoke, _driver_full,
  _level_main, _train_number, _jpeg_driver_final (each prefixed dmi_phase2).
  Verification.json, video, sidecar/debug/compact logs and final images remain
  there. Test logs: /private/tmp/dmi_phase2_tests.log and _vision_tests.log.
  Generated evidence is not staged/committed.

## Deferred issues and next step

Hardware trial must confirm camera type/host/index, dependencies, network,
delivered image size/orientation/quality and actual latency. No reconnect or
native blocked-read recovery. JPEG changes pixels. Video playback is fixed 5 FPS
for inspection, not source time. Remote capture FPS is null; index span counters
are inferred. Later target consumers must include upstream Pi age and RTT in
addition to local receipt age; fresh frames do not guarantee fresh tracked items.

Inherited robot issues remain: camera slots None in legacy take_picture; click
success does not prove contact; contact-loop accounting appears to overcount Z
retraction. Lower bounds, blocking homing/sensor waits, nonzero-Z scaling,
partial GPIO constructor cleanup and late UDP reply correlation need review.
GUI scripts may ignore failed responses; stop flag is not an emergency stop.
Do not modify motors broadly; propose a focused contact/Z fix before pressing.

Next: complete the approved Phase 2 commit/push to verified `origin/main`, staging
only this phase and handoff; preserve unrelated/ignored data/docs/outputs. Report
commit ID and push result in chat; record them at the next natural handoff update.
Phase 3 is synthetic/recording simulation calibration. All six phases remain
offline first; new hardware calibration and physical acceptance are deferred.
