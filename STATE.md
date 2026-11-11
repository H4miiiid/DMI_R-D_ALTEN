# Current handoff — SENSE vision and robot integration

Updated 2026-11-11. Read `AGENTS.md` and `PLAN.md` for the current phased roadmap and working rules.
This file records current facts and approved progress, not a claim that the future
steps are implemented. Git history retains the earlier detailed handoffs.

## Resume here

Phase 2/3 corrective extension — ACCEPTED OFFLINE for now by the user
(2026-11-11); STATE update and commit/push of the latest reviewed updates are
explicitly authorized. Phase 4 has not started and requires separate authorization.
Version 2 uses editable `dmi_robot_master/integration/screen_profiles.json` for
required/optional controls on both SENSE regions, title side, dynamic OCR and
presentation-only confirmation roles. Supported vocabulary is validated; normal
screens can reuse currently verified sidebar geometry. Train profiles add no
informational summary OCR; existing Gamma/Lambda and validation field readers
remain the dynamic-field exceptions to numbered/validation titles/buttons scope.
Each control confirms independently from three consistent real detections in five.
Confirmed median centers/bounding boxes persist through detection/OCR misses and
observation expiry; uncertainty pauses acquisition without renewing action proof.
Recognized screen changes, source/context changes, occlusion and incompatible
measured geometry still invalidate under the existing guards. The six-native-pixel
lock-only edge margin requires center-inside and at least 95% area containment;
it changes no action, calibration or movement tolerance. Local G1/title/border
corrections and the bounded No/Close retry remain SENSE-only. Version 1 and TWIN
behavior and existing action permissions/freshness requirements are preserved.
Accepted runtime fingerprint:
`7bfa3220608f3ed83933e137accec80ed448e7e7c58e5ca215647cc0048ac42b`,
based on HEAD `32609ba51aa111727620b74302891a9b8b81a450` plus reviewed updates.
Canonical accepted evidence: `runs/phase23_persistent_lock/` (immutable
pre-acceptance snapshot); inspect `summary.json`, `results.jsonl` and `contact.png`.
Both final reviewers: PASS WITH WARNINGS.
Checks: 231 tests plus 40 subtests; all 241 native Train Data detector/direct
outputs equal the preceding reviewed baseline. Prior 30 exact V1/TWIN frame
comparisons were reused; fake TWIN/action tests and recorded ROI probes reran.
COMPLETE LOCK frames: Train Type 55/61, page 1 60/86, page 2 58/69, validation 0/25.
Every required validation identity confirms at least once, but not all coexist:
Yes fails the unchanged shape check after a 13-pixel corner difference; monitor
geometry resets occur at frames 9/12/24; Close gets only two valid post-reset
measurements before approximately 6.34-pixel overhangs exceed the unchanged margin.
No now remains cached through nine subsequent missing/rejected measurements.
Validation retains bounded full-detection fallback; no further thresholds were
increased to force validation lock.
Natural transitions, held-out office footage, live GUI/camera, calibration accuracy
and physical pressing remain unverified. Local tests/evidence are ignored and
require separate supply in a clean clone; runtime has no dependency on them.
Next: operator Version 2 hardware validation under existing guards; further
corrections or Phase 4 require separate authorization. PLAN's Phase 4 clarification
is documentation only and does not accept or start its implementation.

## Earlier roadmap milestones (historical)

Phase 3 / G3 — COMPLETED OFFLINE; implementation accepted for now by the user
(2026-11-10), with commit/push explicitly authorized for the reviewed Version 2
work, its Phase 2 dependencies and required workflow documentation. The user will
perform comprehensive Version 2 hardware tests next. Real SENSE transition/blink
comparison, native GUI/live-camera behavior and physical accuracy remain pending;
this acceptance does not verify those criteria. Phase 4 is not authorized.
Version 1 remains the launch default. Version 2 adds selective SENSE Driver ID /
Level ROI checks, existing field recognition with independent 15-read value-change
confirmation, current activity and display-mode updates, bounded full audits and
conservative reacquisition. ROI presentation never renews full observations,
targets, calibration samples or action evidence; existing guards remain intact.
Accepted runtime source fingerprint
`37b217e33a6f7d68f948dd18adeff58870017f446c7ee85f1a940026e59e0549`,
based on HEAD `39dd29c3116b164f050678661db95663ba82cc75` plus accepted Phase 2.
Canonical evidence: `runs/phase3_smart_updates/` (immutable pre-acceptance snapshot);
inspect `summary.json`, `annotated.mp4` and `contact.png`. Final code_review:
PASS WITH WARNINGS; step_checker: NOT VERIFIED for the required real-transition
comparison. The user explicitly accepts the offline implementation with that gap.
Checks: 179 unique tests plus 23 subtests; 262 regular V2 full/direct baseline
matches, 112 V1 frozen matches, all 495 decoded TWIN frames unchanged and excluded
from monitoring, and 12 unsupported SENSE cold regressions. Simulated native
23->24 changes clear old text and confirm after 15 independent reads without
moving field geometry. Matched receipt replay full calls: Level 19->14,
Driver02 29->8, held-out Driver03 76->24; OCR calls 90->61, 29->8 and 76->24.
These are local single-trial replay costs, not hardware FPS. Driver02 has one
additional uncertain displayed field; conservative guards may reacquire. Existing
Phase 1 evidence gaps and hardware/calibration/action limitations remain open.
New tests/harness/evidence remain ignored and require separate supply in a clone;
runtime has no dependency on them. Next: operator hardware validation under the
existing supported scope and guards, then a separately authorized next phase.

Phase 2 / G2 — offline implementation accepted by the user (2026-11-09).
Version 2 progressively locks measured SENSE Driver ID / Level geometry after
three consistent independent observations within five. Required right title,
field and supported buttons remain separate from optional measured left boxes/
speed geometry. Same-pass regions before right smoothing and left optical-flow
tracking supply acquisition; predictions alone cannot confirm a lock. Cached
geometry changes presentation only; dynamic state, targets and fresh action
evidence retain their existing contracts. Full detection was explicitly retained
until separately authorized Phase 3. Version 1 and sampled TWIN outputs match.
Accepted runtime source fingerprint
`36cca7f3b2a59cdbbcda1e6e136a6588f7d1eb2974c9f1b114aa83d512ecb452`,
based on HEAD `39dd29c3116b164f050678661db95663ba82cc75`.
Canonical evidence: `runs/phase2_screen_lock/` (immutable accepted snapshot);
inspect `summary.json`, `annotated.mp4` and `contact.png`. Both final reviewers:
PASS WITH WARNINGS after fixing tracked-only left confirmation and adding native
coordinate-reference comparisons. Checks: 137 passes plus 23 subtests; 268 V2
full/direct baseline matches and 112 V1 frozen matches, with six TWIN samples per
version. Level preview jitter mean 1.10 -> 0.31 px; Driver02 0.07 -> 0.26 px.
Approximate reference-center errors 0.79–7.27 px retain +/-5-px border uncertainty
and disclosed cross-frame limits; these are not physical measurements. Lock
bookkeeping adds about 2.5 ms/frame, with no detection/OCR speedup claimed.
Conservative 4-px monitor checks can reacquire; optional-cell losses also advance
generations. Natural transitions, native GUI and physical accuracy remain
unverified. New tests/harness/evidence remain local/ignored and need separate
supply in a clean clone. Publication was subsequently authorized with Phase 3
(2026-11-10); its offline acceptance and remaining limits are recorded above.

