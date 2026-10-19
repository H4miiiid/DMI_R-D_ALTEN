# Robot/CV integration handoff

## Current status

**Monitor-support Step 4 — completed offline and approved (2026-10-19).**
User approved Step 4 and authorized its commit/push. Publication result is reported
in chat. Step 5 has not started; it requires a separate implementation request.

- Connected candidates validate independently. A complete orphan component/group
  requires measured sidebar or repeated control-border topology to establish its
  role; no partner, identity, image-half or camera-index assumptions. Basis changes
  (separated/connected/partial), existing enclosure jumps and 12%-dimension
  perspective-offset jumps reset incompatible geometry/content history. Missing
  left geometry cannot supply a train-workflow hint. Source/session/size/gap
  resets, numeric confirmation and original-pixel outputs remain intact.
- Current-image glyph-row evidence avoids train-title OCR on gauge arcs. No title
  recognition cache, scheduler, dependency, OCR-confidence or numeric matcher
  change. Direct evidence is still read each actual detection; timestamps,
  freshness, 4-pixel publication and calibration/motion gates are unchanged.
- Matched serial profiles: 48 connected frames, mean/P95 **1003/1043 → 238/267 ms**,
  **76.3% lower mean analysis cost**, OCR **11 → 1 call/frame**. Cold means
  1025 → 238 ms; steady 1001 → 238 ms. Separated 144-frame mean/P95 stays
  **187/267 ms**, OCR 188 calls in each trial. All 192 profile outputs/direct
  evidence match exactly. Geometry, analyzers, OCR, annotation, decode and JPEG
  costs are separated; nested OCR time is not counted twice.
- Fresh 436-frame connected replay exactly preserves corrected Step 3 results
  and direct evidence: 435 expected titles/control counts, 20–22 left boxes;
  direct values 181 correct/0 incorrect/28 unknown, stabilized 202/0/7 across
  209 Driver frames. Main04 frame 102 remains unknown. Accepted sample03 corner
  uncertainty and other connected-state coverage gaps remain unchanged.
- All 144 separated full-pipeline regressions and 11 frozen examples match;
  4330-frame raw-geometry audit and final rejected-frame recheck find no changes.
  The row gate rejects none of 1513 recognized train-title observations.
  Three controlled removal/recovery sequences (99 processed frames) clear loss
  immediately and retain supported roles; maximum partial-control center changes
  relative to full-image predictions: Main 3.16 px, connected Driver 1 px,
  separated Driver 0 px. Natural occlusion remains unverified. Earlier masks
  clipping healthy border pixels caused 17–32 px control changes; those diagnostic
  artifacts are retained and are not accepted alignment evidence.
- Regular paced simulation, identical options/images: measured producer about
  24 FPS despite a requested 30. Connected Main **0.97 → 4.35 processed FPS**,
  Driver **0.95 → 3.63**; mean receipt-to-result **1086/1129 → 254/298 ms**.
  Overwrites 229/229 → 196/203; gap resets 6/9 → 0/0; target updates 22/20 → 2/2.
  Existing 1.5-second expiry remains active; all runs clear targets on stop.
  Debug volume increases with more actual detections; compact/target volume falls.
  Preview/annotations disabled equally in these runs. No sensor/network timing,
  selective-mode transition-delay or 30-FPS detection claim.
- **172 vision/109 integration tests pass**, plus final focused 13-test checks;
  compile/whitespace, full/compact contracts and review-video decodes pass.
  Source capture artifacts and other production sources are hash-identical.
  The pre-existing root AGENTS.md plan edits are untouched. Only five production
  modules, two tests and this handoff are implementation changes; owning vision
  UI/output/evaluation/state docs and generated evidence remain locally ignored.
- Review: `dmi_computer_vision/outputs/monitor_support/step4_20261019_review02/REVIEW.md`,
  direct/stabilized videos and native PNGs. Controlled-removal review:
  `step4_20261019_stability_review03/`; scripts/snapshots/profiles/audits/hashes:
  `step4_20261019_run01/`. Paths are under the same monitor_support directory;
  `/private/tmp/dmi_step4_*` logs record checks. Final report has exact reproduction
  commands with new output directories. Earlier exploratory artifacts remain intact.
