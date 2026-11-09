# SENSE DMI Version 1 / Version 2 improvement workflow

## Goal and scope

Improve upper SENSE Driver ID / Level recognition under lighting variation,
reduce repeated full-screen detection and OCR, stabilize measured screen geometry
and pixel centers, and validate reusable monitor-plane pixel-to-robot mapping.
Provide an operator-selected Version 1 / Version 2 comparison in the existing
TapperWare Flet GUI so hardware tests can measure whether improvements help.
Keep implementation small, readable and measurable.

Follow `PLAN.md` for the detailed improvement phases, technical decisions, test
matrix and exit criteria. The roadmap below replaces the previous numbered
implementation roadmap; completed work remains historical in `STATE.md` and must
not be restarted. Read `STATE.md` for accepted scope, limitations and approvals,
then verify current HEAD and code rather than assuming the handoff describes it.
Read `TEST_FEEDBACK.md` for operator feedback; deferred issues stay deferred unless
explicitly authorized. This document and `PLAN.md` are instructions, not permission
to implement every phase, accept work, update acceptance records or publish.
If PLAN.md conflicts with these working rules or accepted runtime contracts,
preserve the contract and report the conflict before proceeding.

- SENSE: upper connected monitor, camera 1, one physical screen with two logical regions.
- TWIN/TWINS: lower separated displays, camera 0; existing detections are accepted
  by the user and are a frozen regression baseline. Detection updates target SENSE
  only. Do not modify TWIN detection code, tuning, pipeline behavior or outputs.
- Camera index selects acquisition only; image evidence determines geometry/state.
- Work on one selected camera per session. SENSE calibration must never be applied
  to TWIN; physical TWIN calibration is deferred.
- Train workflow meanings/order match TWIN, but recognition must also work when
  starting directly on any supported screen. Never require a preceding screen.
- No new backend service, autonomous screen navigation, GUI redesign or motor rewrite.

Reuse the accepted TWIN implementation as-is. Shared files may receive SENSE-only
changes, but common behavior used by TWIN must remain unchanged; use existing
image-evidenced geometry/state handling, not camera-index rules or a second pipeline.
TWIN recordings are reference/regression evidence only, not a new tuning task.
If a proposed SENSE fix requires changing TWIN behavior, report the conflict before
proceeding. Acceptance of TWIN detection does not imply physical calibration or
pressing validation; existing documented limitations remain historical facts.

## Read and reuse

Before edits, inspect Git status/diffs, this file, `STATE.md`, `PLAN.md`,
`TEST_FEEDBACK.md` and the owning code.
Preserve unrelated edits. Do not assume that a historical report describes HEAD.
Read local vision `docs/UI_SPEC.md`, `OUTPUT_SPEC.md` and relevant workflow guidance
when available; they are references, not runtime dependencies. Do not restore
removed guidance files or duplicate root handoff history into other documents.

Responsibilities:

- `dmi_computer_vision/src/dmi/`: localization, shared analyzers/OCR, tracking,
  annotations and compact logs. Reuse `FrameProcessor`, `process_live`, `LatestState`.
- `dmi_robot_master/integration/`: camera bridge/adapters, observation, calibration,
  target publication and validated label actions. Reuse existing math/transport.
- `TapperWare_Flet/`: intended GUI; `dmi_gui.py` owns controls, `dmi_runtime.py`
  owns execution/worker lifecycle, settings/photos/activity modules own their features.
- `TapperWare_Flet/DmiPositions.json`: intended SENSE reference for this roadmap.
- `dmi_robot_common/`: shared UDP protocol/config/logging and command validation.
- `dmi_robot_rasp/`: receiver, GPIO, motion and sensors; keep hardware imports off PC paths.
- `dmi_robot_config/`: shared deployment configuration; local overrides/calibrations
  belong in ignored `dmi_robot_config/local/` and must survive temporary-output cleanup.