Phase 1 / G1 — offline implementation accepted **for now** by the user, with
commit/push explicitly authorized (2026-11-09). The held-out real-SENSE improvement
gate remains **NOT VERIFIED**; this acceptance does not establish that gate or
physical validation. Version 1 remains the launch default and frozen baseline.
At this milestone, Version 2 enabled the measured contrast/border fallback for Driver ID / Level
fields on image-detected connected SENSE geometry. Existing primary title search,
OCR, control detection/activity, freshness, calibration and action guards remain
unchanged; TWIN uses the accepted path in both versions.
Accepted runtime source fingerprint
`17df5286f444ccfeec651a0dc0ad988bccdbce34e622b25f473a0dfa77ffb895`;
candidate `74d3034ee85c8894fbf5848a013af642467811f49c09408bb7ee691c484b1399`,
based on HEAD `173b4126f493cd0ecd67585d960761f27c417201`.
Canonical evidence: `runs/phase1_lighting/` (immutable pre-acceptance snapshot);
inspect `summary.json` and `native_field.png`. Final code_review: PASS WITH WARNINGS;
step_checker: NOT VERIFIED for the independent held-out gate. The user accepted
the disclosed offline implementation and remaining evidence gap after these reviews.
Checks: 155 tests plus 94 subtests passed; 280 Version 1 full/direct comparisons
match the frozen baseline. Version 2 checked 984 unique native frames, including
all 495 decodable TWIN frames unchanged; non-field content remained unchanged.
The reproduced Driver03 frame120 partial field now yields the full measured field
and direct value `23`; approximate reference-center error improves from 79.3 to
1.9 px. This frame guided development and is not independent held-out evidence.
Measured added field-stage mean cost is about 1–4 ms. Simulated field-stage recall
improves 31/36 to 36/36, but full-pipeline recall remains 22/36; geometry/title
failures, existing Level dropouts and other documented limitations remain.
An independent real SENSE failure recording must still be evaluated without
retuning. Screening first/middle/last frames from nine additional annotated
sessions produced 54 unknown observations across both versions, not a new positive.
Native GUI/live lighting and physical accuracy remain unverified. New local tests,
harness and evidence remain ignored and require separate supply in a clean clone;
already tracked field tests remain tracked. Runtime has no development-data dependency.
Operator comparison procedure: `TapperWare_Flet/README.md`, "Compare Version 1 and
Version 2". Phase 2 was subsequently authorized and accepted as recorded above.

Phase V — GUI Version 1 / Version 2 selector accepted offline; commit/push
authorized (2026-11-09). At that acceptance, both choices
used the Phase 0 detector. Switching requires stopped observation and idle execution,
clears previous evidence/selections/drafts/confirmations and requires explicit
restart. Guided mapping now rejects a different known live origin epoch even with
unchanged model/context files. Saved verification flags and the authorized
experimental recorded-map origin handling remain unchanged; no detector, numerical
fit, motor or protocol change, new action permission or Phase 1 work is included.
Accepted source fingerprint
`2545cf5be8ec6127417520c050343809fd0211a9a93ac7393749cfab8c92e1cd`;
candidate `5eb8cdc8b5f1bd52962fe4a60e3c7336728ec7ca4fc5789a93b034b7c218fda7`.
Canonical evidence: `runs/phase_v_version_selector/` (immutable pre-acceptance
snapshot); inspect `summary.json` and `baseline_equality.png`. Both final reviewers
returned PASS WITH WARNINGS after correcting the guided-origin invalidation gap.
Checks: 197 focused passes plus 66 subtests; the same pre-existing ordinary-press
100-ms expectation versus 300-ms implementation failure remains. All 446 native
full/direct/compact comparisons match Phase 0 (223 per version; TWIN sampled),
maximum one source owner, and nine headless Flet/fake-owner evidence records.
Native GUI rendering, live timing and physical comparison remain unverified.
Operator comparison procedure: `TapperWare_Flet/README.md`, "Compare Version 1 and
Version 2". New tests/evidence remain local/ignored and require separate supply in
a clean clone; runtime has no dependency on them. Phase 1 was subsequently
authorized and accepted with the limits recorded above.

Phase 0 / G0 — Version 1 baseline accepted offline (2026-11-09).
Frozen HEAD `835556da6441d83792d766b267ef3a61c7ba097a`, source fingerprint
`c44696f4d50a43c35ae58c4fbc93cbd1a09c4d001eb136c4fd13979184334578`;
accepted candidate `e81b223b35e1f1f2783f69fa2094ab8fbb4f18507dbd3873b14a4df17051efd0`.
Canonical evidence: `runs/phase0_version1_baseline/`, an immutable pre-acceptance
snapshot; inspect `summary.json` and `level_contact.png` (native frames 0/19/21).
No runtime changes. Validated 730 SENSE and 495 decodable TWIN frames, 21 simulated
lighting cases and two receipt-paced replays; 75 focused tests passed. Level
state/value: 53/53; TBL1+ omitted at 19/21. Level analysis mean/P95: 525/556 ms;
local receipt replay: 1.87 processed FPS, P95 age including recorded upstream
age 0.840 s. These are offline measurements, not live performance or physical proof.
Both final reviewers returned PASS WITH WARNINGS. Corrected field scoring separates
six Main negative frames (zero false positives) from six contract-excluded numbered
train-page samples (zero excluded outputs). Existing recognition failures remain.
Limits: newer-office failure/post-movement footage and raw Driver ID captures absent;
manual pixel references approximate; one raw Level context; TWIN container/decode
counts differ; physical accuracy and live timing unverified. New tests/harness and
evidence remain local/ignored and require separate supply in a clean clone.
Phase 0 acceptance initially authorized only its record update; Phase V and its
publication were subsequently authorized separately, as recorded above.
Prior hardware limits below remain.

Latest office follow-up: experimental one-click pressing and the camera-before-
homing mapping fix are implemented and checked offline; the latest hardware retest
has not been reported. See the office follow-up below and
`runs/experimental_one_click/` (source `457057bf1847`). This handoff update does not
mark that retest passed or authorize publication or another implementation step.