- Next: publish the approved Step 4 changes; await a separate Step 5 request.
  Step 5 still needs
  regular/selective transitions, partial-border/occlusion and same-title changes,
  confirmation delay, preview age/rate and per-arrangement state coverage. Connected
  Level/TRN/Train Data/validation/pages need representative footage; unsupported
  orphan train panes may remain unknown. Hardware capture settings, calibration,
  alignment and pressing remain unvalidated. No motor command was sent.

**Plan update — monitor-support Steps 4/5 (2026-10-16).** User requested speed
improvements alongside the remaining stability/end-to-end work. Root AGENTS.md
now adds profiling, evidence-based OCR retry reduction, bounded title reuse with
explicit invalidation, and before/after regular/selective timing and accuracy
checks. Existing latest-frame scheduling, raw evidence age, confirmation counts,
4-pixel publication policy and calibration/motion gates must remain intact.
This request updates the plan only; no Step 4/5 implementation or commit/push.

Read-only spot profiling on this Mac: first Main01/Driver03 frames took
1.179/1.143 s; each made 11 OCR calls consuming 0.965/0.899 s, mostly while checking
left-side train titles. These two cold observations identify a likely bottleneck,
not steady-state throughput or proof of a future speedup. Profile both arrangements
and preserve genuine train-title recognition before removing unnecessary retries.

Camera mapping is now user-confirmed: 0 = lower separated displays, 1 = upper
connected monitor, one selected source per session. This selects acquisition only;
do not hardcode geometry or screen identity. Connected coverage is Main/Driver ID
on the four supplied captures. Train Running Number shares the updated keypad
path but is unverified there; Level/Train Data/other accepted workflows also need
connected localization and control-alignment evidence. Step 5 must track these
gaps separately from preserved separated-display regressions. Hardware calibration
and pressing remain unvalidated. Documentation whitespace checks pass; no detector
tests rerun for this plan-only update. Next: implement Step 4 after its request.

**Monitor-support Step 3 — completed offline and approved (2026-10-16).**
User approved the corrected shared analysis and explicitly authorized commit/push.
Step 2 was pushed as 27b085e; user committed camera setup as 6b6aebd. This handoff
accompanies the approved Step 3 changes; the publication result is reported in chat.

- Title OCR still supplies screen identity, but its search path/position no longer
  selects layout. Measured blue extent, margin/grid borders and action structure
  choose the crop convention. Moving only the synthetic title by 27 or 41 pixels
  now preserves all 13 Driver ID controls with identical centers/corners; previously
  it produced 16 controls and moved digit_1 about 103 pixels. Main's 11 controls
  also remain identical. Missing active-grid evidence cannot invent legacy slots.
- Corrected the previous report: its claim that both Driver clips read 23 on all
  209 frames described stabilized output. Saved raw evidence had 186 correct and
  23 incorrect readings (Driver02: 5 wrong; Driver03: 18 wrong), not perfect direct
  recognition. Cold Driver03 frame 78 independently reproduced 73.
- New regular replay direct results: 181 correct, 0 incorrect,
  28 unknown / 209 (86.6% correct-reading coverage). Stabilized output:
  202 correct, 0 incorrect, 7 unknown / 209. This is measured
  saved-image performance, not general 100% accuracy. Stronger glyph correlation,
  runner-up separation, shape/alignment and whole-value rejection return null on
  uncertainty instead of dropping glyphs into partial values. Weak bright-field
  proposals require independent existing OCR agreement to preserve legible legacy
  values. No supplied answers, new model or recording-derived templates.
- Cold Driver03 frame 78 now returns null, retaining Driver ID, field geometry and
  13 controls. Driver02 initially remains unknown through frame 6; first accepted
  reading at frame 7 / 1.217 s source receipt elapsed. Stable clips cannot establish
  screen-transition delay. Retained stabilized values do not refresh raw evidence.
- Full replay still has 435/436 expected right titles/control counts. Main04 frame
  102 retains Step 2's ambiguous-division rejection. All 435 localized observations
  retain 20–22 left boxes; 368 have all 22. Existing optical-flow tracking contributes;
  cold frames can lack complete fits. Left analyzer changes from the prior Step 3
  remain unchanged by this correction. Sample03 uncertainty stays accepted.
