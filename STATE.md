# Robot/CV integration handoff

## Current status

**Phase 3A: Completed offline — accepted.** Implemented on 2026-10-08; user
approved its commit and push on 2026-10-09.
Accepted/pushed to origin/main: Phase 1 `e95e274`, Phase 2 `bd99ef6`, Phase 3
`5f2abe0`. Phase 3A commit/push are being performed to verified origin/main
(`https://github.com/H4miiiid/DMI_R-D_ALTEN.git`); Phases 4–6 not started. No hardware
access, robot packets, GPIO or backend service. User-authored Phase 3A AGENTS.md
instructions are included unchanged with the approved phase.

User facts: two webcams probably on Pi (type/index/cabling/network unconfirmed);
PC detection with one selected OpenCV-compatible camera/latest-JPEG bridge, local
camera option. Picamera2 still needs an adapter if required. One large monitor
contains both display regions; monitor-wide homography remains unvalidated beyond
keypad. Robot origin stated bottom-right, +X left, +Y up, travel beyond monitor.
Actual image origin/axes/reference coordinates remain unchecked: KEY_1 X=100 vs
KEY_3 X=200 conflicts with left-positive X in unmirrored recordings. Do not change
reference/simulation calibration based on this unmeasured convention. User will
check deployed PC/Pi files and physical coordinates later.

## Accepted phases

- **1:** fixed imports/config paths and slave method mapping; bounded integer
  absolute-mm/ms command adapter, ERROR/timeout/socket failure handling/cleanup.
  12 fake-only checks; motor routines/pins/wire format unchanged.
- **2:** latest-frame replay/local camera/remote JPEG adapters and one camera-owning
  bridge; observation CLI with per-detection annotation, compact log/receipt/source
  time metadata. Minimal live EOF handling, vision mock namespace repairs.
  27 integration/129 vision tests passed. Recognition limits remain explicit.
- **3:** robust named Driver ID observations, homography/leave-one-key-out errors,
  guarded original-image pixel→absolute-mm conversion, metadata/hash/context/hull
  validation. Simulation/unverified hardware rejected. 41 integration/129 vision
  tests passed. Recorded mean/max errors: 0.658/1.031 mm and 0.248/0.363 mm against
  stored JSON, not physical accuracy. Review/calibration evidence unchanged under
  dmi_computer_vision/outputs/robot_integration/phase3/.

## Phase 3A implementation

- processing_policy.py: thumbnail image-change check against last detected image,
  rate cap, periodic refresh, confirmation burst, reset/session handling and a
  post-action request requiring a newer receipt. No detection/temporal thresholds
  changed. Default regular processing stays available for calibration/regression.
- Optional live.py policy/callbacks, annotation disable, consumed/policy-skipped
  counters and separate detection/annotation time; debug receipt/source timestamps.
  LatestState changes only on actual detection. Skips do not become evidence.
- publication.py: in-memory pixel projection and callback policy. Initial/full
  meaningful snapshots, default 4 px per-coordinate tolerance against published
  baseline, semantic/presence/visibility/usability/context/session bypass, heartbeat
  and source-age expiry/failure/stop invalidation. Internal pixels remain current.
  No targets.json/backend implemented; Phase 4 will provide atomic current-file
  sink/conversion. Prototype targets deliberately usable=false, field values optional.
- Independent status worker handles blocked source/detection expiry. Heartbeats
  carry actual receipt/detection age/revision, not all coordinates. Pi age + RTT
  included conservatively. Aggregate frame freshness is not tracked-item evidence.
- ValidatedCalibration caches copied, validated context and latest per-label mm
  results. Context/reference fingerprint changes trigger full validation; every
  action must still use full revalidation and fresh keypad checks. Calibration
  fitting rules/artifacts unchanged.
- observe.py: selective mode/publication options, optional annotations/debug,
  age-marked reused main-thread preview, review event sink and metrics. Camera.py
  exposes a thin recording-open hook for bounded controlled replay and optional
  remote request cap; frame_bridge.py has optional JPEG encoding cap. Regular
  transport remains uncapped unless configured; selective PC defaults to 10 requests/s.