- `dmi_robot_master/` outside integration: existing controller, legacy GUI/XML assets
  and the old keypad-only reference. Preserve compatibility until explicitly migrated.
- `dmi_robot_general/`: local legacy reference copy, not a second integration backend.
- `runs/`, vision data/outputs and test directories: local development/evidence,
  not runtime dependencies or presentation material. Keep sources read-only.

The root README is currently a GitLab template. Runtime truth comes from code,
current evidence and the integration README, not that template.

## Working rules and approval

Implement only the requested step. If it is too large, split it into smaller
reviewable changes before proceeding. A request to add or amend a future step is
documentation-only unless runtime implementation is explicitly requested. At each step:

1. Reproduce the specific failure and establish a small representative baseline.
2. Make the smallest SENSE-scoped change; verify accuracy, failure handling and cost
   while leaving the accepted TWIN path unchanged.
3. Complete the automatic two-reviewer cycle below, then give a short report
   **in chat**: change, checks/results, both reviewer verdicts, remaining limits
   and the proposed next step. Show useful annotations with source paths.
4. Wait for the user's review/approval. Do not create a per-step REPORT/REVIEW
   Markdown file or another handoff document. Until approval, the working diff
   and chat are pending work; do not mark the step accepted in `STATE.md`.
5. After explicit approval, update `STATE.md` with the accepted step and concise
   results. Commit/push only if that approval also authorizes publication. Stage
   only reviewed changes; report commit ID/destination and actual push result.
   Never force-push, silently include local files or infer publication approval.

For each authorized improvement phase, the main agent owns software implementation,
offline validation and clear hardware operating instructions. Physical hardware
validation is performed later by the user.

Do not block completion of an offline implementation solely because hardware is unavailable, but explicitly distinguish implemented, simulated, unverified and physically validated functionality.

Do not bypass calibration, freshness or robot safety requirements to make an offline test pass. Report any hardware-dependent acceptance criteria as pending until independently verified.

### Automatic implementation and review cycle

For each user-authorized implementation step, the main agent owns implementation
and corrections, and must automatically request both configured reviewers:

- `code_review`: correctness, regressions, performance, maintainability and tests.
- `step_checker`: authorized scope, acceptance criteria, evidence and plan compliance.

Use `.codex/agents/code_review.toml` and `step_checker.toml` for their duties.
The workflow delivery must include those two files and `.codex/config.toml`
alongside this guidance; do not publish instructions that depend on omitted local
agent definitions. Include only reviewed configuration, not unrelated local files. Because this
guidance depends on `PLAN.md`, any later authorized publication must also include
the reviewed `PLAN.md`; do not publish instructions whose required roadmap is
missing from the destination. This requirement does not authorize staging or
publishing either file now.
The user authorizes this delegation for requested steps; do not ask permission
again for each reviewer invocation or ordinary in-scope correction. This workflow
does not authorize starting an unrequested step or implementing a plan-only edit.

1. Implement the current step and run its relevant checks. Define the exact
   review scope: step/criteria, changed files, diff/base revision and evidence paths.
   Prepare the single review package described below; do not ask the user to
   choose between intermediate attempts or several folders named final.
2. Freeze edits while both agents independently review the same working version.
   They may review in parallel; neither edits files, opens live hardware connections,
   sends actions, creates report files, commits or pushes. Findings return in chat.
3. The main agent examines each finding against evidence. Fix confirmed defects
   and unmet in-scope requirements, rerun affected checks and request re-review.
   Do not apply speculative suggestions blindly or expand into another step.
   Resolve reviewer disagreements with evidence and disclose any unresolved issue.
4. Repeat until both reviewers assess the final version with no unresolved
   blocking defects or mandatory criteria missing/unverified. After corrections,
   both reviewers must confirm the final version, not an earlier diff. A PASS WITH
   WARNINGS can be ready only when its remaining warnings are nonblocking and
   explicitly disclosed; a FAIL or NOT VERIFIED is not ready for acceptance.