AGENTS Steps 1–7, the reusable SENSE optimization and Step 8.A are accepted
offline/recorded-camera. Step 9's reference audit is also accepted (2026-10-28);
it was published in `da7eddb`. Step 10 is accepted only as an offline proof of
concept (2026-10-29), with calibration accuracy and physical validation pending.
Step 11 is accepted offline/recorded-camera (2026-10-30), published with its
reviewed Step 10/Flet dependencies in `6189b98`. Step 12 is accepted offline
(2026-11-02) and published in `d78153a`. Step 13 is accepted offline and published
in `806e532` for right-region commissioning moves. Step 14 is accepted for now as
an offline implementation (2026-11-02): simulated pressing/box-16 hold verification
and inspection-only box-14/16 XY estimates; published in `68196f6`. Step 15's office
instructions and manual test record were published in `bb25dce`. The subsequent
office GUI/experimental short-press changes are accepted for now with commit/push
authorized (2026-11-04), retaining the deferred hardware limits below. The earlier
hardware integration dependencies are already in `d2f7569`. Step 16 is not authorized.
No recorded fit meets the ordinary 3 mm limit; saved rejection/verification flags
remain unchanged. The user explicitly authorized an experimental exception using
the saved Driver 03 homography, and reports accurate physical presses on Key 1 and
Key 4. This is location-specific user evidence, not whole-monitor validation.
Detected buttons in both measured connected SENSE regions can use that experimental
path; left presses additionally require registered left corners within 4 px of
the saved geometry. The prior office frame has a 20.24 px residual and would still
block left pressing. The user defers that test until robot access is available.
Ordinary calibration/coverage checks remain unchanged; fields, icon boxes, TWIN,
physical five-second holds and automatic retries are not enabled by this
exception. Issue 3 below adds the user-approved return within a completed press.
General physical vision movement remains unavailable.
Step 8.A was published in `d360176`. Steps 1–3 were published in `f14e46c`,
Step 4 in `0d26bd9`, Step 5 plus optimization in `0360b7b`, Step 6 in `bc727bd`
and Step 7 in `c07ecdc`.
Step 8 remains unaccepted: its offline checks pass, but required raw transition/
TRN footage and hardware are unavailable. The user deferred those checks while
independent Step 8.A was implemented. Resume Step 8 when new raw footage arrives.
Hardware feedback Issue 2 is completed and accepted offline (2026-11-04): shared
stable live preview for SENSE/TWIN, with independent fresh robot observations.
Issue 3's original software was accepted offline (2026-11-05); a later Pi test
returned ERROR after Z retracted, and physical return validation remains unresolved.
The current local post-press check differs from its accepted version, as noted below.
Issue 4 is completed and accepted offline
(2026-11-05): read-only OCR field values beneath the preview. Issue 1 remains
deferred. Issue 5 is completed and accepted offline (2026-11-05): rounded GUI
coordinates and a display-only 2 mm live XY deadband. Issues 2–5 retain their
office-validation limits; no commit/push is authorized. The user withdrew the new
pre-initialization nudge extension (2026-11-05) to retain the existing raw-step
workflow. Its GUI/API/UDP additions and X-helper changes have been removed.
The original `_x_movement()` and commented manual test loop remain as provided;
the GUI's existing 5 mm controls still require initialization. The extension was
never accepted; `runs/prehome_x_nudge/` now records its withdrawal verification.
Office checks of live preview, left-region geometry and additional button locations
remain pending independently; the user reports fixing GUI flashing with gapless
image playback. Detection speed, full-surface accuracy, contact/retraction/stop
behavior and setup repeatability remain open.
Automatic marker-based setup correction and per-session reference alignment were
discussed only; the user explicitly deferred implementation. No new calibration
method, marker detection or setup automation is authorized by this publication.
Further accuracy/performance work, extra action types and Step 16 need separate
authorization. Keep reports in chat and preserve the distinction between user
hardware observations, offline checks and independent physical measurements.

Plan clarification (2026-10-26): Steps 5–7 on SENSE require visible titles and
buttons only, including visible left Yes and right keypad/selector/navigation
buttons. Left summaries and noninteractive right text/rows/field values/confirmation
content are excluded from OCR, annotations and optional exports in those states.
Step 7 now has a user-approved exception: measure the gray right confirmation
button center and OCR its current Yes/No using the existing validation field output.
Keep localization, button evidence/freshness and existing schemas; preserve Step 4
and TWIN behavior. Measure accuracy and processing cost before claiming gains.
This dated plan clarification did not authorize implementation; later approvals
are recorded in the accepted milestones below.

TWIN scope clarification (2026-10-26): the user accepts the existing TWIN
detections. Upcoming detection work targets SENSE only; leave TWIN code, tuning,
pipeline behavior and outputs unchanged. Shared-module edits must be SENSE-only;
TWIN checks are regressions, not a tuning/fix task. Existing limitations remain
documented, and physical TWIN calibration/pressing validation is still deferred.
Issue 2 exception (2026-11-04): the user authorized the shared GUI preview for
TWIN as well as SENSE. This changes presentation only; TWIN detection, tuning,
structured results and robot-coordinate/action logic retain their baseline.

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

Hardware feedback Issue 2 — completed; software accepted (2026-11-04).
One `LivePreviewState` serves SENSE and TWIN in the existing Flet render worker:
fresh camera backgrounds, the existing four-native-pixel display deadband, and
button/title retention through at most two missed updates and 1.5 s from their
last observation. Context/content changes, expiry and Stop invalidate history;
independently measured regions remain available without inventing a partner.
Robot targets still use current unmodified detections and direct evidence.
`TWINS / inferiore` supports observation only, without SENSE calibration or pressing.
Accepted evidence: `runs/issue02_preview_flicker_investigation/`, source fingerprint
`932a1f879111` (immutable pre-acceptance snapshot); inspect `annotated.mp4` and
`twin_preview.png`. Checks: 690 integration/vision passes plus 330 subtests;
69 focused passes; GUI 107 passes with the same three historical fixture failures.
Recorded validation covers all 25 native SENSE validation frames plus three cold
TWIN samples and explicitly simulated misses. TWIN decoding yielded 233 frames
against 263 reported by its container; no full TWIN-video validation is claimed.
The user explicitly waived further subagent review; no final independent verdicts
are asserted for this shared version. Native GUI/live-camera smoothness and physical
behavior remain unverified. Tests/evidence remain local and ignored. Acceptance
does not authorize commit/push, Issue 3 or any other next step.

Hardware feedback Issue 3 — completed; software accepted (2026-11-05).
The Pi receiver requests the existing `click(..., x_y_return_to_zero=True)`:
contact, short hold, sensor-confirmed Z retraction, XY return to absolute `(0, 0)`,
then DONE. Missing contact/retraction or incomplete XY motion yields ERROR without
an automatic retry; failed contact/retraction does not start the XY return.
The existing owner/GUI stays busy until completion. One Z contact-overtravel pulse
is now counted as one step instead of 200; ordinary target/freshness/calibration
guards remain unchanged, and the physical press also checks home/return distance
against its declared bounds. This affects every receiver MOVE_AND_CLICK, including
legacy XML presses; direct Python callers retain the optional return flag.
Accepted evidence: `runs/issue03_return_home/`, source `f9b9fd4cd474` (immutable
pre-acceptance snapshot); `results.jsonl` contains fake command traces. Checks:
432 integration passes plus 153 subtests; 106 focused passes plus 19 subtests;
GUI 107 passes with the same three historical fixture failures. The final two
fake-Z pulse cases ran in the focused suite after the integration run, with the
same production code. No subagents were invoked at the user's request; no
independent reviewer verdict is claimed. Both Pi files must be updated and the
idle receiver restarted before this behavior is available. Physical contact,
retraction, origin accuracy, return and stop remain unverified; GUI Stop still
cannot interrupt blocking motor code. Tests/evidence remain locally available
under the existing ignore policy. No commit/push was authorized or performed.