- 158 vision/109 integration tests, compile and whitespace checks pass. All 144
  fresh separated results exactly match accepted results; 11 frozen separated
  state examples match the previous Step 3 results. Full/compact contracts and
  four complete review-video decodes pass. Comparison with prior Step 3, ignoring
  only the field value, preserves all 436 results including control geometry.
- 44 draft region references: mean/max center difference 2.8/7.7 native px;
  P95/max corner difference 7.1/10.2 px, with about 6–10 px manual uncertainty.
  These use accepted Step 2 rectification, not independent calibration truth.
  New processing means 01–04: 1.10, 1.11, 1.14, 1.07 s/frame;
  offline saved-image timing is not real-time hardware throughput.
- Final review: dmi_computer_vision/outputs/monitor_support/
  step3_correction_20261016_review01/REVIEW.md, review.mp4/review.jsonl per capture,
  contact sheets and explicit direct/stabilized HUD. Reproduction, old snapshots,
  exact field crops, cold frame 78 and test logs: step3_correction_20261016_run01/.
  Earlier step3_20261016_review03 field/layout claims are superseded; its artifacts
  remain intact. Owning specifications/handoff updated under existing docs ignore.
- Integrity: 68 protected files checked against correction start; only
  right_display.py/right_layout.py changed. All 20 capture artifacts, left analyzers
  and other protected sources are unchanged. Temporal logic, actual evidence age,
  schemas, calibration/motion limits and 4-pixel publication tolerance are intact.
  No camera/robot command or physical validation. Step 4 has not started; next is
  partial-region retention and layout/session-history stability after a separate
  implementation request. Other connected states/transitions and selective/
  freshness/export checks remain pending.
- Approved commit scope: four shared analyzer/layout modules,
  tests/test_active_area_analysis.py inside vision, and this root handoff. Owning
  vision docs and generated review evidence remain locally ignored under the
  existing repository policy; recordings/local settings are not included.

**Step 2 localization accepted (2026-10-16), implemented and tested offline.**
User accepted the correction on captures 01–04 and explicitly authorized committing
and pushing the monitor-support updates before the next step. Fixed installed
distance/rotation remains the intended setup. This section records Step 2 acceptance;
Step 3 is tracked above.

- Corrected the existing connected fallback in display_geometry.py: bounded
  analysis scale with native pixel-center mapping, blue-seeded boundary proposals,
  noise/contrast-validated edges and an enclosure hypothesis for distorted dark
  corners. Division uses observed field/keypad or repeated two-column menu borders;
  columns must persist between rows. No fixed split, copied coordinates, filename/
  camera-index logic, analyzer change, extra pipeline or camera-setting change.
- 435/436 frames localize both regions (118/118, 53/53, 156/156, 108/109), versus
  0/436 with the pre-correction module. Main04 frame 102 rejects ambiguous division.
  All 870 accepted geometries pass contract checks; four review videos decode fully.
- Full 4,330-frame separated raw localization is unchanged; 144 fresh complete
  frame results match accepted results. 143 vision/109 local integration tests pass;
  compile/whitespace pass. Five new cases cover menu structure, missing/conflicting
  borders, dark margins and high-resolution native mapping. Source capture artifacts
  and other original production source hashes are unchanged; only geometry differs.
- Draft final-frame division anchors differ by at most 4.4 px with about 8 px
  manual uncertainty. Driver03 upper-left corner differs 16.4 px with about
  10–20 px visual uncertainty. User accepts this small dark-corner limitation with
  lower confidence rather than rejecting the whole display/detections. The user's
  approximate "5%" description is not a measured area or a new geometry tolerance;
  a display-related cause is possible, not established. Confidence here is a
  qualitative review note, not a new output field. Sample03 already localizes
  both regions in all 156 frames; no threshold change was needed for acceptance.
  Fixed-view raw left-center
  P95/max in Driver03 is 5.83/9.43 px; other region P95 values are <=2.11 px.
  No temporal smoothing or calibration/publication tolerance changes hide this.