5. If required evidence, a decision or an unavailable reviewer prevents completion,
   report the specific blocker to the user. Do not invent a second review, conceal
   a failure, repeat fruitless loops, or weaken requirements to obtain a PASS.
   Continue independent authorized work where possible; deferred hardware evidence
   blocks only acceptance criteria that actually require it.
6. Present one short consolidated report to the user. Include the final review
   verdicts and checks, meaningful fixes, limits and an explicit approval request.
   Link the one review folder and the exact preview/video to inspect, and identify
   the source version it demonstrates. Both reviewers must check output discipline
   and package/version consistency before declaring the step ready.
   Subagent approval is advisory; only the user accepts work and authorizes publication.

Keep three permissions distinct: accepting the current step, committing/pushing
it, and starting the next named step. A single explicit user reply may authorize
all three. If it does, update `STATE.md`, commit/push only the reviewed files,
verify/report the push, then start the named next step and repeat this cycle.
If publication fails, report it and resolve it before advancing. If the user
requests changes or declines, stay on the current step. Never infer next-step
authorization from a reviewer PASS or from approval limited to the current step.

Use the current session's delegation tools; do not build a scheduler, background
agent service, new protocol or extra report directory for this workflow. If an
agent is unavailable, disclose it rather than silently replacing its independent
review with a self-review. Do not launch another top-level Codex process.

### Output discipline and one clear review package

Temporary debugging can require many artifacts; the user-facing handoff must stay
small and unambiguous. This policy applies to future work, not retroactive removal
or rejection of previously accepted evidence.

- Keep original recordings, receipt sidecars, reference measurements and accepted
  evidence immutable in their existing locations. Reference them by path/hash;
  do not duplicate raw videos or production source trees in every experiment.
- Use one task-owned scratch root, normally `/tmp/dmi_robot/stepNN_NAME/`, for
  profiling dumps, retries, before/after exports, debug crops, temporary scripts
  and candidate outputs. Generate only what answers a specific open question.
  Do not automatically save a PNG per frame/control/test or encode every replay.
- Reuse the same evidence in both reviews. Reviewers inspect existing outputs
  first; additional checks write only to task-owned temporary scratch space.
  They do not create separate review/review2/final_verified output collections.
- Before requesting approval, select one canonical review folder, for example
  `runs/step05_train_data_1_2/`. Keep intermediate attempts outside that folder.
  It contains only the final candidate's useful machine evidence, normally:
  compact results JSONL; one existing session/summary JSON containing the source
  paths, reviewed source version/hash, checks and measurements; optionally one
  annotated video; and at most three representative PNGs. A contact sheet may
  replace multiple screenshots. A docs-only change needs no generated package.
- These are defaults, not a reason to discard required evidence. Retain necessary
  receipt/status/calibration/action logs or additional failure examples when a
  specific acceptance criterion requires them. Explain the exception and file
  purpose in chat; avoid redundant summaries/manifests and duplicate debug logs.
  Preserve runtime consumer contracts; do not change output schemas to meet a count.
- Freeze the candidate and its review package together. If a fix changes outputs,
  regenerate the affected evidence in scratch and refresh only this task's
  unapproved generated review package before both final reviews. Never replace
  source files or an approved package. Identify the new version in chat, and do
  not leave obsolete candidates beside it with ambiguous final/latest names.
- The main agent owns curation. Both reviewers must flag unexplained artifact
  proliferation, duplicate final candidates, stale previews or missing version
  links as readiness issues. Neither a long test run nor a PASS excuses a handoff
  that leaves the user guessing which output to approve. Resolve these issues
  within the current step before presenting it for acceptance.
- Reports stay in chat; create no README/REPORT/REVIEW Markdown file in the
  output folder. After approval, STATE.md points to the one accepted evidence
  package, with concise results. No per-attempt handoff/report files.