Hardware feedback Issue 4 — completed; software accepted (2026-11-05).
One read-only OCR field-values section below the preview reuses existing compact
field names and recognized values for SENSE/TWIN. Current direct field/state/
visibility/value/center agreement is required; unreadable or unconfirmed reads,
missing fields and expiry are explicit. Stop and screen/session changes remove
old text. No extra OCR, detector, calibration or robot-target changes were made;
previous titles/buttons-only exclusions and absent left-summary extraction remain.
Accepted evidence: `runs/issue04_ocr_fields/`, source `ac974f48b3c2` (immutable
pre-acceptance snapshot); `results.jsonl` contains three native cold readouts
(SENSE Level 1, validation Yes, TWIN Driver ID 12) and seven headless Flet display
states. Checks: 34 focused passes; 454 integration passes plus 153 subtests;
GUI 110 passes with the same three historical fixture failures. The first broad
run hit the existing 1.5-s move-only freshness expiry during overlapping checks;
the isolated test and full rerun passed without changing limits. No subagents
were invoked at the user's request; no independent verdict is claimed. Native
GUI/live-camera readability remains unverified. Tests/evidence remain local and
ignored. Acceptance authorizes no commit/push or additional recognition work.

Hardware feedback Issue 5 — completed; software accepted (2026-11-05).
GUI pixels use whole numbers and millimeter estimates one decimal. The selected
live XY readout holds an independent unrounded pair until either axis changes by
at least 2 mm from its last displayed baseline, then updates both axes. Target,
screen/session and calibration identity/provenance changes, loss/expiry, Stop and
unavailable mapping reset it. Current pixels remain independent of the mm hold.
Live details share the baseline; action dialogs use current coordinates. Stored
calibration points and robot plans/payloads keep their precision and validation.
Accepted evidence: `runs/issue05_display_coordinates/`, source `0ddfa8b9ba1c`
(immutable pre-acceptance snapshot); eight headless Flet cases in `results.jsonl`
include cumulative jitter, threshold crossing, same-capture calibration change,
fresh fake motion despite held display, expiry and Stop. Checks: 50 focused passes;
454 integration passes plus 153 subtests; GUI 129 passes with the same three
historical fixture failures. The GUI calibration test also verifies precise
collected pixels/mm are unchanged. No subagents were invoked at the user's request;
no independent reviewer verdict is claimed. Native GUI/live-camera readability
remains an office check. Tests/evidence remain local and ignored. No commit/push
was authorized or performed.

Office follow-up — current implementation; hardware confirmation pending
(recorded 2026-11-06).
Both Flet preview images now use `gapless_playback=True`. The user reported a
stable browser image but flashing raw/annotated GUI previews; reducing JPEG
publication to 20/10 FPS did not help, and the user reported fixing the GUI issue.
No camera exposure, capture-rate or TCP/HTTP changes were made for this fix.

The experimental SENSE button now uses one click as the operator's confirmation,
without another dialog. Selection persists through missed updates and temporary
unknown/stale display state while the camera/session identity remains compatible.
An available button requests validation; it is not a promise of motion. The backend
resolves precise direct coordinates again after the controller-position query,
preferring the newest detection and permitting at most two missed updates within
the original 1.5-s evidence lifetime. Cached annotations/rounded GUI XY never
authorize pressing. Missing/expired evidence, inactive/uncertain controls, changed
screen/geometry/source, invalid mapping/origin or robot state still block dispatch;
busy actions block duplicate clicks, with no queue or automatic retry. Ordinary
calibrated pressing keeps its confirmation and calibration/envelope checks.

The user's disabled-button screenshot showed the ordinary label and unavailable XY.
Offline reproduction found that homing after camera start invalidated XY and lost
the experimental mode in the GUI. Mode identity now persists through invalidation;
successful operator-confirmed initialization rebinds only the experimental
projector to the new origin and requires a newly captured detection before reuse. It preserves the
camera geometry anchor; custom calibrations remain invalidated. The actual office
calibration-status reply and post-fix hardware result are still unavailable.

Current evidence: `runs/experimental_one_click/summary.json` and `results.jsonl`,
source `457057bf1847` (supersedes the unaccepted `510df727451e` candidate). Eight
synthetic/headless cases record actual fake command traces, misses, coordinate
changes before dispatch and camera-before-homing recovery; no live devices were
opened. Checks: 94 focused passes; full GUI 132 passes with four existing failures
(one ordinary 100/300-ms expectation mismatch and three legacy runtime fixtures).
Earlier broad-run results/timing-test rerun remain explicit in the summary.
No subagents were used under the user's continuing waiver; no independent PASS
is claimed. No Pi update is needed for these PC changes; tests/evidence are local
and ignored. Native GUI and physical pressing/return checks remain pending.

Current local variants must not be confused with the accepted Issue 3 snapshot:
ordinary `physical_press.PRESS_DURATION_MS` is 300, while experimental pressing and
its label remain 100 ms; ordinary GUI labels still say 100 ms. Pi `_z_click()`
still attempts retraction in `finally`, but now returns `clicked` rather than
`clicked and retracted`, so its post-press result no longer confirms retraction
before XY return. The initial Z guard remains. This variant has not received new
physical validation; the accepted Issue 3 evidence is unchanged and does not
validate this altered post-press check. This documentation update changes no runtime.

Office GUI and experimental pressing — accepted for now; commit/push authorized
(2026-11-04), with left hardware validation explicitly deferred by the user.
The existing GUI now prioritizes camera/detected-button inspection, searchable
selection, visible sensor homing and one confirmed 100 ms press; advanced tools
remain expandable. The initialization button's oversized layout was corrected.
Blank robot configuration uses durable ignored `dmi_robot_config/local/gui_robot.json`;
custom overrides and Demo/fake behavior remain separate. Manual X/Y controls send
one 5 mm Z=0 move per click after connection/homing/readiness, using the same owner
and configured travel bounds. Pre-homing jogging is not exposed in the GUI;
existing raw-step helpers/manual test code remain separate. Millimeter conversion
still requires sensor scaling. No motor rewrite is included.
Hardware SENSE HTTP observation with blank custom calibration fields reuses
`dmi_robot_config/local/step10_sense_offline/driver03.candidate.json` without changing
its matrix, keypad reference data, rejection flags or 4.76 mm recorded error.
Current measured right borders register each camera session; fresh original-pixel
targets, matching direct evidence, activity where classified, current origin,
robot readiness, movement bounds and single-use confirmation are rechecked before
one MOVE_AND_CLICK. Left direct button evidence is captured before stabilization
for connected SENSE only; TWIN detection/output behavior remains unchanged.
Normal calibrated presses retain the 3 mm/envelope gates. Move-only tests and
alignment forms are not prerequisites for this explicitly experimental path.
User reports robot initialization and accurate Key 1/Key 4 presses. Their older
Pi receiver needed `DmiRobot.click(..., x_y_return_to_zero=False)` rather than a
nonexistent `move_and_click`; the repository receiver already uses `click`.
Neither DONE nor controller XY independently proves contact or alignment.
The prior full-monitor review was code_review PASS WITH WARNINGS / step_checker
NOT VERIFIED for installed left-side use; its 20.24 px discrepancy remains open,
not converted into a success by this acceptance/publication. Prior evidence:
`runs/sense_full_monitor_press_20261104/` (source fingerprint `44d83f2c31c1`).
Publication review entry point: `runs/office_gui_publication_20261104/`; local
tests/evidence/configuration remain ignored and need separate supply in a clone.
Publication checks: 393 integration passes plus 153 subtests; GUI 104 passes and
the same three known runtime fixture failures. The changed vision file is
hash-identical to the prior 272-pass/177-subtest vision run. Compilation and diff
checks pass; offline GUI events distinguish physical from simulated press labels.
No live robot commands were sent by the agent. An attempted read-only camera
snapshot timed out; no new physical validation was obtained. Automatic setup
correction and physical holds remain unimplemented. Return-home changes were
unimplemented at that milestone; see the later Issue 3 and local-variant notes.

