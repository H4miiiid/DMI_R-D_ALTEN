# SENSE DMI vision, calibration and robot integration

## Objective and scope

Improve the upper SENSE monitor detector, validate pixel-to-robot millimeter
conversion, then integrate live vision and operator-controlled actions into the
existing TapperWare Flet GUI. Keep implementation small, readable and measurable.

This is the new roadmap, replacing the earlier numbered integration plan. Those
phases remain historical accepted work; do not restart them. Read `STATE.md` for
the actual baseline, approvals, limitations and next authorized step. This document
is a plan, not authorization to implement every step in one session.

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

Before edits, inspect Git status/diffs, this file, `STATE.md` and the owning code.
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

### Automatic implementation and review cycle

For each user-authorized implementation step, the main agent owns implementation
and corrections, and must automatically request both configured reviewers:

- `code_review`: correctness, regressions, performance, maintainability and tests.
- `step_checker`: authorized scope, acceptance criteria, evidence and plan compliance.

Use `.codex/agents/code_review.toml` and `step_checker.toml` for their duties.
The workflow delivery must include those two files and `.codex/config.toml`
alongside this guidance; do not publish instructions that depend on omitted local
agent definitions. Include only reviewed configuration, not unrelated local files.
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
This requested documentation rewrite may record the baseline now; it does not
accept any future implementation step. Do not rewrite history to hide failures.

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
5-FPS encoding is not capture cadence. Test variants/held-out recordings separately
from samples used for tuning. Never overwrite source or accepted output files.

Keep `dmi_computer_vision/data/videos/dev/dmi_capture_quality_01` through `_04`
(Main/Driver ID), original separated videos and existing frozen examples as
regressions. Old output annotations are not ground truth. Local evidence absence
is an explicit coverage gap, not permission to claim support or block unrelated work.

## Small implementation steps

### 1. Refine Level accuracy on SENSE

Recheck the current measured-cell implementation on raw Level evidence. Inspect
weak/disabled-looking text, TBL1+, individual outline gaps, Close/More and native
centers. Omit uncertain controls. Measure center/border error and jitter against
independent reviewed examples. Exercise direct startup, loss/recovery and changed
values; obtain missing real variants when needed. Preserve TWIN corrections.
User-confirmed SENSE Level view: Level 0/1/2, KVB, X (`close`) and ... (`more`)
are active; Level 3, MEMOR, ATC-2 (`atc_2`, user wrote ACT-2), SCMT and TBL1+
are inactive. Keep detected inactive controls visible/exported with their centers.
Report `active: true/false/null` per Level button from current glyph appearance;
null means uncertain. This list is validation evidence for this view, not a fixed
label-to-activity rule or a rule for TWIN. Preserve center-only compact button
entries and add a parallel `button_activity` map in JSONL; include `active` in
rich results and robot target JSON. Activity changes bypass pixel jitter tolerance.
Annotate active green, inactive gray, uncertain amber, with status text. Inactive
or uncertain activity must not become actionable just because calibration is valid;
active alone does not establish freshness, calibration, hardware readiness or
successful contact. Do not add OCR work or retain activity after target loss.
Done when remaining defects and supported conditions are explicit and reviewed;
do not replace the already working correction without reproducing a defect.

### 2. Reduce Level processing cost

Profile the Step 1 baseline, then reduce redundant OCR/warps/searches with small
shared changes. Preserve exact-label requirements and current-image border checks.
Compare accuracy and age under regular/selective policies, including same-title
changes and loss/recovery. Demonstrate cost reduction without stale results.
Some existing Level results exceed the evidence lifetime: solve processing cost,
not by extending expiry. Report any jitter/recognition tradeoff.

### 3. Make SENSE localization independent of screen layout

Review `display_geometry.py` using all five sources. Remove the dependency on
Driver ID's field/keypad or Main's menu as mandatory split evidence. Fit persistent
outer/internal structure with conservative image validation, not a fixed midpoint.
Check left train titles/summaries and right controls after rectification. Address
incompatible geometry-history reuse and re-anchoring generically; no hardcoded
transition pairs. Preserve Main/Driver/Level and separated regression behavior.

### 4. Support Train Data on SENSE

Use observation_08 and separated Train Data examples. Recognize left title/summary
and completion Yes, right train-type field and Gamma/Lambda, Close/Enter data and
other controls only where actually visible. Preserve existing identities; navigation
appearance alone does not prove enabled state. Validate positions, text, direct
startup and cost separately; no screen-order shortcut.

### 5. Support Train Data (1/2) on SENSE

Scope for Steps 5–7: detect and annotate only visible screen titles and buttons
in both logical regions, with existing identities and original-pixel centers.
Keep monitor/region localization; omit left summaries and noninteractive right
information text, row labels, field values and confirmation text from OCR,
annotations and optional exports for these three SENSE states. Clear omitted
optional information instead of retaining cached text; preserve output schemas.
Button labels, including numbers and selector choices, still require current image
evidence. Preserve accepted Step 4 and TWIN behavior; this is not a global removal
of summary/field support. Profile the reduced work on equal clips and measure
accuracy, OCR cost, latency and freshness; do not assume a speed gain in advance.