- Disposable scratch created by the current task may be discarded once needed
  evidence is safely retained. This is not permission to delete existing runs,
  another task's scratch, approved evidence or the only copy of any source,
  reference, calibration or reproduction data. Existing-folder cleanup needs a
  separately reviewed retention/deletion list and explicit user authorization.

Keep `STATE.md` short: one current status, baseline, evidence map, open issues,
next step and compact accepted milestones. Preserve the difference between code
implemented offline, recorded-camera validation and actual physical validation.
Documentation-only roadmap changes do not accept implementation work or authorize
changes to acceptance records in `STATE.md`. Do not rewrite history to hide failures.

## Detection and performance requirements

Use the same core detector for SENSE/TWIN. Detect monitor boundaries and their
logical division before interpreting screen controls. A keypad, menu, field or
known title must not be mandatory for finding the same physical monitor. Reuse
compatible measured geometry only with bounded rechecks and explicit invalidation
on movement, perspective/size/source changes, ambiguity, occlusion and recovery.
Retain independently validated regions; never fabricate their missing partner.

Use layout proportions only to propose searches. Measure current borders/content;
never copy sample coordinates, add screenshot matching, draw a synthetic separator,
assign controls from fixed slot order or infer a missing border. Known vocabulary
is allowed; unreadable/ambiguous/duplicate identities and unsupported cells are
omitted. Do not use the robot coordinate database to invent image detections.

Maintain current output identities/schema and original input-pixel centers, even
when analyzing resized/rectified images. Preserve left/right workflow semantics:
train summary/title/confirmation can replace the speedometer/22-box view. Refer
to accepted separated results for expected fields/labels/annotations, not position
truth. Distinguish visible, recognized, enabled, calibrated and actionable controls.

Keep acquisition, detection, preview and actions separate. Consume the latest
frame with bounded buffering. Profile geometry, analyzers, OCR and output before
optimizing. Compare equal clips, timing, options and environment; report mean/P95
analysis time, OCR calls/time, processed FPS, overwrites/skips and result age.
Capture FPS, bridge publication FPS and MP4 playback FPS are not detection FPS.

Avoid unnecessary OCR retries and encoding. Any reuse must have bounded refresh
and invalidate on changed cell/title pixels, source/geometry/state changes,
occlusion/loss/recovery. A stable title must not hide changed fields/buttons.
Reused values/coordinates cannot renew direct-evidence age or confirmation counts.
Keep regular mode for diagnosis; compare selective mode on real transitions.
Preserve 4-pixel per-coordinate publication tolerance (publish only when >4 from
last published baseline), semantic/loss invalidation, heartbeat and evidence expiry.
Do not relax OCR, freshness, confirmation or calibration limits to improve metrics.
Do not promise a detection FPS without measured evidence.

## Evidence to use

User-confirmed SENSE sources, reviewed 2026-10-22:

- Level: `runs/level_raw_01/raw.mp4`, 53 frames at 2304x1728.
- Train Data: `runs/observation_08/annotated.mp4`, 61 frames; Gamma/Lambda view.
- Train Data (1/2): `runs/observation_09/annotated.mp4`, 86 frames; numeric entry.
- Train Data (2/2): `runs/level_raw_02/raw.mp4`, 69 frames; loading-gauge selection.
- Validate Train Data: `runs/level_raw_03/raw.mp4`, 25 frames; summary/Yes/No view.

Names are not detector inputs: the two later `level_raw_*` clips are train screens.
Observation 08/09 are the user's supplied camera recordings, but their saved files
contain an upper-left HUD. Exclude overlay pixels from measurement; use unaffected
monitor pixels and record any overlap. Continue with these inputs; obtain genuinely
unannotated replacements only where overlays prevent trustworthy measurement.
Read first/middle/last frames and sidecars. Use receipt times for replay evaluation;
5-FPS encoding is not capture cadence. Preserve original video FPS and resolution
for full-video validation; reduced-FPS clips are only for focused tests, not
evidence of real-time performance. Test variants/held-out recordings separately
from samples used for tuning. Never overwrite source or accepted output files.