Step 15 — accepted documentation-only; commit/push authorized (2026-11-02).
`TapperWare_Flet/README.md` provides a four-step Mac-first camera check, expandable
PC/Pi setup and office procedures for observation, communication, guided calibration,
independently bounded commissioning moves, failure handling and safe shutdown.
`dmi_robot_config/office_trial.example.json` is a portable manual checklist and
measurement/problem form; all 14 hardware checks start not_run. Neither document
is an action authorization. No runtime, detector, TWIN or Pi code changed.
Both reviewers PASS WITH WARNINGS on final reviewed source
`d7540adfca2bc57456be6063fbb832bdb55320f3e8e79c24b0f1241c622a1835`.
JSON, local links, collapsible sections and diff checks pass. Unchanged-runtime
offline suites: 572 integration/vision tests plus 330 subtests pass; GUI 78 pass
with the same three known fixture failures. Suites were not repeated for the later
documentation simplification. Docs-only work needs no generated evidence package.
Fresh PC/Pi provisioning, native GUI layout and all physical calibration, alignment,
camera/robot/stop/contact/hold behavior remain unverified. Physical vision pressing
stays locked; Step 8's footage/coverage limits remain open. The user requested
publication without invoking subagents again. Next proposed step: 16, only after
separate authorization and operator-supplied office observations/measurements.

Step 14 — accepted for now as an offline implementation (2026-11-02).
Commit/push was subsequently explicitly authorized and published in `68196f6`;
that approval did not authorize Step 15, which was accepted separately above.
One explicitly confirmed
simulated right-button press (100 ms) or eligible left-box-16 hold (5000 ms) uses
the shared command owner and existing MOVE_AND_CLICK protocol. Eight fresh checks,
single-use 30-s intents, unchanged 1.5-s direct evidence, adequate numeric fits,
current source/context/origin/geometry, in-hull targets and independent movement
bounds remain required. No retry, return or automatic sequence is added. Busy
input is rejected; cancellation retains ownership until the bounded wire outcome.
Physical vision presses are rejected unless simulation is true AND transport is
FakeTransport; typed readiness/verification flags cannot enable physical pressing.
Hold eligibility requires a directly lit, confirmed blinking mode with power in
box 14 and matching measured centers/history epoch. After DONE, at least three
new source frames spanning 0.8 s must show the same mode steadily in box 14 and
box 16 visibly empty, retaining the original power/blink lineage. Upstream age,
reset epoch, source/geometry, duplicate/buffered/pre-DONE frames and final file-read
freshness are checked; verification is bounded to four seconds. DONE/blink-off,
loss, ambiguity or changed identity cannot claim acknowledgement. The result is
observed_mode_transition, not proof of physical contact or robot-caused UI input.
Both reviewers PASS WITH WARNINGS on accepted implementation source
`4d1f9a2bfb724a18be5e24a95407e16c0870c0b8c0ffd4cf090a408192177ef9`.
Accepted package: `runs/step14_guarded_pressing/` (summary, compact results,
synthetic mode-hold contact sheet and native recorded box-XY preview; immutable
pre-acceptance snapshot, neither preview is a GUI screenshot or physical proof).
Full suite: 572 passes plus 330 subtests; focused: 181 plus 21 subtests. GUI:
78 passes with the same three pre-existing reference/50-ms/TWINS-profile failures.
code_review independently passed 106 tests; step_checker passed 61. All 51 cold
rich/direct fingerprints match accepted Step 13, including 39 TWIN. Of 59 accepted
vision/icon files, only the opt-in SENSE mode-history reset counter changed (two
lines); core recognition/OCR/TWIN outputs remain unchanged. Existing historical
terminal-timeout and temporary-baseline-expiry warnings are not erased.
Eight mode identities and successful/negative acknowledgement logic are checked
with synthetic images, adequate synthetic fits and fake hardware. Fake clicks
acknowledge immediately: 5000 ms is a tested payload, not five seconds of actual
contact. Recorded Driver02 retains its rejected fit and sends no action. Boxes
14/16 now show estimated XY, including out-of-hull extrapolations; those recorded
left estimates have unverified error and cannot authorize pressing. Other left,
field/unmeasured actions and ordinary physical vision movement stay unavailable.
Receipt replay: 3.65 processed FPS, analysis mean/P95 0.263/0.284 s, P95 age 0.605 s;
28/53 processed, 23 overwrites, two EOF discards. These are local receipt-paced
measurements, not sensor/network/native GUI performance or a speedup claim.
Unverified: natural blinking/acknowledgement footage, native window/dialog layout,
live camera/Pi/robot behavior, physical calibration/coverage/alignment, actual hold
force/duration, retraction/contact/sensors/stop and deployment timing. Existing
receiver accounting/contact and detection speed/transition/TRN/overlay/center/field
limits persist. Schemas retain hardware_verified=false/action_usable=false and no
physical validated area. Operator declarations/controller XY/requested Z=0/DONE
are not physical proof; GUI Stop cannot interrupt blocking receiver motor code.
Accepted legacy static XML/photo safeguards remain separate and unchanged. Local
ignored tests/evidence/synthetic models/envelopes need separate clone supply;
no runtime dependency on runs/tests/scratch. Next proposed step: 15, awaiting
explicit authorization; physical validation remains pending.