Use observation_09 and separated page-1 examples. Recognize the visible Train
Data (1/2) title, left completion Yes where present, and measured right keypad,
Delete/decimal and navigation/action buttons. Max speed, Train category, Length,
Brake percentage and the selected-field value are outside this step's scope.
Do not fabricate a whole keypad from one detected line. Check exact button labels,
centers, direct startup, same-title button/layout changes and loss/recovery;
recognition must not depend on reading the summary or selected value.

### 6. Support Train Data (2/2) on SENSE

Apply the titles/buttons-only scope above. Use level_raw_02 and separated page-2
examples. Recognize the visible Train Data (2/2) title, left completion Yes where
present, and measured right selector buttons G1, GA, GB, GC, Out of GC plus visible
navigation/actions. Exclude Loading gauge, Axle load category and Airtight
information rows/values; these are distinct from the selectable buttons.
The footage demonstrates loading-gauge selection only; other button layouts need
evidence before claiming coverage. Reuse page/navigation helpers without assuming
every mode has that grid. Test direct startup, changed button layouts, exact labels,
centers and loss/recovery without summary/value OCR or screen-order assumptions.

### 7. Support Validate Train Data on SENSE

Apply the titles/buttons-only scope above. Use level_raw_03 and separated validation
examples. Recognize the visible Validate Train Data title and measured Yes/No/Close
buttons, retaining their existing region-qualified identities. Exclude the left
summary and right confirmation field/text. Verify the left completion button is
absent when not visible; never invent a second Yes. Test direct startup, changed
button appearance/layout and loss/recovery without reading confirmation content
or requiring the previous page. Recognition or an exported Yes is not a press,
proof of enabled state or confirmation that the robot changed the DMI.

### 8. Validate SENSE workflow and preserve TWIN

Run representative cold/steady frames and real transitions across supported
screens; separately measure geometry, identity, in-scope values, centers and delay.
For Steps 5–7, validate titles/buttons only under the scope above. Turn
fixed known failures into ordinary passing tests only when actually corrected.
Check preview/compact logs/targets, occlusion, source failure and camera/session
switches. Recheck accepted TWIN states for regressions only; do not modify or retune
their detector. Any new TWIN difference from the baseline must be resolved in the
SENSE change, not accepted as an intentional TWIN improvement. Existing documented
TWIN limitations do not become new implementation work. Main/Driver ID remain
required regressions; Train Running Number remains unverified on SENSE until
representative evidence is checked. Approve detection coverage and latency before
calibration work.

### 9. Audit SENSE reference coordinates and identities

Use only `TapperWare_Flet/DmiPositions.json -> DMI_SENSE_TOUCHSCREEN`. The old
master database uses `DRIVER_ID_WINDOW`; this one uses `DRIVER_ID_SCREEN`, different
positions, spacing, axis conventions and default press duration. Do not swap paths
and assume compatibility. Match `(model, screen, detector label)` explicitly to
reference buttons, starting with digit_n/KEY_n and unambiguous Level controls.
Review confirmation/Yes/end-entry aliases with the user; never match by order or
`leads_to` alone. The database is sparse: it lacks complete per-control mappings
for the numbered train pages/validation. List missing/ambiguous points and verify
units, origin, panel offsets and actual tool alignment before treating them as truth.
Apply a panel/tool offset in one defined place; do not add the GUI Y offset again
when the calibration already produces absolute coordinates in that convention.

### 10. Fit and export SENSE pixel-to-mm calibration offline

Reuse homography math/validation. Fit current original-image pixels to verified
absolute robot XY; compare an affine fit if it achieves comparable independent
error, keeping the simplest adequate model. Do not use a universal pixel/mm ratio.
For a planar screen, use spatially distributed correspondences and held-out keys,
entire controls/locations or screens, not repeated frames of the same point.
At least four non-collinear matches are needed for a homography; use at least
five for leave-one-out checks, preferably all reliable digits plus wider controls.
Repeated references at the same physical location do not add independent coverage.
Report per-point/mean/max mm error, outliers and validated coverage; reject
collinear/contradictory points. Do not force a fit through inconsistent references.

Extend the existing keypad-only model/projector/action validation deliberately;
changing a reference path alone does not enable other screens or the left region.
One SENSE transform can serve coplanar UI states only after coverage is validated.
Convert other detected centers for inspection where mathematically valid, but mark
out-of-coverage/uncertain mm unusable. Add measured spread-out references where
needed; do not authorize the whole monitor from the keypad hull. Separate physical
planes require separate fits. Save model/matrix, reference hash/label map, camera
identity/settings/frame size/mount, origin/panel/tool convention, coverage, errors
and verification status. Durable calibration belongs outside `/tmp`.

