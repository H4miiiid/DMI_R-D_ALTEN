# Current handoff — SENSE vision and robot integration

Updated 2026-10-27. Read `AGENTS.md` for the new numbered roadmap and working rules.
This file records current facts and approved progress, not a claim that the future
steps are implemented. Git history retains the earlier detailed handoffs.

## Resume here

AGENTS Steps 1–6 and the reusable SENSE optimization are accepted
offline/recorded-camera (latest approval 2026-10-27). Step 6 is accepted for now
with detection speed still an open concern; this is not acceptance of general
real-time performance. The user authorized committing/pushing Step 6 and this
handoff. Steps 1–3 were published in `f14e46c`, Step 4 in `0d26bd9`, and Step 5
plus the shared optimization in `0360b7b`. Next proposed implementation: Step 7
(SENSE Validate Train Data, titles/buttons only), awaiting explicit authorization.
Installed-camera speed, natural transitions and physical performance remain
unverified. Keep reports in chat; accept later steps only after user approval.

Plan clarification (2026-10-26): Steps 5–7 on SENSE require visible titles and
buttons only, including visible left Yes and right keypad/selector/navigation
buttons. Left summaries and noninteractive right text/rows/field values/confirmation
content are excluded from OCR, annotations and optional exports in those states.
Keep localization, button evidence/freshness and existing schemas; preserve Step 4
and TWIN behavior. Measure accuracy and processing cost before claiming gains.
This is a roadmap update only; it does not start or accept Steps 5–7.

TWIN scope clarification (2026-10-26): the user accepts the existing TWIN
detections. Upcoming detection work targets SENSE only; leave TWIN code, tuning,
pipeline behavior and outputs unchanged. Shared-module edits must be SENSE-only;
TWIN checks are regressions, not a tuning/fix task. Existing limitations remain
documented, and physical TWIN calibration/pressing validation is still deferred.

