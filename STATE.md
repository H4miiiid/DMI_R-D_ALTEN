# Robot/CV integration handoff

## Current status

**Phase 4: Completed offline — accepted.** User approved the revised phase,
including both review corrections, for commit and push on 2026-10-09.
Accepted/pushed to origin/main: Phase 1 e95e274, Phase 2 bd99ef6, Phase 3 5f2abe0,
Phase 3A 160ea04. Phase 4 commit/push are being performed to verified origin/main
(https://github.com/H4miiiid/DMI_R-D_ALTEN.git); Phases 5–6 not started.
No hardware access, robot packets, GPIO or backend service.

User facts: two webcams probably on Pi (type/index/network unconfirmed); PC detector
with one selected OpenCV-compatible camera/latest-JPEG bridge, local camera option.
Picamera2 needs an adapter if required. One large monitor contains both regions;
wide-plane calibration remains unvalidated beyond keypad. Robot origin stated
bottom-right, +X left, +Y up, travel beyond monitor. Actual origin/axes/reference
positions remain unchecked: stored KEY_1 X=100 vs KEY_3 X=200 conflicts with left-
positive X in unmirrored recordings. Preserve simulation convention; user will
check physical positions and deployed PC/Pi files later.

## Accepted phases

- **1:** imports/config paths/slave method mapping, explicit integer absolute-mm/ms
  command adapter, ERROR/timeout/socket failure handling and cleanup. 12 fake
  checks; motors/pins/wire format unchanged.
- **2:** bounded replay/local/remote JPEG camera paths, single-owner bridge,
  annotation/compact/receipt-time observation CLI; minimal live EOF support and
  vision mock namespace fixes. 27 integration/129 vision tests passed.
- **3:** named stable key observations, homography/held-out error/context/hash/hull
  validation and guarded conversion. 41 integration/129 vision tests passed.
  Recorded mean/max fit errors 0.658/1.031 and 0.248/0.363 mm against stored JSON,
  not physical accuracy. Evidence under outputs/robot_integration/phase3 unchanged.
- **3A:** optional rate/change/refresh/burst scheduling, separate publication and
  evidence/heartbeat expiry, 4 px threshold against published centers, cached
  calibration conversion, optional annotation/transport caps. Regular path and
  thresholds preserved. 57 integration/129 vision tests passed. Controlled
  comparison 169→86 detections, 23.60→16.99 s detection time; 12 meaningful snapshots
  in both modes. Actual 4 FPS profile added 3.89 s Main delay; selected 5 FPS/.4 s/
  3 s-burst profile stayed within .14 s of regular, with one capture-gap reset.

## Phase 4 implementation

- New integration/targets.py: current projection, cached calibration/context/file
  invalidation, mm inside right Driver ID keypad hull only, direct supporting
  evidence/keypad recheck, independent CurrentTargets getter, atomic targets/status
  sink, optional full snapshot history and fail-closed file readers/selection.
- Vision FrameProcessor optionally exposes current right raw state/visibility and
  observed key/field centers before temporal region stabilization. Same detector
  pass; returned detection contract, thresholds and temporal behavior unchanged.
  process_live optional evidence callback connects this to export only.
- observe.py --export-targets/--calibration/current-context/evidence-tolerance options
  wire existing Phase 3A publisher to targets.json + target_status.json, keeping
  rich logs. No action/terminal/backend implementation. Default earlier modes unchanged.
- Publisher carries source frame/capture index in events, keeps exact internal
  centers, reports labels still supporting published coordinates in heartbeats.
  Loss of support bypasses 4 px suppression and forces a new snapshot. Usability/
  visibility/context/loss remain semantic changes. Source timestamps are never
  export timestamps or renewed by skipped captures/heartbeat.
- Calibration cache exposes context/hull/recheck methods; valid identical points
  reuse conversions, invalid unchanged documents are not repeatedly refitted.
  Required future per-action full validation remains. No robot/reference changes.

## Verification actually run

Configured development Mac/Python 3.13.3 pyenv + existing numpy/OpenCV/PyYAML/
Tesseract. No new dependencies, camera hardware or actual network/robot service.

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
python3 -m compileall -q dmi_robot_master/integration tests dmi_computer_vision/src/dmi/pipeline
git diff --check
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 3 --max-frames 12 --debug \
  --export-targets --target-history \
  --calibration dmi_computer_vision/outputs/robot_integration/phase3/driver12/calibration.simulation.json \
  --calibration-context dmi_computer_vision/outputs/robot_integration/phase4/driver12_context.simulation.json \
  --evidence-tolerance-px 3 \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase4/driver12_NEW
```

- **77 integration tests pass** (20 new Phase 4 cases), **129 vision tests pass**;
  compile/whitespace checks pass. Covers atomic read/write/failure preservation,
  current versus published jitter, support-loss override, expiry/abrupt death,
  duplicate/missing/uncalibrated/session-revision/clock rejection, simulation gate,
  missing current evidence, invalid cache/context, and live stop/error cleanup.
- Evidence-enabled/disabled processors returned identical detections on three
  actual recorded frames. No duplicated detector or altered calibration threshold.
- Driver ID real replay: 12 detections; all contract/compact checks pass, 12 history
  snapshots including empty startup/stop. Up to ten simulation targets usable in
  one observation. Several frames failed 3 px raw keypad recheck despite smooth
  stabilized output; warning/invalidation retained, no tolerance loosened.
- Actual selective Level-to-Main replay: 136 detections (44 Level, 61 unknown,
  31 Main), 71 target history snapshots. Pixels exported; all mm null without
  calibration. Contract/compact checks pass; no semantic mismatches in either run.
- Actual receipt UTC retained. Both sessions ended with targets=[], status stopped;
  consumers reject selection after stop. Final empty files ~321/250 bytes. Live
  snapshots include right buttons/field and left boxes, stable qualified labels.
- Review files (already ignored) inside dmi_computer_vision/outputs/robot_integration/
  phase4/{driver12,level_main}/: targets_example.simulation.json (historical review,
  NOT a current actionable file), targets_history.jsonl, targets.json/status,
  verification.json, source/debug/compact logs and Driver ID annotations.
  Independent offline context fixture is phase4/driver12_context.simulation.json.
  Test logs /private/tmp/dmi_phase4_tests.log and _vision_tests.log.

## Phase 4 review corrections

User reported two defects; both reproduced offline before correction (7 failing
subcases in new tests): current() sampled time before a contended lock, and live
source kind/connection was not bound to calibration context. tick() shared the
clock-order defect. Both now sample the default production clock under lock;
current() also rejects already invalidated state. Explicit now remains test-only.

Target projection now checks source_kind for all supported sources, local
camera_index/requested_size and remote bridge_url against calibration/context.
observe target export also compares declared metadata with the actual source
adapter before acquisition and on each exported detection. Invalid unchanged-source checks are cached, and source
metadata changes invalidate that negative cache. Regression tests cover positive
bindings, crossed local/remote kinds, changed/missing indices/sizes/endpoints,
misdeclared actual adapters, and cache recovery. No hardware/geometry assumptions
were changed; physical serial identity still requires the installed trial.

Final review checks: 77 integration/129 vision tests passed; compile/diff checks
passed. New tests failed before the fixes and passed afterward. Review logs:
/private/tmp/dmi_phase4_review_reproduction.log, _review_tests.log,
_review_vision.log. Fresh recorded smoke output in phase4/review_fix_replay,
using the accepted simulation calibration/context; no hardware service opened.
User accepted these corrections with Phase 4 approval; Phase 5 not started.

## Consumer and deployment limits

targets.json writes only on meaningful change; status separately updates actual
freshness/revision and published-supported labels. Two atomic files are not one
transaction: revision mismatch must reject/read again. File mtime/history is never
freshness evidence. Consumer checks heartbeat and actual receipt UTC/combined age;
cross-host file readers require aligned clocks and transfer-delay accounting.
Local CurrentTargets uses monotonic age, returns latest exact pixels/mm or None
on expiry/stop/failure. It does not dispatch actions. Field values/icons are absent
from first target schema. Usable means geometry/freshness, not an approved press.

Only right Driver ID validated-hull points receive mm; other display/screens/
outside-hull pixels remain exported unusable. All recorded examples are simulation;
real-source export and hardware consumers reject simulation/unverified calibration.
Raw evidence is current detector support, not proof of correct borders/identity.
Future action must revalidate calibration/current target/bounds and fresh geometry,
not trust cached file coordinates. Physical axes, origin and reference values remain
unverified. Legacy contact/Z accounting, blocking homing, bounds/nonzero-Z scaling,
GPIO startup and late UDP reply correlation need focused physical review. GUI stop
is not emergency stop. All implementation phases precede hardware trial.

Next: complete the approved Phase 4 commit/push to verified origin/main, excluding
ignored recordings/outputs. Report commit ID/result in chat; record at the next
natural handoff update. Phase 5 is one-label interactive fake-transport actions.
No Phase 5 implementation started.
