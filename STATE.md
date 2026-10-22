# Current handoff — SENSE vision and robot integration

Updated 2026-10-22. Read `AGENTS.md` for the new numbered roadmap and working rules.
This file records current facts and approved progress, not a claim that the future
steps are implemented. Git history retains the earlier detailed handoffs.

## Resume here

The user requested a fresh plan: improve SENSE Level accuracy/speed, support four
train-data screens separately, then implement SENSE calibration and TapperWare GUI
integration. The roadmap/ignore rewrite is approved together with the Level
activity update below. Next implementation: AGENTS Step 1 (focused Level
accuracy review), then Step 2 (measured speed improvements), after the user's
instruction. Give short reports in chat; no new report Markdown files. Record
step completion here after approval; commit/push only with publication approval.
The user explicitly authorized commit/push on 2026-10-22 for these updates.
Publication result will be reported in chat. No other roadmap step is authorized.

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

- Inspected HEAD: `e95d707` (Level screen detection for SENSE monitor), branch main.
  Local origin/main points there too; no remote network check was performed.
  The previously pending Level/optional-controls/launcher/recorder changes are now
  in this commit. Do not repeat the old "uncommitted Level implementation" status.
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
  11.887-s receipt span. Same HUD caveat; right numeric-entry/field rows visible.
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

Level independent review before this rewrite reproduced all 53 raw frames exactly:
Level/field Level 1 correct 53/53; ten controls 53/53, TBL1+ 51/53, no unexpected
identities. First/middle/last annotations inspected. Last-frame center mean/max
error 3.87/6.19 native pixels against coarse manual references (~3-px uncertainty).
The current fitter measures each cell's borders and reads its content; it no
longer assigns the old fixed Level label order. Current Level button geometry
bypasses the old bad-anchor stabilizer; no blanket claim of zero jitter.

- Recorded live-path replay: regular/selective 0.72/0.77 processed FPS with full
  annotations/debug/export; some result ages exceed the unchanged 1.5-s expiry.
  OCR per control/retries is a measured cost lead. Source/network throughput is
  not measured by that replay. Improve cost before claiming responsive action use.
- Static Level evidence is validated; changed values, natural transitions, new
  framing/occlusion and fresh deployment remain unverified. No physical mm proof.
- Train states have existing TWIN analyzers, but SENSE localization/control alignment
  is not accepted. Connected localization still depends on a field/keypad or menu
  structure; sparse train layouts need a general image-supported geometry fix.
  Fresh cold processing of each source's last image during this rewrite found
  Level/11 controls, but unknown/zero controls on all four train sources. This is
  a sampled failure baseline, not a full replay or an all-screen coverage assessment.
- Existing Main->Driver transition geometry failure remains (integration expected
  failure). Legacy unsupported-cell/numeric/Close alignment findings from Step 5
  must be reproduced/classified where relevant; do not assume Level fixed them.
- Last independently run suites before this documentation change: **196 vision
  tests pass; 122 integration checks = 121 passes + one known expected failure**.
  They were not rerun for this docs-only rewrite. New tests/evidence remain local
  under the requested ignore policy; a clean clone cannot reproduce them unaided.

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

All new roadmap Steps 1–16 are planned; none is claimed completed here. Work one
requested step at a time: Level accuracy -> speed -> shared localization -> each
train screen -> combined validation -> reference audit -> fit/export -> guided
physical calibration -> GUI live view -> shared UDP -> move -> press -> presentation.
After each approval, replace this paragraph's next-step status and add a short
accepted milestone with checks/remaining limits. Do not accumulate old reports.

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