### 11. Implement guided physical calibration and move-only checks

The current calibration CLI is simulation-only; build a small explicit workflow
using current HTTP frames and existing bounded UDP commands. First check ACK,
homing/origin, measured travel and Z retraction with operator control. Capture
fresh stable raw correspondences and save an unverified installed-camera fit.
Simulation/old-recording transforms are not physical movement authorization.

Provide a separate commissioning mode for an operator-reviewed, bounded XY move
with the tool retracted and no press; it must not mark an initial fit verified or
weaken normal action gates. Resolve only the selected current target, show predicted
XY, require explicit confirmation per commissioning move, and log measured alignment.
Use independent robot/tool measurements across the plane. Correct a consistent
offset once at the defined coordinate boundary; refit for location-dependent errors.
Keep fit points and independent physical validation points distinct. Validate on
held-out locations before enabling normal actions. Never treat a typed true flag
or low training residual as physical verification. Defer missing hardware facts
explicitly; implement/test the workflow offline with fake objects first.

### 12. Add observation to the TapperWare GUI

Reuse Flet's `DmiControlPanel`/`Runner` lifecycle. Add a small live-view session
adapter around existing acquisition/detection, not a subprocess running the terminal
CLI or a duplicate detector. HTTP over TCP receives Pi `/frame.jpg`; detection and
encoding run off the UI event loop, UI updates remain on its loop. Start/stop once,
keep bounded buffering and observation age visible. Initialize/press/network waits
must not freeze preview. Stop/clear targets on source loss, panel/camera change,
window close or session reset. Reuse the bridge's latest image for photos; avoid
a second camera owner/legacy TAKE_PICTURES conflict.

### 13. Unify GUI and vision command ownership

TapperWare currently loads flat local protocol/controller modules. Add the smallest
adapter to share the common validated transport with GUI initialization and vision
actions. Reconcile message IDs/payloads/units/timeouts with the installed slave;
preserve the wire protocol. One UDP socket, one receiver and one serialized command
owner per session; no simultaneous GUI and run_robot command clients.

Verify ACK without motion before explicit INITIALIZE. Reset calibration context
and targets when homing/origin changes. Report ACK, DONE, ERROR and timeout distinctly.
Review local IP/ports on both ends; neither HTTP success nor demo initialization
proves robot readiness. Provide explicit cleanup (the legacy GUI backend lacks
complete socket cleanup). Keep existing XML/demo behavior testable through the same
ownership boundary; never let a script bypass physical/vision-mode guards.

### 14. Add GUI target selection and move-only action

Expose current screen/label/pixel/mm/usability and one operator-selected Move
request. Reuse the validated action interface; extend its current Driver ID/right
keypad restrictions with screen-qualified identities and direct support checks for
each accepted SENSE control. Fields/boxes are not automatically press targets.
Resolve/revalidate immediately before dispatch; no queued stale target positions.
Block concurrent XML/vision/manual actions. Use at most one outstanding command,
keep detection running, latch uncertain failures and require operator review.
Inspect move-only alignment on installed hardware before the pressing step.

### 15. Enable one GUI press and verify its effect

After physical calibration/alignment/readiness acceptance, expose one Press request
through existing MOVE_AND_CLICK. Preserve signed-integer bounds/rounding checks,
correct press-duration units and no automatic retries. Observe a newer source frame
and verify the expected screen/value change where recognition supports it; otherwise
report unconfirmed. DONE means controller completion, not successful DMI input.

Review known contact/Z-accounting and homing/limit defects before pressing, using
focused separately reviewed fixes if needed. GUI Stop stops future commands; it
cannot interrupt a blocking motor routine and is not an emergency stop. Do not
automatically park/home/move after a failed action. Keep legacy XML coordinate
mode explicit; a future vision XML mode must resolve fresh labels per action,
not compile detected coordinates once for an entire sequence. No autonomous
multi-screen execution is included in this first GUI integration.

### 16. Prepare a clean presentation and reproducible startup

Replace the root GitLab-template README with concise purpose, package map,
PC/Pi dependencies (including system OCR), host-specific commands, configuration
and verified limitations. Keep one GUI startup and existing observation/terminal
entry points; no duplicate top-level launcher scripts. Include GUI source/assets
and the SENSE reference database in the approved delivery, with portable example
configuration; keep operator/network/calibration data local. Test startup from
outside the owning directory and clean shutdown without hardware in demo.

Keep only purposeful runtime/source/config/docs directories visible in the delivery.
Remove/reorganize genuinely obsolete files only with specific review and preserve
legacy/local evidence. Gitignore does not remove local clutter or already tracked
files. Do not use git rm/cached, destructive cleanup or mass moves as an implicit
part of ignore maintenance. Confirm staged files exclude videos, logs, test outputs,
operator settings and unverified calibration. Present a clear final live trial:
observe -> fit/validate -> move-only -> one press -> newer UI observation.

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