Keep `dmi_computer_vision/data/videos/dev/dmi_capture_quality_01` through `_04`
(Main/Driver ID), original separated videos and existing frozen examples as
regressions. Old output annotations are not ground truth. Local evidence absence
is an explicit coverage gap, not permission to claim support or block unrelated work.

## Improvement roadmap — one authorized phase at a time

Use the PLAN phase numbers below when naming work, approvals and evidence. The
additional version-selector phase follows Phase 0 and precedes Phase 1. This avoids
confusing the new phases with historical accepted step numbers in `STATE.md`.
`PLAN.md` sections 3–6 supply the detailed requirements and review gates; follow
its phase-specific tests and exit criteria as well as the rules in this file.

### Phase 0 — Establish the Version 1 baseline (PLAN Phase 0 / G0)

Verify HEAD, working tree, environment, source hashes and camera conventions.
Freeze the exact existing behavior/source fingerprint as Version 1, preserving
unrelated work and recording known failures rather than treating them as successes.
Reproduce grey-field failures and Level dropouts from available real SENSE evidence.
Measure accuracy, false positives, center/corner jitter, OCR cost, processing time,
freshness and overwrites on matched inputs. Separate independent reference points
from predictions and tuning samples from held-out evidence. No runtime detector
change; unavailable office footage or measurements remain explicit gaps.

### Phase V — Add the GUI Version 1 / Version 2 selector (new step)

Add one clearly labeled selector to the existing GUI before implementing Phase 1.
Version 1 preserves the Phase 0 behavior and functionality, including documented
limitations. Version 2 enables only the improvements implemented and reviewed so
far; selecting it does not mean the whole roadmap is implemented or accepted.
Initially both modes use the baseline behavior. Default to Version 1 on launch.

Allow switching only with observation stopped and no robot action or other
execution running. Clear prior observations, locks, selections and pending action
confirmations; require explicit observation restart. Revalidate source, origin and
calibration context, invalidating incompatible mappings. Switching versions must
not change calibration verification flags or grant physical-action authorization.

Keep one camera owner, one latest-frame slot and one active processing path. Reuse
existing components with narrowly scoped version choices; do not duplicate the
application, detector source tree or backend. Keep Version 2 SENSE-only; TWIN
retains its accepted behavior in both modes. Preserve existing GUI features and
robot safety checks in both versions. This selector is the only planned GUI
addition beyond the small observation/action wiring described in PLAN.md.

Record selected version, source fingerprint, enabled improvements and relevant
settings in comparison evidence using existing diagnostics where possible; do not
unnecessarily change public output schemas. Verify selector/default behavior,
busy/live-switch rejection, clean restart, absence of cross-version cached evidence,
and Version 1 equality against the frozen baseline using offline/fake hardware.
Explain the operator procedure for repeating the same hardware test in each mode.
No hardware action is authorized by this documentation or by selecting a version.

### Phase 1 — Lighting-robust localization (PLAN Phase 1 / G1)

Preserve successful primary field detection and OCR. Add a conservative SENSE-only
fallback based on current measured contrast and borders, rejecting competing or
unsupported rectangles. Improve control borders only for reproduced failures.
Validate held-out lighting variants, negatives, accuracy and bounded overhead;
Version 1 and frozen TWIN outputs must remain unchanged.

### Phase 2 — Screen acquisition and locking (PLAN Phase 2 / G2)

Introduce cohesive session-owned Driver ID / Level profiles and bounded multi-frame
acquisition: at least three consistent full observations in a window of at most
five. Lock measured geometry and median original-pixel centers without inventing
missing controls. Keep static cached layout separate from dynamic state and fresh
action evidence. Invalidate on context, source, geometry, screen, calibration or
origin changes and uncertainty. Other screens retain full detection until separately
profiled and validated; bypass the SENSE lock for TWIN.