- Localization means 48.25/51.01/51.70/42.96 ms for captures 01–04; not full-detector
  FPS or a speedup claim. Capture receipt times remain separate from 5-FPS playback.
  Cold/first-12 shared analysis remains right-state unknown, zero right buttons,
  variable left boxes; Driver03 recovers a field. Titles/controls/left-box alignment
  still require Step 3. Other states/transitions are unverified.
- Final review/reproduction: vision outputs/monitor_support/
  step2_refresh_20261015_review02/REVIEW.md; scripts and pre-change snapshot in
  sibling step2_refresh_20261015_run01/. Earlier review01 is incomplete evidence
  (13/156 dark Driver03) and must not be used for acceptance. Root evidence list
  and owning vision UI/evaluation/handoff updated; accepted V2 history preserved.
  No motion, calibration certification or Step 3 implementation. Calibration,
  freshness, raw-evidence and motion limits remain unchanged.
- Commit scope: root guidance/handoff, geometry implementation and focused tests.
  Owning vision specifications were updated locally under the existing ignored
  docs/ directory; generated evidence/recordings remain local. Separate Picamera2
  bridge/source/README/tests, .gitignore changes and local vision guidance/review
  deletions remain outside this commit. The 109 integration checks include eight
  tests from that separate camera work; geometry has no dependency on it.
- Pre-commit verification repeated on 2026-10-16: 143 vision tests and 109 local
  integration tests pass; compile and staged whitespace checks pass. GitHub main
  was verified at the pre-monitor-support reference below before publication.

**Step 1 refreshed baseline accepted for proceeding (2026-10-15).**
User confirms the installed camera/robot/DMI view is fixed in distance and rotation.
Work must use that view; no camera repositioning/zoom/exposure change is required
to proceed. Fixed mounting does not authorize hardcoded pixel partitions or imply
physical calibration/pressing validation. Preserve per-selected-view/session context.

- Reprocessed all 118 Main-capture and 53 Driver-ID-capture frames through the
  unchanged FrameProcessor using sidecar receipt times and separate histories.
  All 171 remain unknown with no geometry/content; saved compact logs reconstruct
  exactly against fresh full results and output contracts pass. No history resets.
- Reviewed first/middle/last MP4 frames and final PNGs for both captures: full
  monitor visible; Main/menu and Driver ID/value `23`/keypad/left boxes are present
  in the sampled evidence. Mask measurements exclude the old HUD rectangle;
  surface hypotheses do not intersect it. Source input pixels were not altered.
- All 171 have one significant production-blue component. The connected fallback
  rejects 170 fits at the top edge and one at the left edge, before division or
  analysis. Main diagnostics: 117 invalid_surface/1 clipped_surface; Driver ID:
  53 invalid_surface. Some color hypotheses extend outside the monitor, so the
  clipped label is not proof of physical clipping. The Main final PNG and final
  MP4 frame yield different failed hypotheses/labels; saved encoding is a limit.
- Main also lacks the pale input field/three-column keypad required by the current
  division helper. Step 2 must correct the existing boundary/division fallback for
  both Main and Driver ID without adjusting camera framing or duplicating pipelines.
- 144 fresh full-pipeline frames from six separated recordings exactly match
  accepted results; 11 raw/accepted state examples and historical 4,330-frame
  summaries preserved. 138 vision/109 integration tests pass; whitespace passes.
  All 70 protected input/source hashes match before/after. No detector/capture/
  analyzer/calibration/robot implementation changed; no commit/push or motion.
- Review/reproduction: `dmi_computer_vision/outputs/monitor_support/` +
  `step1_refresh_20261015_run01/REVIEW.md` and `refresh_baseline.py --output-dir NEW`
  from root. Fresh offline mean processing 39.14/40.48 ms on unknown output is not
  successful detection throughput. Timing uses receipt spans 16.582/7.452 s, not
  5-FPS playback. Other states, transitions and target errors remain unverified.
  Review this baseline before Step 2 corrections; earlier completion does not transfer.