Step 13 — accepted offline with the disclosed limits; commit/push authorized
(2026-11-02). Current target selection inspects native pixels, predicted absolute
XY, calibration status and freshness. Explicit commissioning-only moves require a
numerically adequate guided fit, a measured right-region button inside its fit
hull, current direct screen/button evidence, matching source/geometry/context/origin,
and independently configured absolute XY bounds plus a maximum move distance.
Prepare sends no packets. A single-use 30-s intent requires five fresh operator
checks, without extending the 1.5-s evidence limit. The one command owner checks
ACK/current controller XY, revalidates current evidence/files/bounds and sends one
validated MOVE[X,Y,0]. Busy requests are rejected, not queued; UI cancellation
retains ownership until the bounded transaction finishes. No press, retry or
automatic return is added; uncertain faults revoke readiness/origin and close.
Both reviewers PASS WITH WARNINGS on reviewed implementation source
`dc5c0b990650dc83fb6692a16985dc8114ad464944d62284cbff0af5796082a4`.
Accepted package: `runs/step13_move_only/` (summary, compact results and one native
recorded-frame preview; immutable pre-acceptance snapshot, not a GUI screenshot).
Full suite: 518 passes plus 330 subtests; focused: 88 passes. GUI: 71 passes with
the same three pre-existing reference/50-ms/TWINS-profile fixture failures. Each
reviewer independently passed 50 move/Flet tests. All 51 rich/direct cold output
fingerprints match durable accepted Step 12 evidence, including 39 TWIN samples;
all 59 detector/icon files are unchanged. The earlier Step 12 temporary-baseline
expiry remains historical, not retroactively repaired. TWIN is not retuned.
Positive movement/Flet checks use an adequate synthetic fit, independent synthetic
bounds and fake hardware only. Actual recorded Driver02 keeps its rejected fit
and sends no MOVE. Receipt replay: 3.50 processed FPS, analysis mean/P95
0.274/0.332 s, P95 result age 0.550 s; 27/53 processed, 24 overwrites, two EOF
discards. Preparation mean/P95 0.0168/0.0184 s. These are local measurements,
not installed-camera/network/native-GUI performance or a claimed speedup.
Ordinary movement stays blocked: schema-3 hardware_verified=false/action_usable=false
and no physically validated coverage remain unchanged. Both recorded models still
fail 3 mm and cannot authorize even commissioning movement. Only represented right
buttons inside the fitted hull are supported; left buttons, fields and unmeasured
controls remain inspection-only. Box centers remain detected in pixels; GUI box XY
projection is skipped. A read-only Driver02 frame-0 follow-up calculated affine/
homography estimates for boxes 14/16, both outside the fit hull; left-region error
is unverified. That calculation did not implement box XY display or movement.
Native layout and all physical bounds/start-position/retraction/path/stop, camera/
mount/tool/origin conventions, calibration accuracy and alignment remain unverified.
Operator declarations, controller XY, requested Z=0 and DONE are not physical proof;
GUI Stop cannot interrupt blocking receiver motor code. Existing receiver accounting/
contact, detection speed/transition/TRN/overlay/center/field limits persist. Legacy
XML/photos retain their separate accepted confirmation/observation guards. Tests,
evidence and synthetic calibration/envelope fixtures remain local/ignored and need
separate clone supply. Next proposed step is Step 14 (guarded pressing/box-16 hold
and box-14 visual verification), requiring explicit authorization. Acceptance here
does not implement or authorize that step or a left-region extension.

Step 12 — accepted as an offline software implementation; commit/push authorized
(2026-11-02). One shared UDP command owner connects the Flet GUI to validated
communication, ACK-only connection, explicit readiness/homing checks, position
inspection and cleanup. Guided SENSE collection records fresh native pixels and
operator-entered absolute XY, compares affine/homography with held-out controls,
shows residuals and saves durable schema-3 inspection candidates. Source/origin/
geometry changes invalidate drafts and mappings. Legacy static-coordinate XML
requires separate per-run confirmation, homing and stopped observation; the whole
plan is bounds-checked before XML movement. Legacy photos share that owner and
exclude observation; atomic saves preserve complete photos on write failure.
Both reviewers PASS WITH WARNINGS on reviewed implementation source
`94709bbef079908e836f5e3349d3521d9f7839495e006355fb09b9ad2a510e4c`.
Accepted evidence: `runs/step12_guided_calibration/` (summary, compact results,
annotated source preview and residual plot; immutable pre-acceptance snapshot).
Full suite: 473 passes plus 330 subtests; focused: 63 passes. GUI: 66 passes and
three pre-existing fixture failures: attached-script reference/50-ms expectations,
empty TWINS-profile expectation, and normal-run 50-ms versus current 100-ms default.
An earlier full trial hit the existing intermittent simulated-terminal 2-s timeout;
focused recheck and final serial suite passed without relaxing any safety limits.
All 59 detector/icon files match accepted Step 11. The same 51 cold samples were
rerun, but their historical temporary rich/direct baseline expired; final outputs
are fingerprinted and numeric equality was not re-compared. TWIN is not retuned.
Recorded Driver02 demo: 10 points, eight fit/two held out, using existing reference
XY as simulated operator input, not new independent physical truth. Affine/
homography maxima 5.216/3.986 mm both reject 3 mm; no selected model or physically
validated coverage. Durable local candidates: `dmi_robot_config/local/step12_sense_guided/`;
the accepted summary identifies the exact candidate path/hash. Receipt replay:
3.70 processed FPS, analysis mean/P95 0.261/0.326 s, P95 age including recorded
upstream age 0.538 s; 28/53 processed, 23 overwrites, two EOF discards. These are
local worker measurements, not current sensor/network or native GUI paint rates.
Unverified: native window/dialog layout (Computer Use permission unavailable), live
Pi/camera/robot connection and installed settings/mount, homing/travel limits,
Z retraction/contact/physical stop, tool/origin/panel conventions, independent
held-out mm accuracy, alignment and physical vision-guided moves/presses. Operator
checkboxes, entered XY and controller XY/DONE are not independent physical proof.
Existing speed, overlays, natural-transition/TRN and center/field limits persist.
Schema-3 exports always retain hardware_verified=false, action_usable=false and
no physically validated area, even for numerically adequate fits; rejected models
cannot authorize movement. Freshness, confirmation, coverage and calibration gates
remain intact. New vision-selected movement/pressing/holds are not implemented.
Explicit homing and separately confirmed legacy XML can move real hardware when
later operated; only fake hardware was exercised here. No automatic retries or
parking after uncertain failures. Incomplete drafts are memory-only; save complete
candidates before context changes and back up local calibration independently.
Ignored tests/evidence/local models need separate clone supply. Step 13 was later
accepted with the restricted scope above; office physical validation stays pending.

Step 11 — accepted offline/recorded-camera; commit/push authorized (2026-10-30).
Integrate observation into the existing Flet GUI through VisionSession and the
shared calibration inspector: independent acquisition/detection/render workers,
bounded in-memory latest state, matching annotations, native pixel centers,
inspection-only predicted XY, freshness clearing and optional diagnostic JSONL.
Opt-in SENSE mode pairs/history distinguish blink-off and verify the same blinking
identity replacing power; stale lineage, intervening modes and cumulative geometry
drift invalidate that association. No movement, pressing or hold is enabled.
Both reviewers PASS WITH WARNINGS on final source
`eda706300adf18867cf1481020f24ae1808a145409a38dfb6fb1b5f91c463cd8`.
Accepted package: `runs/step11_flet_observation/` (summary, compact results, one
native 25-frame 2304x1728/5-FPS replay and three previews). Full suite: 450 passes
plus 330 subtests; focused: 31 passes. All 51 frozen samples match, including 39
TWIN. GUI: 59 passes and three unchanged baseline failures against current reference
data. Receipt-paced Level/page-1/validation: 1.66/3.19/3.46 processed FPS; P95 age
including recorded upstream age 0.894/0.553/0.572 s; EOF clears targets. These are
local replay measurements, not camera/GUI paint rates. Native GUI layout, natural
blinking footage, installed-camera performance and physical operation remain
unverified. Rejected calibration remains inspection-only. Evidence/tests/local
models need separate clone supply. The later Step 12 acceptance is recorded above.