### Phase 3 — Selective screen and dynamic-state updates (PLAN Phase 3 / G3)

Use cheap bounded checks of current title, field, geometry, button/activity and
mode-icon regions. Run existing targeted OCR/recognition when required; same-title
field/activity/icon changes must still be detected. Preserve blink history and
manual-change detection. Reacquire on unknown transitions or invalid geometry;
retain bounded structural audits. Keep lock state independent of FrameProcessor's
processed-frame gap resets. Measure full-call reduction and actual latency/cost,
not just preview or acquisition FPS.

### Phase 4 — Stable original-pixel coordinates (PLAN Phase 4 / G4)

Keep measured median centers fixed within a verified lock generation; compare
changes to its original baseline and never accumulate drift. Clearly distinguish
cached display coordinates from current evidence. Preserve raw calibration/action
precision and the GUI's independent display-only deadband. Suggested ±10 X / ±5 Y
pixel tolerances are hypotheses, not adopted action rules; any change needs measured
pixel-to-mm uncertainty, negative tests and explicit approval.

### Phase 5 — Stable SENSE monitor-plane mapping (PLAN Phase 5 / G5)

Reuse existing calibration math and saved provenance. Establish one robust session
registration from consistent measured monitor geometry, then check continued
alignment rather than recomputing a noisy transform per frame. Invalidate on real
movement or incompatible context. Compare independent spread-out physical holdouts
across screens/regions; normal acceptance still requires maximum held-out error
≤3 mm and verified coverage. Keypad coverage does not authorize the whole monitor.
Keep rejected/experimental models truthfully qualified; no database edits, new
motor offsets or physical commands in this phase.

### Phase 6 — Minimal guarded action integration (PLAN Phase 6 / G6)

Requires explicit authorization distinct from read-only locking and projection.
A locked cache cannot authorize actions. Retain on-demand full detection until a
fresh, independent target-ROI verifier is implemented, validated and approved.
Preserve current identity/activity/source/geometry checks, 1.5 s evidence expiry,
4 px evidence agreement, calibration/origin/readiness/bounds checks, single action
ownership, no queue and no automatic retries. A completed-action notification
predicts what to inspect; it never proves contact or a UI transition. Grey fields
remain visually observed fields; adding physical field pressing requires separate
explicit review and authorization.

### Phase 7 — Matched comparison and evaluation (PLAN Phase 7 / G7)

Compare frozen Version 1 with implemented Version 2 on equal sources, options and
environment. Also evaluate PLAN.md's staged modes A–D where implemented and
separately approved. Report recognition accuracy, false retention, transitions,
geometry/jitter, OCR/full-call cost, mean/P95 latency, freshness, skips/overwrites
and independent mm errors. Check failure/recovery, stale caches, source changes,
manual interactions, same-title changes, blinking and rejected calibration.
Recheck existing SENSE coverage and frozen TWIN outputs. Explain the GUI hardware
comparison procedure; physical results remain pending until supplied by the user.

## Accepted contracts to preserve throughout the roadmap

- Preserve Level center-only compact button entries, parallel `button_activity`,
  rich/target `active` true/false/null and green/gray/amber status annotations.
  Activity comes from current glyph evidence, adds no OCR, clears on loss and
  changes independently of coordinate jitter. Inactive/uncertain is not actionable.
- Preserve accepted train-state identities and region semantics. Numbered Train
  Data pages and Validate Train Data retain titles/buttons-only scope: no left
  summary or noninteractive row/value OCR. Validation's measured gray Yes/No
  field remains the explicit exception, separate from lower Yes/No/Close buttons.
  Preserve Train Data Gamma/Lambda summary/field support and TWIN behavior.