**Current evidence refresh (2026-10-15):** user replaced the previous connected-
monitor sample with `dmi_computer_vision/data/videos/dev/dmi_capture_quality_01/`
and `dmi_capture_quality_02/`. Root AGENTS.md now makes these the active inputs;
the removed `dmi_detection_check_03/` and its results below are historical only.
Preserve existing detector changes and original separated-display regressions.
This refresh changes guidance/handoff only; no detector or capture code changed.

- Both videos decode fully at 2304x1728: 118 and 53 frames. Final images show the
  complete connected monitor, clearer text and less white clipping than the old
  sample. Capture 01 shows Main/menu buttons; 02 shows Driver ID/field `23`/keypad.
  These are two states on the connected arrangement, not coverage of both monitor
  types or all supported states. Camera index/deployed detector version are absent.
- Saved compact logs remain unknown with null left/right geometry and no controls.
  Fresh read-only `detect_displays` calls on all annotated frames also find neither
  region: 01 has 117 `invalid_surface`, 1 `clipped_surface`; 02 has 53
  `invalid_surface`. These describe rejected fitting hypotheses, not verified
  physical clipping. The previously reported Step 2 success does not transfer.
- Session/sidecar counts agree. Regular processing, no policy skips or errors;
  receipt spans 16.582/7.452 seconds, processed throughput about 7.00/6.89 FPS.
  MP4 playback is 5 FPS; evaluate timing with processed_frames.jsonl. Captured
  frames overwritten in the latest buffer: 121/56. Throughput on unknown output
  is not a successful full-detector benchmark or the camera sensor frame rate.
- Supplied videos already contain annotations; raw inputs and sensor readback
  are absent. Separate original overlays from fresh results and use raw evidence
  when available. New profile framing is visible, but exact native mode, AF,
  exposure readback and capture rate are not established by these output files.
- Next implementation: refresh visual references on both captures, correct/review
  connected localization, then verify shared content analysis. Main has no pale
  input field/numeric keypad, so those cannot gate localization of every state.
  Preserve original-pixel coordinates, conservative ambiguity handling and all
  calibration/motion checks. No physical calibration or pressing validation.
- Checks for this documentation refresh: metadata/compact/sidecar inspection,
  both final PNGs viewed, all 171 MP4 frames decoded and current localization
  measured using pyenv Python 3.13.3/OpenCV. No full-pipeline replay or test suite
  rerun; previous test results below are historical. No commit/push authorized.

Capture-profile follow-up (2026-10-15): user requested CameraTool2 settings as
bridge defaults while monitor-support Step 2 awaits review. Picamera2 now requests
2304x1728/10-bit sensor mode and output, continuous AF, -2 EV, 30 FPS, both flips.
Bridge defaults to Picamera2 camera 1 and 10-FPS JPEG publication; receiver must
use rotation 0 instead of 180. Actual selected sensor/output settings are printed.
Closest native sensor mode may differ from the request. Actual mode and sustained
load remain to be confirmed. MP4/25-Mbps recording is not part of JPEG transport.
Only source/bridge/tests/integration README and this handoff changed for capture;
concurrent monitor geometry/specification changes were preserved. No commit/push.
Verification: 109 integration tests pass, including eight fake Picamera2 source/
bridge cases; bridge help and whitespace checks pass. New supplied captures now
show real 2304x1728 HTTP reception with receiver rotation 0; deployed-file parity
and printed actual sensor settings still need confirmation. More pixels may
increase encoding/network/detection
cost; measure the installed path before changing freshness limits or robot gates.

**Current milestone: support separated displays and the connected single monitor
in the shared vision pipeline — Step 2 localization accepted on captures 01–04;
Step 3 shared screen analysis is completed offline and approved; Step 4 is
completed offline and approved on 2026-10-19; Step 5 has not started.**
User accepted corrected Step 3 and authorized
its commit/push on 2026-10-16. Step 2 acceptance includes lower-confidence
acceptance of sample03's dark corner. Root AGENTS.md defines the steps. User confirms real camera capture,
transmission and master-PC reception have been tested on hardware; remaining work
concerns detection. Connected localization now succeeds on 435/436 current frames;
shared analysis is verified on Main/Driver ID, Step 4 partial/stability work is
approved offline, and Step 5 end-to-end validation remains incomplete.
No physical calibration accuracy or robot pressing has been validated.