- benchmark_policy.py repeats original decoded recording pixels through bounded
  replay (one pending slot) with controlled Driver ID→Main→loss→Driver ID changes.
  No re-encoding detector inputs, no actions implied by prerecorded changes.

## Checks and measured evidence

Environment: development Mac, configured Python 3.13.3 pyenv, existing
numpy/OpenCV/PyYAML/Tesseract; no new dependency/Pi package install.

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
python3 -m compileall -q dmi_robot_master/integration tests dmi_computer_vision/src/dmi/pipeline/live.py
git diff --check
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --processing selective --debug \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase3A/selective_NEW
python3 -m dmi_robot_master.integration.benchmark_policy \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase3A/comparison_NEW
```

- 57 integration checks and 129 vision checks pass; compile/diff checks pass.
  Focused checks cover 3/4 px suppression, >4/cumulative drift, same-title image/
  button/value changes, removals/context/visibility/usability, real receipt age,
  stale/blocked-source expiry/failure, fresh post-action/session reset, cached
  conversion versus per-action rejection and fake transport encoding/request caps.
- Final controlled comparison: 169 regular / 86 selective detections (49% fewer),
  detection time 23.60 / 16.99 s (28% less), annotation time 0.77 / 0 s. Each mode
  emitted 12 meaningful snapshots (~47.3 KB); selective status ~14.4 KB. A naive
  per-detection projection would emit 86 snapshots/~356.8 KB, a counterfactual
  baseline. Existing change-based publication already suppresses static data;
  no extra publication saving is claimed against it or CompactWriter.
- Controlled source-time max recognition delay 0.93 / 0.77 s; including measured
  receipt-to-result delay yields conservative maxima 1.17 / 1.02 s. Loss response
  0.07 / 0.13 source seconds. Both modes had zero temporal resets in this trial.
  Contract/compact reconstruction passed for every actual detection.
- Actual Level-to-Main replay: regular 199 detections, first Main at source 19.188 s;
  initial 4 FPS profile 118 calls/first Main 23.074 s (3.89 s later). Selected
  5 FPS/0.4 s refresh/3 s burst profile: 156 calls/first Main 19.051 s, within 0.14 s
  of regular, one capture-gap reset. Do not hide missed brief states/reset effects.
- Initial lossy MP4 frozen fixture lost Driver ID recognition; retained as failed
  fixture evidence, replaced with decoded BGR frames without detector changes.
  Early exploratory runs overlapped other checks; final pair ran sequentially.
- Review evidence (ignored): dmi_computer_vision/outputs/robot_integration/phase3A/
  final_comparison/comparison.json, controlled_replay.json, regular/selective logs,
  publication_review.jsonl, regular annotated.mp4 and final image; actual replay
  directories baseline_transition/selective_transition/selective_transition_fast.
  Test logs /private/tmp/dmi_phase3A_tests.log and _vision_tests.log. Do not stage
  generated outputs/recordings; preserve Phase 3 evidence and user AGENTS.md edits.

## Timing limits and deferred work

Selective defaults: cap 5 detections/s; 0.4 s refresh; 3 s confirmation burst;
thumbnail 160×120, >12 intensity on >=0.2% pixels; 4 px publication threshold;
0.5 s heartbeat; evidence expires after 1.5 s with <=0.1 s worker tick plus OS/
callback scheduling. Resets/actions can bypass cap. Source delivery and expensive
native processing can exceed deadlines; no real-time guarantee/reconnect. Brief
changes can be missed, and confirmation still counts actual processed frames.
Full review annotations/debug remain optional; regular path preserves accepted
calibration behavior. Recheck settings/latency/recognition on installed hardware.

After all implementation phases: measure camera/mount/robot origin/reference keys
and button/tool/robot accuracy, fit NEW hardware calibration, validate wider monitor
points before enabling beyond keypad. Cached publication must never authorize an
old target. Legacy contact/Z retraction accounting, lower bounds, blocking homing,
nonzero-Z scaling, partial GPIO startup and late UDP reply correlation remain
focused hardware issues; GUI stop is not an emergency stop.

Next: complete the approved Phase 3A commit/push to verified origin/main and
report its ID/result in chat; record them at the next natural handoff update.
Phase 4 is atomic current target-file and evidence/status integration. No Phase 4
implementation started.
