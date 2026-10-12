# Robot/CV integration handoff

## Current status

**Phase 5: Completed offline — accepted.** User approved the revised phase,
including the timestamp correction, for commit and push on 2026-10-12.
Accepted/pushed: Phase 1 e95e274, Phase 2 bd99ef6, Phase 3 5f2abe0, Phase 3A 160ea04,
Phase 4 ea6f5d1, all on origin/main. Phase 5 commit/push are being performed to
verified origin/main (https://github.com/H4miiiid/DMI_R-D_ALTEN.git); Phase 6 not started. No physical camera/robot/UDP/GPIO access or backend implementation.

User facts: two webcams probably on Pi; type/index/network unconfirmed. PC detector,
one selected camera/latest-JPEG bridge, local-camera option; Picamera2 adapter still
needed if installed hardware requires it. One monitor holds both regions; wider
calibration unvalidated. Robot origin stated bottom-right, +X left, +Y up, travel
beyond monitor. Stored KEY_1 X=100 vs KEY_3 X=200 conflicts with left-positive X in
unmirrored recordings; keep simulation convention until user checks physical
axes/positions and deployed PC/Pi files. No guessed deployment values.

## Accepted phases

- **1:** fixed imports/config/slave mapping, absolute integer XY-mm/ms adapter and
  bounds/failure/cleanup. 12 fake checks; base motors/pins/protocol unchanged.
- **2:** bounded replay/local/remote camera paths, single-owner bridge/observation
  CLI, annotations/compact/receipt metadata, minimal live EOF and vision test import
  corrections. 27 integration/129 vision tests.
- **3:** robust named keys/homography/held-out validation/context/hash/hull limits,
  simulation rejection. 41 integration/129 vision tests; recorded max fit errors
  1.031/0.363 mm against stored JSON, not physical accuracy.
- **3A:** optional scheduling/change/refresh/burst, separate 4 px publication and
  evidence/heartbeat expiry, cache/annotation/transport caps. 57 integration/129
  vision tests. Controlled calls 169→86 and detection time 23.60→16.99 s; timing
  tradeoffs measured, selected 5 FPS/.4 s/3 s burst, thresholds unchanged.
- **4:** atomic current target/status files, supporting raw evidence, exact current
  getter and conservative file readers. 77 integration/129 vision tests after
  review corrections: clock sampled under publisher lock; actual source kind/
  index/requested-size/endpoint bound to calibration and adapter. Recorded export
  contracts passed; stop clears targets; geometry jitter remained explicit.

## Phase 5 implementation

- New actions.py: preview/request one known right Driver ID keypad label; full
  calibration/source/context/reference/hull/raw-key recheck, bounds, explicit nearest
  integer-mm half-up rounding, pre-send re-resolution. One action worker; busy labels
  rejected, no queue. ERROR/timeout/disconnect/send/response failure latch prevents
  further commands; no retry. Closure during preview cannot start a late worker.
- New action_transport.py: fake robot/transport through existing master/slave and
  RobotCommands; response trace and bounded delay/failure simulation. No wire change.
- New press_label.py: one terminal program, default dry-run/fake banner, modes
  dry-run/simulated-press/move-only/physical-press. Detection/optional preview on main
  thread; daemon blocking-input thread and one action worker. Logs separated from
  prompt; EOF/quit/Ctrl-C coordinated stop/cleanup. No XML sequences/backend.
- Direct current evidence now available for actions: all raw matched keys, receipt/
  upstream age, same-pass direct field value. Adds no target-file values/confidence.
  Optional stop_event supports graceful live-session cancellation. Existing regular
  detector output/thresholds and base robot movement/timing untouched.
- DONE triggers policy refresh and newer-than-completion source observation check,
  conservatively subtracting upstream Pi age/RTT. Known direct/confirmed field value
  implies appended digit; requires expected value in raw and confirmed newer data.
  Replay/fake match explicitly simulation, unknown/mismatch/shutdown unconfirmed.
- Hardware execution requires live source, full verified hardware calibration,
  actual source check, explicit bounds and readiness/alignment facts. No checks
  are guessed or performed by flags. Contact/Z defect review needed before physical
  press. Fake modes exercise payloads without asserting hardware validation.

## Verification actually run

Development Mac, configured Python 3.13.3 pyenv + existing numpy/OpenCV/PyYAML/
Tesseract; no dependencies/Pi packages installed.

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
python3 -m compileall -q dmi_robot_master/integration tests dmi_computer_vision/src/dmi/pipeline
git diff --check
python3 -m dmi_robot_master.integration.press_label \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 1.5 \
  --calibration dmi_computer_vision/outputs/robot_integration/phase3/driver12/calibration.simulation.json \
  --calibration-context dmi_computer_vision/outputs/robot_integration/phase4/driver12_context.simulation.json \
  --evidence-tolerance-px 3 --max-x-mm 380 --max-y-mm 470 \
  --mode simulated-press --transport fake --verification-timeout 2 --debug \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase5/terminal_NEW
```

- **97 integration tests pass**, **129 vision tests pass**; compile/whitespace pass.
  20 new Phase 5 cases exercise modes/payload units, hull/bounds/rounding, stale/
  wrong/missing/duplicate/context-changed targets, fresh pre-send recheck, one busy
  action, ERROR/timeout/disconnect latch, current post-action evidence, shutdown race,
  logging, EOF/quit/Ctrl-C, detector continuity during waits and main-thread preview.
- Valid-hardware-policy fixtures are synthetic assertions with fake transport;
  no actual physical calibration or hardware call. Simulation-to-hardware rejection
  and missing readiness before UDP opening tested.
- Actual terminal replay: one KEY_5 request sent to fake robot at [150,250] mm,
  200 ms; DONE, newer observation, UI **unconfirmed** (recorded field stayed 12).
  119 actual processed replay detections passed output/compact contract checks.
- Separate default dry-run terminal: KEY_5 rejected for current raw geometry;
  NOT_SENT. 129 replay detections valid. Did not relax tolerance or replay old
  centers. Both sessions quit cleanly and final targets=[]; progress outside prompt.
- Controlled synthetic terminal: fake command changed mock value 12→125, observed
  in a newer frame and labelled simulation; another input while busy rejected.
  Camera/detection advanced during delayed response, one action log record.
- Evidence (ignored) under vision outputs/robot_integration/phase5/: replay_press/
  and replay_dry/ have source/debug/compact/status/targets and verification.json;
  sibling *_progress.log and *_button_tests.jsonl. Preserve earlier calibration/
  review artifacts. Test logs /private/tmp/dmi_phase5_tests.log and _vision_tests.log.

## Phase 5 timestamp review correction — 2026-10-12

User identified dispatch log retaining the earlier preview source_observed_at when
validation advanced to a newer frame/coordinates. A deterministic fake-transport
regression advanced frame 0→1 and its timestamp/pixel during dispatch validation;
it failed before the fix. Dispatch now updates source timestamp together with
source_frame/pixel/mm from the final validated observation. Regression and all
97 integration tests pass; compile/whitespace checks pass. Test log:
/private/tmp/dmi_phase5_timestamp_review_tests.log. No hardware, commit/push or
Phase 6 work. User accepted this correction with Phase 5 approval.

## Remaining limitations and next step

All examples are simulation; no real pressing or camera compatibility demonstrated.
Actual bounds/axis/reference/offset/camera/mount/tolerance/homing/retraction/contact/
physical stop and move-only alignment must be verified after all six phases plus
3A. Existing contact/Z accounting, lower bounds, blocking homing/nonzero-Z scaling,
partial GPIO startup and late UDP reply correlation need focused hardware review.
Software quit cannot stop an issued physical move/press; not an emergency stop.
Blocked stdin can remain as a device-free daemon until process exit; no late action.
Native blocked device/wait cleanup may require process exit and unconfirmed outcome.
Recognition/value confirmation delay and raw geometry jitter remain; unknown baseline
or missing direct field evidence cannot establish successful UI input. Integer-mm
rounding and physical button/tool accuracy need assessment on installed hardware.

Next: complete approved Phase 5 commit/push to verified origin/main, excluding
ignored data/outputs. Report commit ID/result in chat; record at the next natural
handoff update. Phase 6 is full offline integration verification; not started.