Phase 6 is completed offline and accepted (2026-10-12). The original numbered
phases plus 3A remain accepted; do not restart or relabel them.
Phase 5 was accepted including its timestamp correction on 2026-10-12.
Accepted/pushed: Phase 1 e95e274, Phase 2 bd99ef6, Phase 3 5f2abe0, Phase 3A 160ea04,
Phase 4 ea6f5d1, Phase 5 ed66b83, Phase 6 15dabbd. The pre-monitor-support
HEAD/origin/main reference is 022202a (Add icons), on
https://github.com/H4miiiid/DMI_R-D_ALTEN.git. Existing uncommitted Picamera2
source/bridge/tests/README work must be preserved. No robot motion or backend
implementation is established by this camera trial.

Updated hardware facts (2026-10-15): Debian 12 Linux/Pi slave, hostname dmirobot,
serves cameras over Ethernet. Confirmed slave eth0 address is 192.168.1.210/24;
the earlier 192.186 address was incorrect. Mac master Ethernet is 192.168.1.133/24;
Windows master use is also intended. rpicam-hello shows both cameras with rotation 180; Picamera2 lists
two IMX708 cameras (0 and 1). Picamera2 imports successfully and user belongs to
video group. OpenCV bridge failed to open 0/1; libcamera source is required.
User confirmed two arrangements: one camera views a single monitor with connected
left/right content; the other views two separated display regions. Camera 0/1 to
arrangement mapping is not confirmed; do not hardcode it. Logical Driver ID, Level,
Train Running Number and other supported UI content retain the same meanings.
PC detector uses one selected camera/latest-JPEG bridge per session. Wider
calibration remains unvalidated. Robot origin stated bottom-right, +X left, +Y up, travel
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

Accepted phase evidence is simulation. User has now demonstrated live Picamera2
capture and HTTP reception on the Mac. Single-monitor localization is accepted
on the reviewed captures, with Main/Driver ID shared analysis tested offline.
Some left boxes are omitted when borders are unsupported; Step 4/5 verification remains.
No real pressing or physical calibration accuracy has been demonstrated.
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

## Phase 6 — completed offline, accepted 2026-10-12

New verify_offline.py runs fresh recording calibration, three independent fake
label presses and the full Driver ID-to-Level transition, with output/compact and
annotation decode checks. New test_offline_integration.py connects actual live
orchestration/projection/publication/actions/master/slave with controlled synthetic
observations for verification and failure cases. README documents startup and the
existing get/preview/request interface. Detector/base robot code unchanged.

101 integration and 129 vision tests pass; compile/whitespace checks pass. Four
new cross-phase tests cover three fake selected presses with controlled newer
field observations, wrong screen/removal/calibration/bounds rejection, stale file/
evidence/camera failure and ERROR/timeout/disconnect latch with detection continuing.

Passing recorded run: ignored vision outputs/robot_integration/phase6/run03/;
verification.json, button_tests.jsonl and calibration/actions/transition artifacts.
440 actual detections (12 calibration + 7 action + 421 transition) passed output
contracts, compact reconstruction and annotation decode checks. Three fake presses
KEY_4/5/6 received DONE/newer evidence, UI unconfirmed (recorded value stayed 12).
Fresh simulation fit held-out mean/max error 0.653/1.119 mm against reference JSON.
Transition captured 855/processed 421 in 111.41 s; 236 overwritten + 198 policy
skips, 7.67/3.78 FPS; mean/max receipt-to-result 239.7/424.0 ms. No history resets.
192 Driver ID/146 Level/83 unknown observations (79 obstructed). Uncalibrated
transition mm stayed null/unusable; both sessions cleared targets on stop.
Three Driver ID/Level sample annotations inspected and retained as *_review.png;
broad layout alignment, inherited jitter/OCR/loss limits remain. No per-frame
ground truth, sensor/network latency or physical accuracy claim.