Step 10 — accepted as an offline proof of concept only (2026-10-29).
User explicitly accepts the implementation while calibration accuracy and physical
validation remain pending; that initial acceptance did not authorize publication
or Step 11. Later Step 11/publication permissions are recorded above. Reviewed
implementation `2d7d2cd275f012ae0390807b9644a30df48c80023e72005649658d15aa082916`;
diagnosis `aca33b56357d99d191f350f73d8099abc1900126a0740365067673da84d32f96`.
Canonical accepted POC evidence: `runs/step10_sense_calibration/` (summary, compact
results, source preview and two diagnosis plots). Separate durable, rejected
candidate exports: `dmi_robot_config/local/step10_sense_offline/`.
Offline SENSE schema 2 compares affine/homography with whole-control holdouts and
explicit screen/region/kind aliases. Recorded-source inspection checks context and
geometry, always returns unusable targets with no action support; legacy executable
keypad calibration/action gates and TWIN detection remain unchanged.
Full suite: 423 passes plus 330 subtests; focused/guard checks: 11 plus 21 subtests.
Implementation code_review PASS WITH WARNINGS; step_checker NOT VERIFIED for the
required adequate fit. Both reviewers PASS WITH WARNINGS on the later diagnosis.
Two independent recording contexts fail the provisional 3 mm maximum: affine
3.98/4.19 mm, homography 5.27/4.76 mm; no selected model or physical validated area.
Diagnosis favors persistent reference/image-center mismatch, amplified by sparse
coverage and field extrapolation; averaging does not pass. Small center bias and
one reproduced 80-px partial-field transient also need follow-up. Exact physical
cause, tool/origin convention and independent center/mm truth remain unverified.
Next accuracy evidence: remeasure spread-out exact centers, prioritize column
2/5/8/0, upper gray field and spacing 1/2/3; preserve independent holdouts and reject
partial current field measurements. Do not infer replacement coordinates from fits.
No live hardware or robot actions were performed. Evidence/new tests/local models
need separate clone supply; the unchanged TapperWare reference JSON is a reviewed,
production dependency included in the later Step 11 publication approval.

Step 9 — reference audit accepted; commit/push authorized (2026-10-28).
Read-only audit of `TapperWare_Flet/DmiPositions.json -> DMI_SENSE_TOUCHSCREEN`;
no runtime, detector, TWIN, database or action-gate changes. Canonical accepted
package: `runs/step09_reference_audit/` (summary, mappings JSONL, one preview),
reviewed version `59c913e91f09ef46168143db2d7bf9be5f821a48077d3a4c2a6a90a93e749ea4`.
Both reviewers PASS WITH WARNINGS, no blockers. Of 24 reference entries, 20 have
recorded SENSE semantic matches at 16 distinct stored XY locations; two further
TRN candidates lack validated SENSE footage. Of 75 recorded control identities,
22 map to references and 53 lack an unambiguous reference. User confirms gray
Driver/Level/TRN confirmation controls use existing field outputs; KEY_YES_1 is
the left completion Yes on Train Data/(1/2)/(2/2), and KEY_YES_2 is validation's
upper-right gray Yes/No field, separate from lower Yes. END_OF_DATA_ENTRY remains
explicitly unknown; ACK has no validated detector identity. Similar KEY_YES_1
positions do not prove identical centers or add independent spatial points.
User reports the reference set was physically tested on the same setup with
panel/setup offsets included. Do not add that panel Y offset twice; separate tool
datum, center correspondence and independent mm accuracy remain unverified.
Checks: 72 pure XML compiler cases at 0/+7/-7 mm, field/native-center contracts,
alias isolation, accepted source/package hashes and Git diff check pass. The old
calibration loader rejects the new schema; no path swap, fit or hardware action
was performed. Package and generator are local/ignored and need separate clone
supply. Step 8 remains pending; that approval did not authorize Step 10.

Step 8.A — accepted offline/recorded-camera; commit/push authorized (2026-10-28).
Expose `dmi_computer_vision.src.dmi.api.VisionSession` / `Observation` with a
package README. Reuse FrameProcessor/LatestState and the exact process_live alias;
no detector, TWIN, GUI, command or calibration behavior changes. Explicit source/
session lifecycle, serialized processing owner, detached native-pixel results/
direct evidence and bounded receipt/upstream freshness; invalid input or analysis
failure closes/clears, with explicit restart and no automatic retry. Raw runner/
LatestState aliases retain their documented original contracts. Calibration
resolution stays separate until later reference/physical validation; no mm/action
eligibility is enabled. Reviewed source
`3e4cd74ede624edcb64c36fff3c471e273cb00a9eb68c99003542ff15705a815`;
code_review PASS, step_checker PASS WITH WARNINGS, no blockers. Suite: 412 passes
plus 309 subtests; focused 10 plus 23 subtests, independently rerun by reviewers.
All 730 static native results/direct supports and 51 cold samples (39 TWIN) match
existing output exactly. Wrapper overhead mean/P95 0.46/0.62 ms per frame over
730 same-call measurements; no live-FPS improvement claim. Canonical accepted
package: `runs/step08a_vision_library/` (summary, compact results, seven-case fake
lifecycle log, native 25-frame 2304x1728/5-FPS video and one preview). Caller owns
acquisition and serialized worker lifecycle; GUI wiring is deferred. Step 8's real
transition/TRN and installed-camera limits remain open. Tracked icon assets and
OCR-English are deployment dependencies; ignored tests/evidence need separate
supply in a clone. No hardware actions. Await the next explicit instruction.

Step 8 — offline checks completed; recording-dependent checks deferred by the
user (2026-10-28), not accepted. Runtime remained unchanged at `c07ecdc`.
Full 948-frame native validation: 730 static frames plus 218 stress frames;
294 prior SENSE rich/direct results and 51 cold samples (39 TWIN) match exactly.
402 tests plus 286 subtests pass, including four new workflow/lifecycle tests.
Both reviewers returned NOT VERIFIED: real train-page transitions and trustworthy
transition latency are missing. Observation 11 has 168/203 unknown, 35 Main and
zero Driver detections amid source overlays, real hand occlusion and movement;
overlays are not proven to be the sole cause. All 15 annotated TRN observations
reject geometry; SENSE TRN remains unverified. Synthetic screen cuts and fake
source-failure/session checks pass but do not replace natural-transition evidence.
Regular Driver/page-1 replay: 3.35/3.04 processed FPS, P95 local age 0.496/0.430 s;
headless replay is not installed-camera/GUI performance. Pending package:
`runs/step08_workflow_validation/`, version
`387ccba1c030cd9b3cae8951ef9ef706c3e0effae5b98463b64d88870883efdf`.
The user has no unannotated originals or transition recordings and hardware is
currently unavailable. Resume these checks when new raw footage is supplied.
Independent Step 8.A was subsequently accepted (see above); Step 8 detection
coverage/latency remain unapproved; that approval did not authorize calibration,
motion or GUI integration.