Accepted evidence entry point — `runs/accepted/` (curated 2026-10-26 at the
user's request): `step01_level_accuracy`, `step02_level_speed`,
`step03_monitor_localization`, `step04_train_data`. Each has three previews,
one accepted replay `annotated.mp4`, selected machine results and one summary with
original paths/hashes, historical source version, accepted measurements and limits.
These are historical copies,
not new runs or physical validation. Complete original evidence stays unchanged
at the paths below. This local ignored selection needs separate supply in a clone.
Videos contain only processed replay frames at 5-FPS playback; the summaries record
their source sessions, frame counts and coverage separately from sequential results.

Automatic two-reviewer workflow — approved for commit/push (2026-10-23): main
agent implements one authorized step, code_review and step_checker independently
review, main fixes/rechecks, then both confirm the final version before one short
chat report and user approval. No per-step report files; STATE.md is updated only
after approval. Acceptance, publication and starting the next named step remain
separate permissions. Both reviewers returned PASS on the workflow instructions.
The workflow files (AGENTS.md, `.codex/config.toml` and both reviewer TOMLs) are
included in `b071752`; models and concurrency are unchanged. Workflow approval
itself did not authorize runtime work or hardware operations.

Step 6 — accepted for now offline/recorded-camera; commit/push authorized
(2026-10-27). Detection processing remains too slow for the user's desired
experience; further performance work remains open and is not authorized here.
Recognize SENSE page-2 title/current left Yes and measured selector/navigation
buttons; omit summary, information rows/values and confirmation text. Reuse
current-border/glyph helpers with bounded exact-label OCR retries; reject false
half-cell fits instead of relocating boxes through legacy anchors. TWIN behavior
and previously accepted SENSE results remain unchanged. Reviewed source
`2569c74c4949c785879fc57ebeeda82274aa2a8b2eebbe1c9823719e78817b03`;
both reviewers PASS WITH WARNINGS, no blockers. All 69 frames retain title/left
Yes and eight right controls; G1 appears in 58/69 and is omitted when uncertain.
Cold first/middle/last samples recognize all nine right buttons. Synthetic label/
layout changes, missing edges, duplicates, information independence and loss/
recovery pass. All 225 other SENSE frames and 51 cold regressions match exactly.
Final suite: 385 passes plus 265 subtests; each reviewer independently passed the
10 new tests. Current validation costs more than the former misplaced positional
output: analysis mean/P95 0.172/0.176 -> 0.271/0.288 s; OCR 69/0.99 -> 451/3.68 s
(calls/total time). Regular receipt replay: 3.25 detection FPS, 4.78 headless preview
callbacks/s, P95 local result age 0.495 s; 47/69 processed, 22 overwrites, zero policy
skips. Selective: 2.56 detection FPS, P95 age 0.470 s, 28 policy skips. Freshness/
confirmation/4-px publication gates remain unchanged; targets clear on stop.
Measured center jitter mean/P95/max 1.00/5/10.8 px; old anchored but misplaced
coordinates were steadier. Coarse frame-0 center error mean/max 5.47/10.82 px
against agent border readings with about +/-8 px uncertainty, not human/mm truth.
Canonical accepted evidence: `runs/step06_train_data_2_2/` (compact results,
summary, publication/expiry evidence, before/after video and two PNGs). The video
shows all source frames at 5-FPS playback, not detection throughput or live GUI
paint cadence. Only loading-gauge selectors are covered; other selector layouts,
independent held-out footage, natural transitions and physical validation remain
unverified. An earlier full run and standalone rerun hit a simulated-terminal
completion timeout; baseline/candidate diagnostics and final suite passed. The
intermittent issue remains unresolved/disclosed; no action/freshness gates changed.
Local tests/evidence require separate supply in a clone. No hardware actions.

Step 5 + reusable SENSE optimization — accepted offline/recorded-camera;
commit/push and subsequent Step 6 authorized (2026-10-27). Rebuilt page 1 from
accepted Step 4: current visible titles, left Yes and measured right keypad/
Delete/decimal/navigation only; clear excluded summary/field information. Final
reviewed source `c5eca9b5b2df8596274ed50403b0b870faca71c68341575f8698742595580f3e`;
both reviewers PASS WITH WARNINGS, no blockers. Page 1 localizes/recognizes 84/86
frames; overlay-affected 9/15 fail closed. All 16 right controls in 79/84 valid
frames; remaining uncertain glyph omissions unchanged by optimization. Matching
Tesseract C API reuse and current-image border memoization preserve all 294
recorded rich/direct results, 51 cold regressions and 12 Main/Driver samples.
Full suite: 375 passes plus 265 subtests. Page-1 analysis mean/P95 0.621/0.696 ->
0.279/0.310 s; 352 OCR calls unchanged, total OCR time 26.05 -> 3.38 s. Matched
receipt replay: 1.63 -> 3.34 detection FPS with original preview, or 2.77 detection/
6.88 fresh-preview callbacks per second with SENSE-only opt-in smooth preview;
P95 local result age 0.558 s, 52 overwrites and zero policy skips. Level remains
1.57 detection/4.65 preview callbacks per second. Display-only center deadband
reduces mean page-1 jitter 1.16 -> 0.91 px; P95/max unchanged. Machine coordinates,
direct evidence age, confirmation, 4-px publication tolerance and 1.5-s expiry
remain unchanged. Default TWIN detection/preview remains unchanged; new smooth
preview is SENSE-only. Source loss/stop clears targets; no hardware actions.
Canonical accepted package: `runs/sense_realtime_optimization/` (summary, compact
results, publication expiry/clear evidence, one labeled receipt-trace reconstruction
video and two PNGs). Historical rebuilt Step-5 evidence remains immutable at
`runs/step05_train_data_1_2/`; the optimization package is the current entry point.
Preview callbacks/reconstructed video are not GUI paint or installed-camera
measurements. CLI fallback without a matching native library may retain old speed.
Natural transitions/new framing, independent human center truth and physical
validation remain unverified; local tests/evidence require separate clone supply.
Page-2/validation replays only preserve baseline behavior; Steps 6/7 semantics
are not implemented or accepted by this milestone.

Step 4 — accepted offline/recorded-camera; publication authorized (2026-10-23):
measure Train Data controls from current borders/glyphs; recognize the two-tone
train-type field, left title/summary and completion Yes independently. Add optional
left summary geometry/value to rich/compact output and annotations, never targets.
Both reviewers initially flagged missing summary recognition; corrected and both
re-reviewed final version `f5b3cb819c63df0103fd3de91f6fd6c162ea050712c7c50747c20957319b8c6f`:
PASS WITH WARNINGS, no unresolved blockers. All 61 SENSE frames retain left
title/summary/Yes and six right controls; direct right Gamma is 58/61 (uncertain
11/35/59). Cold startup, independent left/right Lambda changes, duplicates, blanks,
missing borders and loss/recovery pass; existing confirmation/freshness gates stay.
Suites: 227 vision and 126 integration passes; compact reconstruction has zero
semantic mismatches at 4 px. Existing content is exact in 40/42 cold regressions
(39/42 including new summary metadata); measured Train Data geometry differs and
blurred/hand-occluded TWIN frame 286 omits four legacy nominal controls. Six clear
TWIN views retain summary, Gamma and four controls. Coarse matched center error
mean 29 -> 2.72 native px (agent references ±5 px, not human ground truth).
Analysis mean/P95 0.755/1.196 -> 0.704/0.733 s; OCR 486/36.42 -> 421/32.05 s.
Receipt replay regular/selective ~1.344/1.353 processed FPS; each consumes 11/61,
with 50 overwrites and zero policy skips. P95 local result age 0.916/0.871 s,
excluding upstream age; targets remain unusable and clear on stop. No selective
saving established. Natural SENSE Lambda/transitions/new framing, independent
human position truth and hardware performance/physical accuracy remain unverified.
Durable local evidence: `runs/step4_train_20261023_01/review2/`; ignored media and
evidence require separate supply in a clean clone. No hardware actions performed.

Step 3 — accepted offline/recorded-camera; publication authorized (2026-10-23):
localize from current sparse border segments without a mandatory keypad/menu;
recheck dim top boundaries, exclude saturated non-blue marks, and reset only
incompatible geometry bases. Optimize existing topology scoring with identical
hypotheses/penalties/ties (48 generated cases and recorded 277-candidate fit match).
Both regions found in 292/294 frames: Level 53/53, Train 61/61, page 1 84/86,
page 2 69/69, validation 25/25. Annotated page-1 frames 9/15 fail closed; clean
replacements are needed to assess those views. Forty-two cold regressions match
exactly. Suites: 218 vision and 126 integration passes; former Main->Driver
expected failure now passes normally. Both reviewers: PASS WITH WARNINGS.
Level ten controls/value/activity remain stable; TBL1+ stays 51/53, but omissions
move 17/23 -> 19/21. Mean center difference 0.61 px; jitter mean/P95 improves
1.48/5.39 -> 1.45/5.10 px. Level geometry mean 0.056 -> 0.107 s; full analysis
mean/P95 0.825/1.054 -> 0.909/1.127 s, OCR 242 -> 252 calls. Receipt replay
regular/selective ~1.12/1.05 processed FPS; some ages exceed unchanged 1.5-s
expiry, excluding upstream age. Targets remain unusable and clear on stop.
Train semantics remain Steps 4–7; natural SENSE transitions/new framing, independent
boundary truth and hardware performance remain unverified. Durable local evidence:
`runs/step3_geometry_20261023_01/`; ignored evidence/tests need separate supply.

Step 2 — accepted offline/recorded-camera; publication authorized (2026-10-23):
batch current measured Level text crops into one OCR call, retaining individual
retries, exact-label/current-border checks and unchanged freshness/confirmation
gates. All 53 rich/direct results match Step 1 exactly; jitter and two TBL1+
omissions persist. Matched analysis mean/P95: 1.281/1.514 -> 0.833/1.067 s;
OCR 617 -> 242 calls, 42.21 -> 18.89 s. Receipt replay regular/selective:
~0.76 -> ~1.15 processed FPS; P95 result age ~2.02 -> 1.29/1.27 s, excluding
sensor/network age. Thirty cold regressions retain all previous identities;
one visibly supported TWIN KVB is gained. Suites: 210 vision passes, 125
integration passes plus the existing expected failure. Both reviewers: PASS
WITH WARNINGS. Synthetic changes/loss/recovery pass, but direct recognition
and confirmed values differ: one change is recognized at ~1.05 s and confirmed
at ~7.88 s under unchanged 15-observation/capture-gap rules. Natural TWIN replay
uses assumed timing; real SENSE transitions/new framing and physical performance
remain unverified. Static selective replay shows no additional policy saving.
User accepts these limits for now, pending their real hardware validation.
Durable local evidence: `runs/step2_level_20261023_01/`; ignored evidence/tests
remain unavailable in a clean clone unless separately supplied.

Step 1 — accepted offline/recorded-camera; publication authorized (2026-10-23):
fixed reproduced broad-outline/gap fitting failure with a wider retry only after
all narrow fits fail; current border-support gates and fresh OCR/activity crops
are preserved. All 53 Level frames retain identities/activity and OCR counts
(617 total); ten controls 53/53, TBL1+ 51/53 (omitted at 17/23). Thirty paired
cold regression samples preserve semantics. Cold startup and synthetic changed
field/activity/loss/recovery pass. Suites: 204 vision passes; integration 125
passes plus the existing expected transition failure. Both reviewers: PASS WITH
WARNINGS, no blocking findings. Mean estimated center/border error improves
5.94/4.53 -> 4.06/2.86 px against agent visual references (±4 px, not human ground
truth); maxima remain ~9/~13 px. Jitter mean/P95 rises 1.08/5.00 -> 1.48/5.39 px.
Sequential analysis mean/P95: 1.27/1.46 s. Regular receipt replay: 0.69 processed
FPS; age mean/P95 1.59/2.14 s, sometimes exceeding unchanged 1.5-s expiry; targets
clear correctly. Real SENSE variants/transitions and physical behavior remain
unverified. Durable local evidence: `runs/step1_level_20261023_01/`, including
before/after/live_regular outputs, comparison/reference JSON and suite logs.
Extra ignored tests/evidence remain unavailable in a clean clone; critical
regressions are in already tracked test files.

Level activity update — accepted offline, commit/push authorized (2026-10-22): distinguish active
Level 0/1/2, KVB, X/Close and .../More from inactive Level 3, MEMOR, ATC-2, SCMT
and TBL1+ in the current SENSE view. Add `active` boolean/null to detected Level
buttons and target JSON, parallel `button_activity` in compact JSONL, and green/
gray/amber status annotations. Use current glyph color evidence, not fixed label
availability; null is uncertain. Preserve all centers/identities and omit missing
controls. Inactive/uncertain targets must be rejected by action consumers.
The user clarified that the original request intended a future plan step; the
runtime change had already been made and is now explicitly approved for publication.
Future requests to edit the plan must not trigger runtime implementation. This
metadata update does not accept/complete broader Step 1 or authorize physical motion.
Checks: 200 vision tests pass; integration 125 checks = 124 passes
and the existing expected transition failure. Full 53-frame raw Level replay
matches the requested activity groups for every recognized control (TBL1+ remains
omitted twice); removing activity metadata reproduces the old results exactly.
Compact JSONL reconstructs all 53 frames without semantic mismatches. Preview/video,
JSONL and last rich JSON are under `/tmp/dmi_robot/level_activity_20261022_01/`;
temporary review artifacts only. No additional OCR or physical action.

## Repository and hardware baseline

- Current Step 4 implementation review base: `f14e46c`, branch main; Steps 1–3
  were published there after workflow `b071752`, roadmap/activity `eb88729` and
  Level/optional-controls/launcher/recorder `e95d707`. Accepted Step 4 publication
  is explicitly authorized and included in the commit carrying this handoff.
- Original integration Phases 1–6 plus 3A were accepted offline, ending `15dabbd`.
  Monitor localization/shared analysis/stability are `27b085e`, `99f9aea`,
  `6ecdcc2`; Step 5 validation is `cf10c81`. Preserve these foundations; they do
  not establish full monitor coverage or physical robot accuracy.
- Camera 1 = upper connected SENSE; camera 0 = lower separated TWIN/TWINS.
  One selected camera/session. Same core pipeline; no camera-index screen rules.
- Pi uses Picamera2/IMX708. Requested bridge defaults: 2304x1728, autofocus,
  -2 EV, 30-FPS capture, 180-degree source rotation; receiver rotation 0.
  JPEG publication defaults to 10 FPS. Actual selected mode/cadence need checking.
- Camera HTTP acquisition/reception has worked on hardware. Last known Pi URL:
  `http://192.168.1.210:8080/frame.jpg`; last known PC address `192.168.1.133`.
  Root PC/Pi YAML still references Pi .100 and PC UDP port 50; TapperWare's local
  YAML uses .210/port 50. Verify deployed IP/ports; do not silently change them.
- Physical vision calibration, independently measured offsets, UDP robot trials
  and successful vision-guided presses are not established by existing evidence.

## Architecture and code to inspect

- Vision core: `dmi_computer_vision/src/dmi/detection/{display_geometry,right_display,
  right_layout,left_display,left_layout}.py`, temporal trackers, pipeline/live and
  output modules. Local `docs/UI_SPEC.md`/`OUTPUT_SPEC.md` describe accepted output;
  these ignored docs can contain historical coverage claims, so check current code.
- Integration: `observe.py`, `record_raw.py`, `frame_bridge.py`, `camera.py`,
  `picamera_source.py`, `processing_policy.py`, `publication.py`, `targets.py`,
  `calibration.py`, `calibrate.py`, `actions.py`, `action_transport.py`, `commands.py`.
  Existing compact logs, current state/targets, direct evidence and freshness
  checks should be extended, not replaced with another pipeline.
- `press_label.py` already combines detection, preview and terminal KEY_n input.
  `run_robot.py NAME` forwards settings from its adjacent `run_robot.json`, saving
  under `/tmp/dmi_robot/NAME` with sibling progress/action logs. It replaces
  observe for action sessions. Physical config fields intentionally remain null;
  this launcher is not a calibration/commissioning workflow.
- TapperWare: `main.py`/`DmiGUI.pyw` -> `dmi_gui.py` (`DmiControlPanel`) ->
  `dmi_runtime.py` (`compile_script`, `Runner`, `RealBackend`). GUI has model/panel
  selection, initialization, XML actions, demo, settings, photos and activity view.
  UI uses asyncio; protocol calls run on one executor worker.
- Current GUI compiles XML to static database coordinates, applies a selected
  panel's Y offset, sends ACK then INITIALIZE, runs sequential operations and
  normally returns to origin. It is not CV-integrated. GUI demo is not readiness.
- GUI RealBackend imports flat local protocol/controller copies, opens a separate
  UDP socket and lacks full socket cleanup. Integration uses common protocol and
  validated RobotCommands/RobotLink. Share ownership via a small adapter; do not
  run both command clients. Live vision uses HTTP/TCP; actions/responses use UDP.
- `dmi_photos.py`/legacy TAKE_PICTURES is separate from HTTP capture. Avoid opening
  an already-owned camera; future photos should reuse the bridge's recent frame.
- `dmi_robot_general/` is a legacy reference copy. Root README is a GitLab template.

## Detection evidence and present limits

User confirmed observation_08/09 as the intended SENSE sources on 2026-10-22.
Directory names must not be used as screen identities.

- `runs/level_raw_01/`: Level, raw.mp4, 53 frames, 2304x1728, 10.683-s receipt span.
- `runs/observation_08/`: Train Data (Gamma/Lambda), annotated.mp4, 61 frames,
  7.181-s receipt span. Existing upper-left HUD; unaffected monitor pixels usable.
- `runs/observation_09/`: Train Data (1/2), annotated.mp4, 86 frames,
  11.887-s receipt span. HUD and occasional monitor-crossing annotations;
  Step 3 rejects frames 9/15. Right numeric-entry/field rows are visible.
- `runs/level_raw_02/`: Train Data (2/2), raw.mp4, 69 frames, 13.910-s receipt span;
  reviewed first/last images show loading-gauge G1/GA/GB/GC/Out of GC selection.
- `runs/level_raw_03/`: Validate Train Data, raw.mp4, 25 frames, 4.850-s receipt span;
  reviewed first/last images show summary, right Yes field, No/Yes and Close.
- All are local evidence; preserve source files and receipt sidecars. Playback
  commonly uses 5 FPS; use sidecar receipt times for event timing. Exclude existing
  overlay pixels and state evidence limitations instead of treating annotations as truth.
- SENSE Main/Driver: quality captures 01–04 under vision data/videos/dev remain
  regression evidence. Train Running Number needs representative SENSE validation.
- TWIN: original videos `driver_id_12`, `driverID_to_level`, `level_to_main`,
  `train_numbers`, `train_data_gamma`, `validate_train_data` and existing frozen
  examples preserve prior workflows. Limited sampled equality is not full equivalence.

Pre-Step 1 Level review reproduced all 53 raw frames exactly:
Level/field Level 1 correct 53/53; ten controls 53/53, TBL1+ 51/53, no unexpected
identities. First/middle/last annotations inspected. Last-frame center mean/max
error 3.87/6.19 native pixels against coarse manual references (~3-px uncertainty).
The current fitter measures each cell's borders and reads its content; it no
longer assigns the old fixed Level label order. Current Level button geometry
bypasses the old bad-anchor stabilizer; no blanket claim of zero jitter.

- Pre-Step 1 recorded live-path replay: regular/selective 0.72/0.77 processed FPS with full
  annotations/debug/export; some result ages exceed the unchanged 1.5-s expiry.
  OCR per control/retries is a measured cost lead. Source/network throughput is
  not measured by that replay. Improve cost before claiming responsive action use.
- Static Level evidence is validated; changed values, natural transitions, new
  framing/occlusion and fresh deployment remain unverified. No physical mm proof.
- Step 3 accepts SENSE localization on the five recordings with the two page-1
  failures above. Step 4 now accepts the recorded Train Data view with the limits
  in its milestone; numbered-page semantics are accepted above with their limits;
  validation remains Step 7. Geometry
  success does not establish semantic coverage. Earlier cold checks finding
  unknown/zero controls on all four train sources describe the pre-Step 3 baseline.
- The reproduced Main->Driver geometry transition failure is corrected by generic
  basis invalidation in Step 3 and is an ordinary passing regression. Legacy
  unsupported-cell/numeric/Close findings still need reproduction where relevant.
- Current suite results and durable evidence are recorded in the accepted
  milestones above. New ignored tests/evidence remain local under the requested
  policy; a clean clone cannot reproduce the full checks unaided.

## Calibration and hardware blockers

- New intended reference: `TapperWare_Flet/DmiPositions.json`, model
  `DMI_SENSE_TOUCHSCREEN`. It contains Driver ID digits/Delete/confirmation, some
  Level/Main/Train Data/TRN/ACK controls, not full numbered-page/validation mappings.
  Match semantics explicitly; review ambiguous Yes/confirmation aliases.
- New Driver ID reference is `DRIVER_ID_SCREEN`, e.g. KEY_1=[200,364], KEY_2=[165,364],
  KEY_3=[135,364], model default 100 ms. Old master reference is DRIVER_ID_WINDOW,
  KEY_1=[100,300], different spacing/axis direction, default 200 ms. Do not mix them.
- Existing calibration code defaults to the old file and ten digit identities;
  CLI accepts simulation replay only. Validation/target conversion/action checks
  restrict the right Driver ID keypad/hull. Replacing a JSON path does not enable
  all screens. Fit/coverage/context/schema and direct-support logic need deliberate
  compatible extension, with SENSE isolated from future TWIN calibration.
- Reuse planar homography; compare simpler affine fit against independent mm error.
  Need actual matched points distributed across the plane, held-out validation,
  reference/origin/panel/tool conventions and a measured acceptance tolerance.
  Do not apply the GUI Y offset again if already included in calibrated absolute XY.
- No guided installed-camera commissioning mode exists yet. Implement an explicit
  operator-confirmed move-only measurement workflow for unverified current-camera
  fits, without enabling normal presses or relabeling simulation as verified.
- Review homing, measured limits, Z retraction/contact and physical stop first.
  Known slave concerns include contact success reporting and Z step accounting.
  Position feedback is internally calculated, not independent alignment evidence.
  GUI stop cannot interrupt blocking motor code. No automatic retries/parking after
  uncertain failures; DONE alone is not successful UI input.

## Next approvals and delivery rules

Steps 1–6 plus SENSE optimization are accepted with the limits above and approved
for commit/push. Detection speed remains an open limitation despite acceptance
for now. Steps 7–16 and further performance work need separate authorization.
Continue one requested step at a time; do not infer next-step permission from
acceptance or reviewer verdicts. Do not accumulate old reports.

Ignore policy excludes local tests, media/results, caches/logs, operator settings,
local deployment data and the legacy general copy. TapperWare source/reference/
requirements and useful example XML are now eligible for version control; they
were previously entirely ignored and still require deliberate staging/review.
Ignored tests stay locally available; already tracked tests are not untracked.
The roadmap rewrite itself deleted/moved no source files and changed no runtime;
the separately accepted activity update above extends detection/output/action guards.
No camera/UDP/motor calls were performed.
Documentation paths, all 16 step numbers and representative ignore rules checked;
152 runtime/support files remain hash-identical. `git diff --check` passes.