Reproduce from root in existing Python 3.13.3/OpenCV/Tesseract environment:
`python3 -m unittest discover -s tests -q`,
`python3 -m unittest discover -s dmi_computer_vision/tests -q`,
`python3 -m dmi_robot_master.integration.verify_offline --output-dir
dmi_computer_vision/outputs/robot_integration/phase6/verification_NEW` (one line).
Use new output directory. Test logs: /private/tmp/dmi_phase6_integration_tests.log,
_vision_tests.log; replay: /private/tmp/dmi_phase6_replay.log. Earlier run01/path
smoke and run02/report-serialization failures are incomplete evidence; both runner
issues fixed before passing run03. No calibration/detector/base robot behavior changed.

Phase 6 was approved and committed/pushed as 15dabbd. Preserve that acceptance;
the live monitor-support failure is a new vision follow-up, not a completed
hardware validation of the original integration.

## Hardware trial follow-up — Picamera2 bridge, 2026-10-14

- Added integration/picamera_source.py and explicit frame_bridge --backend
  picamera2; OpenCV remains the default. Lazy Pi import, BGR RGB888 stream,
  single latest-frame slot, increasing indices/local receipt timestamps,
  timeout/error propagation and camera cleanup. No detector/robot changes.
- README includes slave/Windows startup commands and PC-only rotation; final
  camera/resolution/orientation need visual confirmation before new calibration.
- Added six fake-device tests for selection, channel/copy contract, bounded slot,
  capture error, timeout/stale data, close/unblock and failed-start cleanup.
- All 107 integration tests passed in the existing pyenv Python 3.13.3 environment;
  bridge --help and git diff --check passed. The default system Python lacks
  OpenCV/NumPy; use the configured environment. No Pi device accessed locally.
- User subsequently confirmed actual camera capture and HTTP preview reception.
  Deployed-file parity and capture settings still need confirmation. No motor
  commands or commit/push authorized for this follow-up.

## Connected-monitor investigation and next step — 2026-10-15

- Historical evidence: root dmi_detection_check_03/ (user-provided live session,
  subsequently removed/replaced; no longer an active prerequisite).
  749 processed 1280x720 frames over about 93 s, regular processing, zero policy
  skips, no session error. Compact log stays at null left/right geometry, unknown
  screen and empty fields/buttons. Original debug/raw per-frame logs are absent;
  saved video already includes annotations. Source frames remain preferable for
  independent image tests.
- Read-only segmentation of all 749 saved video frames found one significant blue
  component per frame. display_geometry._split_display_components requires two;
  it rejects the connected monitor before screen/OCR/button analysis. The existing
  portrait geometry check also cannot accept the whole wide monitor as a region.
- Baseline Driver ID first frame has two components and detects both regions even
  resized to 1280x720. Resolution alone does not explain the observed failure.
- Diagnostic in-memory partitions let existing right analysis find a field, but
  not title/buttons. Those guessed partitions are not valid geometry or a fix;
  actual monitor/internal-boundary fitting and downstream alignment must be checked.
- New plan: preserve separated-display path, add connected-surface localization,
  reuse common analyzers, make only justified title/border adjustments, review
  independent-region failure handling, then regress both arrangements with visual
  center/border evidence and timing/freshness checks. No fixed midpoint, synthetic
  black separator, filename/camera-index rules or duplicate detector.
- Root AGENTS.md now defines the implementation sequence and acceptance criteria.
  This update changes those two Markdown files only; the new detector support is
  not implemented or tested. Prior 107 integration/129 vision results do not prove
  connected-monitor support. Next agent should read the active plan and inspect
  representative raw evidence before implementing the localization extension.
  No commit, push, calibration certification or robot action requested.

## Monitor support Step 1 — baseline accepted for proceeding, 2026-10-15

- Scope: failure and separated-display regression baseline only; no detector,
  calibration, robot or output-schema changes. Step 2 has not started. User confirms
  hardware camera capture/transport/reception; this does not certify physical
  calibration or pressing.
- Original 749-frame session remains entirely unknown. All 749 saved annotation
  frames decode; threshold-only and production segmentation each find exactly one
  significant blue component throughout. `_split_display_components` requires two,
  so no logical region reaches the shared analyzers. Fresh reprocessing reproduces
  unknown output. The source directory contains no raw single-monitor footage;
  annotation/encoding contamination is explicitly recorded.