- Use only `TapperWare_Flet/DmiPositions.json -> DMI_SENSE_TOUCHSCREEN` for the
  intended SENSE reference. Match model/screen/region/kind/label explicitly;
  never substitute the legacy DRIVER_ID_WINDOW database for DRIVER_ID_SCREEN,
  infer aliases from order, or use references to invent detections. Missing and
  ambiguous mappings remain unusable. Apply panel/tool offsets in one place.
- Reuse existing calibration fits, validation and transport. Use distributed
  non-collinear correspondences and whole-control/location holdouts; repeated
  frames of one point do not add independent coverage. Compare affine/homography,
  report outliers/errors and reject contradictions. Save provenance, conventions,
  coverage and verification status in durable ignored local calibration storage.
- Calibration loading/inspection is distinct from action authorization. No ordinary
  recorded fit is to be treated as accepted merely because an experimental press
  was reported successful. Preserve existing narrowly authorized experimental
  scope from STATE.md in full, including detected buttons in both measured SENSE
  regions under its existing guards. Do not narrow that authorization to the
  user-tested keys or extend it beyond the already authorized scope. Fields, icons,
  TWIN and any other extension require their own evidence and explicit approval.
- Reuse existing box_14 white / box_16 yellow icon templates and ModeHistory.
  Blink-off is not disappearance or acknowledgement. Physical hold/contact success
  requires its own authorization and validation; command completion is insufficient.
- Keep detailed per-frame JSONL optional for diagnostics; use bounded in-memory
  state for GUI communication. Do not create another pipeline or continuously
  transfer full per-frame JSON as the runtime communication mechanism.
- Keep legacy XML/photo behavior compatible and separately guarded. No motor,
  GPIO or UDP protocol rewrite, automatic screen navigation, automatic retry or
  unsupported safety claim. Missing hardware blocks only criteria requiring it.

### Complete when

Measured Version 1 / Version 2 comparisons demonstrate improved supported SENSE
recognition, cost and stability without stale action evidence, fabricated geometry,
TWIN regressions or weakened safety/calibration gates. Independent physical accuracy
and hardware results must be reported separately; stable annotations or offline
tests alone do not establish physical success. Unverified criteria remain explicit.

## Code, output and validation standards

- Small explicit functions/classes; normal formatting, useful names, units and
  interface type hints. Split by responsibility, never arbitrary file length.
- No duplicate pipelines, broad refactors, wildcard imports, hidden fallback
  coordinates or a framework/new dependency without measured need.
- Keep acquisition, image analysis, calibration, target state and actions distinct.
  Use one consistent import strategy and paths relative to owning files/config.
- Give cameras, threads/workers, sockets and GPIO explicit owners and cleanup.
  Avoid dynamic cross-package imports where an explicit adapter suffices.
- Test meaningful behavior and failures with fake hardware. Keep tests locally
  even though the user requests test folders excluded from new commits. Already
  tracked tests remain tracked; do not untrack them without specific approval.
  Report that ignored new tests/raw data are unavailable in a clean clone unless
  separately supplied. Ship no runtime dependency on such development files.
- Run relevant tests after runtime changes; full suites for shared detector,
  calibration/transport or final integration changes. For docs/ignore-only edits,
  check references, Git diff and ignore behavior rather than rerunning hardware.
- Use one task-owned scratch root and one canonical review package as specified
  above. Never overwrite sources or approved evidence; refresh only task-owned,
  unapproved generated review artifacts after a candidate change. Full debug/video/
  history is optional; compact machine action logs and required runtime outputs are allowed.
  Do not add new Markdown reports. Copy selected useful evidence to durable local
  storage before `/tmp` cleanup; never store the only calibration there.
- HTTP frames and UDP commands share Ethernet; they remain separate protocols.
  Keep real network/device settings configurable, never infer final values.
- Claim only what measured evidence supports. Offline success is not physical
  pressing validation, and one supported state is not all-screen robustness.