Step 7 — accepted offline/recorded-camera; commit/push authorized (2026-10-28).
Recognize the SENSE validation title and independently measured right Yes/No/Close;
omit the left summary and never invent a left Yes. The gray confirmation button
has measured geometry/center and exact current Yes/No OCR in existing
`data_field` / compact `fields.validation`, separate from lower button identities.
Reviewed source `ebf660b33102a3456b181c156d1a3064dff194690589533b43d3cebf547ae7ef`;
both reviewers PASS WITH WARNINGS, no blockers. Title, lower Yes/No and gray
button/Yes succeed 25/25; Close 24/25 (sequential frame 12 conservatively omitted).
Cold first/middle/last recognize all three lower controls. Synthetic No, blank/
unknown/missing/ambiguous gray evidence, changed/moved/erased controls, information
independence and loss/recovery pass. All 269 prior SENSE frames and 51 sampled
cold regressions retain exact rich/direct results. Suite: 398 passes plus 268
subtests; each reviewer independently passed the 13 focused tests.
Native 25-frame analysis mean/P95 0.254/0.300 s; 75 OCR calls/0.648 s total,
including one extra gray-value call/frame. Regular/selective receipt replay:
3.08/2.64 processed FPS, P95 local result age 0.520/0.498 s; 16/13 of 25 frames
processed, 9/6 overwrites and 0/6 policy skips. No speedup over positional labels
is claimed. Existing confirmation, direct-evidence age, 4-px publication and
expiry gates stay unchanged; targets clear on stop. Lower-button center jitter
mean/P95/max 1.47/5.05/15 px remains an open limitation before coordinate use.
Accepted evidence now lives at `runs/accepted/step07_validate_train_data/`;
source/artifact hashes match the reviewed package formerly at
`runs/step07_validate_train_data/`. Its six files include compact results, summary,
publication evidence, video and two PNGs. The video retains all 25 source frames
at 2304x1728 and original 5-FPS encoding; playback FPS is not detection throughput.
Only one short static recording plus synthetic changes is validated; natural
transitions, independent footage, human coordinate truth and installed-camera/
physical accuracy remain unverified. Recognition is not enabled/actionable/press
proof. Ignored tests/evidence need separate supply in a clone. No hardware actions.

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

## Historical repository and hardware baseline (2026-11-06)

- Local HEAD at that handoff: `f2597ae` on main, matching the local origin/main reference
  (no remote query or push performed for this update). It contains the earlier
  office GUI/SENSE pressing work; hardware integration is `d2f7569`, Step 15
  `bb25dce`. Later feedback/follow-up changes remain uncommitted. Preserve unrelated
  local XML/settings/calibrations; no publication is authorized for this update.
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
  Saved GUI JSON: Mac `.133:2001`, ID 48059; Pi `.210:2000`, ID 43690;
  coded XY bounds 380 x 470 mm and timeout 60 s. Root Pi YAML was updated in
  `d2f7569`; the old PC YAML is not the GUI's communication source. Local JSON
  and calibration remain ignored; preserve/back them up separately.
- User reports successful connection, robot initialization and accurate live
  Key 1/Key 4 presses. Independent mm measurements, wider physical coverage,
  repeatable placement and Z/contact/stop behavior remain unverified.

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
- GUI observation uses VisionSession/VisionObserver; guided fitting uses the shared
  calibration interfaces. Existing XML remains static database coordinates with
  the selected panel's Y offset, separate legacy confirmation and observation
  exclusion. Successful XML normally returns to origin; uncertain failure does not.
- GUI RealBackend wraps RobotSession/RobotLink/validated RobotCommands/common
  protocol on one executor and one UDP owner with explicit cleanup. Connect sends
  ACK only; homing needs explicit readiness confirmation. Live bridge frames use
  HTTP/TCP; commands/responses use UDP. Demo is not physical readiness.
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
  validation is accepted in Step 7 above. Geometry
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
  Step 9 records the user-reviewed confirmation/Yes aliases; END_OF_DATA_ENTRY
  remains unknown and ACK unsupported. Keep actual screen/region/kind qualification.
- New Driver ID reference is `DRIVER_ID_SCREEN`, e.g. KEY_1=[200,364], KEY_2=[165,364],
  KEY_3=[135,364], model default 100 ms. Old master reference is DRIVER_ID_WINDOW,
  KEY_1=[100,300], different spacing/axis direction, default 200 ms. Do not mix them.
- Legacy executable calibration still uses the old file/right Driver ID keypad.
  Step 10 adds a separate intended-reference SENSE offline fit/inspection schema
  and CLI; neither recorded candidate meets 3 mm or enables normal action support. Physical
  coverage, source/tool convention and direct-support validation still need work;
  a file-path change or typed verification flag cannot enable other controls.
- Reuse planar homography; compare simpler affine fit against independent mm error.
  Need actual matched points distributed across the plane, held-out validation,
  reference/origin/panel/tool conventions and a measured acceptance tolerance.
  Do not apply the GUI Y offset again if already included in calibrated absolute XY.
- Steps 12–13 provide guided fitting and independently bounded right-button
  commissioning moves. Step 14's fake-only presses/holds remain the simulation
  baseline; the current office short-press exception is described at the top.
  The saved rejected homography is reused only through that explicitly experimental
  route; normal calibration gates and model flags are unchanged. Full physical
  coverage, left geometry, setup repeatability and box-14/16 action validation remain
  pending. Simulation is not verification; physical five-second holds stay disabled.
- Review homing, measured limits, Z retraction/contact and physical stop first.
  Known slave concerns include contact success reporting and Z step accounting.
  Position feedback is internally calculated, not independent alignment evidence.
  GUI stop cannot interrupt blocking motor code. No automatic retries/parking after
  uncertain failures; DONE alone is not successful UI input.

## Next approvals and delivery rules

Steps 1–7, SENSE optimization, Step 8.A and the Step 9 reference audit retain their
accepted scope and publication approvals. Step 10 is accepted only as an offline
proof of concept; accuracy and physical validation remain pending. Step 11 is now
accepted offline and published with reviewed Step 10/Flet dependencies. Step 12
is accepted offline and published in `d78153a`; Step 13 in `806e532`. Step 14 is
accepted for now offline (2026-11-02), retaining all restrictions and warnings above,
and published in `68196f6`. Step 15's documentation was published in `bb25dce`.
On 2026-11-04 the user authorized updating this handoff and committing/pushing the
implemented office GUI/experimental mapping changes, accepting their current limits
while deferring the left-region hardware test. That approval alone did not validate
that geometry or authorize automatic marker/reference alignment, return-home changes,
extra action types, detection/performance work or Step 16; later feedback approvals
are recorded separately above. Next: await the user's office retest of the latest
experimental button/mapping recovery and unresolved contact/retraction/return case.
If still blocked, inspect the displayed calibration/robot-state reason before
changing another guard. No new runtime work or commit/push is authorized by this
2026-11-06 documentation request.
Detection speed remains an open limitation. Step 8 still awaits new raw footage
and acceptance. POC acceptance does not validate a calibration or authorize actions.
Continue one requested step at a time; do not infer next-step permission from
acceptance or reviewer verdicts. Do not accumulate old reports.

Ignore policy excludes local tests, media/results, caches/logs, operator settings,
local deployment data and the legacy general copy. TapperWare source/reference/
requirements and useful example XML are now eligible for version control; they
were previously entirely ignored and still require deliberate staging/review.
Ignored tests stay locally available; already tracked tests are not untracked.
Historical roadmap rewrite checks: no source files were deleted/moved, no runtime
was changed and no camera/UDP/motor calls were performed during that rewrite.
Documentation paths, all 16 step numbers and representative ignore rules were
checked; its 152 runtime/support files were hash-identical. Later implementation
and hardware observations are recorded in their own milestones above.