- First/middle/last review: Driver ID visible; full monitor in frame 0, lower edge
  clipped in later close views, soft text/weak blue borders. One component reaches
  the image bottom in 546 frames. Other states on this arrangement are unverified;
  center/border error, jitter and transition delay cannot be established here.
- Six separated recordings: 144 fresh native frames (first 24 per clip) exactly
  match accepted results; contracts pass. Full historical summaries retain 4,330
  frames and 11 frozen state examples with raw source PNG/accepted JSON/annotations.
  These are accepted predictions, not new ground truth or a full fresh replay.
  A 1280×720 separated control still finds both displays/22 left boxes; cold-frame
  right recognition is unknown. Resolution alone is not the localization cause.
- 107 integration and 129 vision tests pass. Reproduction: existing commands above;
  baseline script, exact metrics, test logs, before/after input/source SHA-256
  manifests and visual review outputs under ignored
  `dmi_computer_vision/outputs/monitor_support/step1_20261015_run01/` (`REVIEW.md`).
  Run its `baseline.py --output-dir NEW_DIRECTORY` from root. Hashes match: original
  evidence, accepted inputs and production Python sources are unchanged.
- Preserve pre-existing local changes, including deleted vision AGENTS.md/review.md;
  their HEAD versions were read without restoring files. Accepted V2 history and
  owning behavior specifications remain unchanged. Review this baseline before
  Step 2 localization work. No commit/push or robot action performed.

## Monitor support Step 2 — completed offline, awaiting review, 2026-10-15

Historical completion claim for the superseded sample only. Replacement-capture
inspection above reopens localization validation; do not advance on this claim.

- Added a connected-surface fallback colocated with display_geometry.py. Existing
  successful separated-display localization remains the first path. A blue-seeded
  boundary hypothesis is refined using observed chromatic edges; the division
  requires agreement between a pale upper field and lower three-column grid edges.
  Logical quadrilaterals map back to original pixels. No midpoint, copied source
  coordinates, synthetic stripe, camera-index rule or analyzer modification.
- Initial review: 190/749 saved frames localized; 548 rejected as clipped, 6 invalid
  surface and 5 ambiguous division. The saved evidence remains annotation-contaminated;
  this is not raw-camera or hardware validation. Other states remain unverified.
- Nine new synthetic cases pass (perspective and both sides of midpoint,
  off-center/scale/blur/exposure, distractors, missing/conflicting structure,
  multiple surfaces, clipping and diagnostics). 138 vision/107 integration tests
  pass; 144 fresh full-pipeline separated frames exactly match Step 1.
- Full raw-localization regression: all 4,330 separated-display frames exactly
  match the pre-change geometry, including missing cases. All 380 connected
  display geometries pass contract checks. Draft visual references on frames
  0/100/180 have outer-corner differences up to 5.8 px, with about 3–5 px manual
  uncertainty; these are not approved ground truth or physical accuracy. Raw
  center movement in frames 0–35 has P95/max 1 px for each logical region and
  includes camera motion. Localization mean/P95 9.66/17.23 ms on the saved clip;
  supported frames average 16.48 ms, not full-detector throughput.
- Owning UI/output specs and vision handoff/evaluation updated separately from
  accepted V2 history. Evidence/inputs and all other original production Python
  sources hash-identical. Final focused geometry checks, compile and whitespace
  pass. Review outputs: outputs/monitor_support/step2_20261015_review01/ inside
  vision, including REVIEW.md, geometry-only video, original-resolution outline
  samples and rectified regions. Scripts/pre-change snapshot/probes: sibling
  step2_20261015_run01/. Output/docs directories remain locally ignored as before.
- Cold analyzer diagnostics: frame 0 still finds no field; frames 100/180 find a
  field and an unread title candidate, but all three remain unknown, with zero
  buttons/left boxes. This is localization-only progress, not end-to-end monitor
  support. No analyzer changes were made. Other states/field-free layouts remain
  unverified; clipped surfaces and ambiguous layouts conservatively return neither
  region. Independent-region retention and temporal layout resets remain Step 4.
- Next: user review of Step 2 before any Step 3 analyzer work. No calibration
  change, commit/push or robot action. No new hardware or physical accuracy claim.
