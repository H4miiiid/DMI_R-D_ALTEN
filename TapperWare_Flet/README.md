# TapperWare · interfaccia Flet

## Using the camera → key → robot view

### Manual movement: 5 mm per click

After **Connetti / ACK** and **Initialize robot · sensor homing**, use the visible
**Manual robot movement · 5 mm per click** panel under the connection controls.
Confirm the tool is retracted, path clear, starting position/movement limits verified
and physical stop available. Then click **X−**, **X+**, **Y−** or **Y+** for one
5 mm step in the robot's coordinate axes. There is no repeat while holding a button.

Each click reads the current controller XY, checks the full 5 mm destination against
the existing configured limits, and sends one MOVE with Z=0. An out-of-bounds step is
rejected rather than shortened. Controls stay disabled until that command finishes;
no movement is queued, retried or followed by an automatic return. Reported XY is
read again after completion and is internally calculated, not physical metrology.
**Read controller XY** is also available without moving. Camera/calibration are not
required for manual movement; they remain required for vision-guided actions.
Pre-initialization jogging is not supported: the existing Pi conversion needs
the sensor-based travel scaling established during homing.

A new connection/origin, reinitialization or communication failure clears manual
readiness. A failure requires checking the setup and reconnecting/initializing as
needed. GUI Stop cannot interrupt blocking motor code. This panel has been validated
offline with fake hardware; physical direction, travel and retraction require office
verification. No Pi code update is needed for this panel; it uses the existing MOVE
and position commands.

### Current office test: reuse the recorded homography

At the user's request, **Hardware / SENSE TOUCHSCREEN / superiore** can reuse the
saved `dmi_robot_config/local/step10_sense_offline/driver03.candidate.json`
**homography** for an explicitly experimental short press. The user confirmed the
live camera position, orientation, 2304×1728 size and crop are unchanged. The recorded
maximum independent error is about **4.76 mm**, exceeding the earlier **3 mm** limit.
This exception accepts that numerical inaccuracy for this initial test; it does not
mark the model verified, change its saved rejection flags or validate physical contact.

1. Restart the GUI after this code update. Connect/ACK and initialize the robot.
2. In **Camera and detection results**, choose **Bridge HTTP camera SENSE** and
   enter `http://192.168.1.210:8080/frame.jpg`. Leave both custom calibration fields
   empty. **Start camera** automatically loads the saved experimental homography.
   If camera observation was started before connection/initialization, stop/start it
   afterward so its origin binding is current.
3. Select a currently detected button on either the **right or left SENSE region**,
   on any recognized screen. The GUI shows its latest native pixels and predicted robot XY, labelled
   unverified. **Experimental move and click · 100 ms** becomes available.
4. Click it, inspect the predicted XY and accept the experimental-accuracy/readiness
   statement. **Press once · 100 ms** sends exactly one MOVE_AND_CLICK. Observe the
   actual DMI result yourself before another action.

The initial camera view is registered to the recording using all four currently
measured right-region corners. Current native pixel centres are transformed into
the recorded pixel plane, then through the saved robot homography. No sample
coordinates or synthetic monitor borders are substituted for current detections.
A small framing difference from the recording therefore does not require an
identical pixel-for-pixel camera pose. The first clear measured geometry anchors
this camera session; movement beyond the existing 4 px tolerance afterward clears
XY and requires an explicit Stop camera / Start camera before a new preview.

No calibration collection, alignment form, preceding move-only test or separate
movement-envelope file is required for this experimental path. It uses the existing
configured robot XY limits confirmed during homing, checks the actual controller
start and target, and bounds movement by that configured travel. Retraction, clear
path/contact area, physical stop and contact-sensor/routine readiness still require
operator confirmation. Controller position is internally calculated, not independent
metrology. GUI Stop cannot interrupt blocking Pi motors.

At the user's request, this experimental path uses the **same unchanged homography
across the whole measured SENSE surface**, including detected buttons in both logical
regions. The user reports accurate physical presses for **Key 1 and Key 4**. Other
locations remain unverified; the recorded 4.76 mm error describes the recorded
validation points, not a maximum error bound across the whole monitor. The saved
keypad fit/coverage and rejection flags are preserved; extrapolation is explicitly
experimental. This does not create detections for unsupported screens or controls.
Left buttons additionally require their measured region corners, transformed by
the existing right-border registration, to agree with the recorded left corners
within the unchanged 4 px tolerance. A mismatch disables left pressing and shows
the reason; existing right-button mapping remains available. After correcting the
view, explicitly stop/start the camera to establish a new session before trying again.
The earlier office frame has a 20.24 px left-corner discrepancy, so left pressing
would remain blocked for that view. The user has deferred checking it until the
next hardware test; whole-monitor operation is not physically validated.
Fields and information/icon boxes are not short-press buttons. Buttons outside their
measured region, separated/TWIN geometry, movement after session registration
(>4 native pixels), wrong resolution/rotation, inactive/uncertain controls, stale or changed
selected targets, and uninitialized/faulted robots cannot authorize a test press.
Direct evidence remains limited to 1.5 s; each single-use confirmation lasts 30 s.
There is no automatic retry, return, sequence or physical five-second hold. DONE is
protocol completion, not proof of contact or correct DMI input.

Entering a custom calibration/context uses the previous guarded calibration path,
including its unchanged 3 mm acceptance and independent-envelope requirements.
Recorded test candidates are not enabled through that normal path. The saved model
must remain available in the durable ignored `local/` directory; no recorded videos,
per-frame files or test fixtures are required at runtime. No Pi Python update is
needed for this coverage extension. Physical accuracy beyond the two reported keys
remains for the office test.
Restore this local model separately on a new clone: the default Hardware HTTP
camera workflow loads it even for observation. It is not downloaded or regenerated.
Camera registration compensates image framing; it does not measure changes in the
monitor's position relative to the robot. Automatic setup correction is not implemented.

**Robot initialization is visible above the camera controls.** The button
**Initialize robot · sensor homing** is the former **Inizializza hardware** action.
Open **Robot connection settings · connect / ACK first**, leave **Custom robot
configuration (optional)** empty and click **Connetti / ACK**. The GUI automatically
loads the saved `dmi_robot_config/local/gui_robot.json`. This checks communication
without moving. Then click
**Initialize robot · sensor homing**, complete the five safety checks and explicitly
confirm homing. The Pi runs its existing sensor-based origin/travel setup and sends
DONE or ERROR. After DONE, the GUI shows **Controller initialization complete**;
this does not prove that a new sensor sweep occurred.
The existing Pi routine skips the full sweep once autoscaling is already complete
in that receiver process. Demo labels the operation as simulated homing.
Camera viewing needs no initialization. Homing moves hardware; it does not validate
pixel-to-mm calibration or by itself enable physical vision pressing. GUI Stop cannot interrupt
a blocking receiver motor routine.

The saved setup on this Mac uses the office addresses updated during testing:
Mac `192.168.1.133:2001` (ID 48059), Pi `192.168.1.210:2000` (ID 43690).
Its XY limits are 380 × 470 mm, copied from `DmiRobot._X` / `_Y`, with a 60-second
command timeout. These code limits are not new physical measurements; the existing
homing checks still require operator verification. The optional field overrides
the saved file only when needed. Demo keeps its separate fake setup. Keep a backup
of the ignored `local/` file; it is not included in Git or regenerated automatically.

1. Select **SENSE TOUCHSCREEN**, **superiore** and **Hardware**. Under
   **1. Camera and detection results**, choose **Bridge HTTP camera SENSE**,
   enter the Pi URL in **Camera address**, then click **Start camera**.
   Demo uses a recording path instead of a live camera.
2. See the annotated monitor on the left. Expand **Live camera image** for the
   latest raw picture. Expired results disappear; no old coordinates can authorize actions.
3. Under **2. Select a detected key**, type **5** in **Find a detected key**,
   then click **Key 5 · KEY_5** if it is detected. Searching only filters current
   detections; it never adds a missing key. This click selects the key without moving.
4. **3. Inspect and act** shows the selected native-pixel centre, predicted robot
   XY and result age. Missing calibration gives no XY; an estimate is not verified
   alignment. **Move and click selected key · 100 ms** opens the short-press confirmation
   when a current target, initialized robot and existing movement limits are available.
   Calibration and all action guards are validated before sending.
5. For calibration, expand **Calibration · enter measured robot X / Y**. Supply
   the independent context, start a collection, select a detected key and enter
   independently measured values in **Measured robot X (mm)** / **Measured robot Y (mm)**.
   Selecting a key also selects its measurement row. Every selection attempt,
   including a failed one, clears previous entered XY and confirmation.
   Never copy predicted XY as independent measurements. Collect
   at least five different fit controls and one held-out control, compare fits and
   save a new durable candidate. Stop/restart observation to load a model/context.
6. Robot setup is in the visible initialization panel described above. Guarded alignment moves
   are under **Movement limits and optional move-only test**, with the same adequate
   fit, current evidence, independent bounds, homing and single-action confirmations
   described below. A physical single press uses the same movement limits and the one
   readiness confirmation above; the optional move-only test is not a prerequisite. The current experimental
   recorded-map exception above uses configured robot travel directly. Demo press/hold
   tests remain behind **Demo presses and mode holds · simulation only**.

Legacy XML/photo tools and event logs are collapsed below the main view. XML uses
stored reference positions and does not perform camera-calibrated pressing. Its
run/stop footer appears when the XML section is opened or a sequence is busy.
Do not use it to bypass the physical commissioning requirements. **Stop camera** ends
observation; a GUI stop is not a physical motor emergency stop.
Switching Demo/Hardware selects recording/HTTP respectively. Each source keeps
its own address or path for this app session; changing a source does not open it.

## Start here: see the SENSE camera in the GUI

Your **Mac runs the GUI**. The **Raspberry Pi sends the camera picture**.
Start by getting that picture and the detected buttons onto the PC screen.
Robot connection, calibration and movement are later tasks.

These steps use the complete project already copied to both computers, with its
Python dependencies installed. Use the same Python environment you normally use
for this project. On a new computer, expand **Detailed setup and robot testing**
below and follow **Prepare the PC and Pi** first.

### 1. On the Raspberry Pi: start the camera

Open a terminal **on the Pi**, and open the project folder: the folder containing
`TapperWare_Flet`, `dmi_robot_master` and `dmi_robot_config`.

Find the Pi's network address:

```console
hostname -I
```

Write down its Ethernet IPv4 address (four numbers such as `192.168.1.210`).
If several addresses appear, use the one on the same network as the PC.
Then start the upper SENSE camera:

```console
python3 -m dmi_robot_master.integration.frame_bridge --bind 0.0.0.0 --camera 1
```

**Leave this terminal open.** Close any other app using that camera first.
This command runs the camera bridge; do not start the robot receiver for this check.

### 2. On the Mac: open the GUI

Open **Terminal on the Mac**, in the project's root folder. To get there, type
`cd` followed by a space, drag the project folder from Finder into Terminal,
then press Return. Run:

```console
python3 TapperWare_Flet/main.py
```

If you normally activate a project virtual environment, activate it first.
Start without `--demo`: Demo accepts recordings, not a live camera.

### 3. In the GUI: select the camera

- Model: **SENSE TOUCHSCREEN**.
- Panel: **superiore** (upper).
- Under **1. Camera and detection results**, source: **Bridge HTTP camera SENSE**.
- **Camera address**: `http://PI_IP:8080/frame.jpg`, replacing `PI_IP` with the address from step 1.
  For example, if the Pi reports `192.168.1.210`, enter
  `http://192.168.1.210:8080/frame.jpg`.
- Leave the **calibration model** and **independent context** fields empty.
- Click **Start camera**.

You should see a recent camera picture and a separate annotated picture showing
the detected monitor/buttons. The annotation may update more slowly than the camera.
This first check sends no robot commands. Leave **Connetti / ACK**,
**Inizializza hardware** and **Avvia sequenza** unused.

### 4. Finish, or report what went wrong

To finish, click **Stop camera**, wait for it to stop, and close the GUI.
In the Pi camera terminal, press **Ctrl+C**.

If it fails, keep the exact error message:

- Python/module/Tesseract error: check the installation section below.
- Camera busy: close the other camera app, then restart the camera command.
- No picture/connection error: check that both computers are on the same network,
  the Pi terminal is still running, and the GUI URL uses the Pi's actual address.
- Picture visible but missing/wrong detections: note the screen shown and save
  the error or a useful image. Stop observation before restarting it.

For this first check, **no robot JSON, calibration JSON or movement-limit JSON is
needed**. Once the camera check works, proceed separately through robot connection,
calibration and movement limits using the details below. Then select a detected
button and explicitly confirm one short press; move-only testing is optional.

<details>
<summary>Detailed setup and robot testing — open when needed</summary>

## Office hardware test procedure (Step 15)

Use this procedure for the **upper SENSE TOUCHSCREEN / superiore** only, one
camera per session. It describes the implementation based on `68196f6`; later
sections describe earlier milestones and historical features. This procedure
takes precedence where those sections still say that Steps 13/14 are deferred.
Preparation and offline checks do not establish physical validation or authorize
Step 16 changes. TWIN detection remains frozen; do not use a SENSE fit on TWIN.

The current office commissioning addition is documented above; the remaining
milestone sections retain their historical scope. Observation and calibration collection are available;
ordinary physical vision movement is unavailable. Restricted, independently bounded
right-button commissioning MOVE is implemented but physically unverified. All
box-16 holds are **fake-transport simulation only**. A real right-button press
requires the new measured commissioning sequence above; connecting, checking a
flag or loading a rejected fit cannot enable it. Existing recorded fits fail the unchanged 3 mm maximum and cannot
authorize even commissioning. Legacy static XML can move/press real hardware under
its separate confirmation; leave it unarmed throughout the vision trial.

### Prepare the PC and Pi

Keep the complete repository, including shared packages, English OCR data and
tracked `dmi_computer_vision/data/icons/` assets. Run module commands below from
the repository root in separate terminals. Record `git rev-parse HEAD` and
`git status --short` on both machines; deploy matching reviewed runtime sources.
Do not use the older master GUI or `dmi_robot_general` as another backend.

On the PC, use Python 3.13 (the offline test environment), or separately validate
another supported Python >=3.10. On macOS/Linux create a new virtual environment:

```console
python3 -m venv .venv
```

On Windows with the Python launcher, create it with
`py -3.13 -m venv .venv` instead. Activate with `source .venv/bin/activate` on
macOS/Linux, or `.venv\Scripts\Activate.ps1` in Windows PowerShell. If activation
is unavailable, use `.venv\Scripts\python.exe` in place of `python` in the PC
commands below. Then:

```console
python -m pip install -r TapperWare_Flet/requirements.txt
python -m pip check
python -c "import cv2, numpy, flet, PIL, yaml; print('PC imports OK')"
tesseract --version
tesseract --list-langs
python TapperWare_Flet/main.py --demo
```

Install Tesseract using the PC's managed OS installer and put its executable on
PATH; `--list-langs` must include `eng`. Keep the matching shared library available
for the existing SENSE C-API acceleration; CLI fallback may be slower. Flet's native
desktop client must be available (Linux native file dialogs also need Zenity).
The pinned Python requirements are the deployment request, not a claim that a
fresh installation or native window has been validated on the office PC. Record
`python --version` and `python -m pip freeze` after installation. Browser preview
is Demo-only. Do not install Pi GPIO/camera packages on the PC.

On the Pi, use the existing Raspberry Pi OS camera/GPIO environment. It must provide
`picamera2`, `libcamera`, `lgpio`, `cv2`, `numpy` and `yaml`; Picamera2/libcamera must
match the installed OS camera stack. Have the office maintainer provision missing
OS packages before continuing; the PC requirements are not a Pi camera installer.
Run this import-only check with the same Pi interpreter used for the commands below:

```console
python3 -c "import picamera2, libcamera, lgpio, cv2, numpy, yaml; print('Pi imports OK')"
```

This check does not open a camera, claim GPIO or test motors. Record the Pi OS,
Python/package versions and selected libcamera mode from the later bridge startup.
No Pi installation, native GUI layout or actual device operation was verified here.

### Set deployment values before starting hardware

Copy these portable examples into ignored, durable `dmi_robot_config/local/`
with unique session names when preparing a new setup. The robot connection file
on this Mac is already configured and loads automatically; it needs no copying or
path entry for normal use. Never use `/tmp` as the only calibration copy:

- [gui_robot.example.json](../dmi_robot_config/gui_robot.example.json): GUI UDP
  `address=[PC IPv4, PC listen port, PC protocol ID]`,
  `remote_address=[Pi IPv4, Pi listen port, Pi protocol ID]`, measured positive
  integer `xy_limits_mm` (upper bounds exclusive), finite `timeout_seconds` in
  `(0,120]`. Use decimal protocol IDs in JSON. Choose timeout from the independently
  assessed homing/travel duration; timeout is not a motor stop.
- [guided_calibration.example.json](../dmi_robot_config/guided_calibration.example.json):
  independent camera identity/mount, origin/axes, panel/tool/contact-center convention
  and the same measured XY limits. For the bridge use `source_kind="remote_bridge"`
  and add the actual full `bridge_url` under `camera.settings`. Retain receiver
  `rotation_clockwise=0`, no mirror/crop. Record actual native `original_size` in settings
  as `[width,height]`. For a local camera use `source_kind="local_camera"`,
  `camera_index` and `requested_size=[null,null]`. Calibration XY are absolute mm;
  include the measured panel/tool offset once, never add the XML GUI Y offset again.
- [commissioning_envelope.example.json](../dmi_robot_config/commissioning_envelope.example.json):
  fill only after independent physical measurement. Camera/mount/origin/axes must
  match the candidate. Minimum/maximum XY describe an inclusive safe rectangle;
  both corners must be inside exclusive robot limits. Declare a conservative
  maximum single-move distance and measurement basis. Never derive bounds from a fit.
- [office_trial.example.json](../dmi_robot_config/office_trial.example.json): manual
  checklist, measurements and problem record, described below. It is not loaded
  by the GUI and cannot authorize any action.

The Pi receiver currently reads **only**
`dmi_robot_config/raspberry_cfg.yaml` beside the deployed repository; it has no
config-path argument and does not read a copy in `local/`. Back up the deployed
file into durable local storage, then have the operator set its actual network
tuples and independently verified GPIO assignments on the **Pi deployment**.
Pi `address` must equal GUI `remote_address`, and Pi `remote_address` must equal
GUI `address`, including protocol IDs. Existing IDs are `0xAAAA=43690` (Pi) and
`0xBBBB=48059` (PC); confirm them against the deployment. Do not copy historical
IP addresses as current truth. The old YAML PC ports include 50, which may require
privileges; agree usable matching ports on both ends rather than elevating the GUI
by default. Allow the configured UDP pair and camera TCP port through the local
firewall. Flet does not use `TapperWare_Flet/pc_cfg.yaml` for communication now.

The receiver also contains nominal `_X=380`, `_Y=470` limits in
`dmi_robot_rasp/DmiRobot.py`. Those constants are not measurements. If they conflict
with measured travel, stop hardware motion and report the discrepancy; do not
increase bounds or edit motor code to get through this trial.

### Start with observation, then communication

1. Inspect the physical stop/power isolation, retracted tool, homing path, sensors,
   travel and camera/tool mount with the office operator. Do not home with an
   unverified stop or unsafe path. Close other UDP command clients (`run_robot.py`,
   old GUIs/master scripts) and camera owners. The bridge alone owns camera 1.
2. Start the Pi camera bridge in its own terminal, replacing `PI_LAN_IP` below
   with the actual interface IPv4 address:

   ```console
   python3 -m dmi_robot_master.integration.frame_bridge --bind PI_LAN_IP --port 8080 --backend picamera2 --camera 1 --width 2304 --height 1728 --frame-fps 10
   ```

   These are requested settings: 30-FPS sensor capture, continuous autofocus,
   -2 EV, source rotation 180 degrees, and a 10-FPS JPEG publication cap. Save the
   startup `capture_settings` output and verify actual selected mode, resolution,
   focus and upright image. Camera index selects acquisition, never screen identity.
   Receiver rotation stays zero; do not rotate the GUI image a second time.
3. Launch `python TapperWare_Flet/main.py` on the PC (without `--demo` or `--web`).
   Select **SENSE TOUCHSCREEN**, **superiore**, **Bridge HTTP camera SENSE**, enter
   `http://PI_LAN_IP:8080/frame.jpg`, leave model/context empty initially and press
   **Start camera**. Starting observation sends no robot commands. Check
   the annotated frame and, under **Live camera image**, the raw frame, monitor division,
   identities, native-pixel centers and age. Preview images are scaled for display;
   do not measure original pixels from their screen size. The GUI should remain
   responsive while analysis runs. No receiver is needed for this observation test.
4. With robot motion still unarmed, briefly stop/restart the bridge. Verify stale
   targets/annotations clear (1.5-s evidence lifetime plus UI scheduling) and report
   errors. Stop the old observation and wait for its workers before explicitly
   restarting; no automatic recovery is assumed. Do not test a network interruption
   during physical motion. A stale/lost target must never remain action authority.
5. Once the independent physical preflight is complete, start the Pi receiver in
   another terminal: `python3 -m dmi_robot_rasp.DmiControllerSlave`. This claims GPIO;
   it is hardware-capable. Leave **Custom robot configuration (optional)** empty
   to use the saved setup; enter a file only for an override. Press **Connetti / ACK**,
   then **Controlla ACK** and **Leggi XY controller**.
   Connect checks communication only; confirm it does not home/move. No response:
   check endpoint reversal, IDs, firewall, bind permissions and sole UDP ownership.
   Do not repeatedly send motion to diagnose communication.
6. **Inizializza hardware** requires explicit confirmation of all five checks:
   measured XY limits, independently retracted Z, available physical stop, clear
   homing area and verified origin/mount. INITIALIZE moves axes. Observe it in
   person. DONE and controller XY are internally calculated completion/position,
   not independent alignment, retraction or contact proof. Connection/homing changes
   invalidate calibration drafts/mappings; start collection only after this origin.

### Collect calibration and try one commissioning move

Enter the independent context path in the Vision card (stop/restart observation
to change source/model/context fields). Choose **Nuova raccolta**, select a fresh
measured right button or confirmation field, enter independently measured absolute
XY and confirm its visible center. Use at least five distinct spread-out fit
controls plus one or more different held-out controls; prefer additional reliable
digits/wider controls. Repeated frames or references at one physical location do
not add coverage. Collection sends no movement. If safe independent metrology is
unavailable, record calibration as blocked and continue observation only.

Use **Confronta fit / residui**, inspect each held-out and leave-one-control-out
error and compare affine/homography. Every required error must meet the maximum
3 mm (or stricter) limit. Record outliers rather than forcing a fit or dropping
them silently. Wrong measurements need independent recollection. **Salva candidato**
uses a new durable local filename; back up points, context and candidate separately.
Restart observation with that candidate and matching independent context on the
same connected/homed origin. A mismatch or source/geometry/origin change requires
reassessment, not copied verification flags. Save complete candidates before
changing context; incomplete drafts are memory-only.

A numerical pass still saves `hardware_verified=false`, `action_usable=false` and
no physical coverage. It does not unlock general ordinary movement. The limited
initial-test press workflow above uses a numerical pass plus the existing action
guards and explicit operator readiness; rejected fits stay blocked. Current
recorded fits reject 3 mm; use them for inspection only. Out-of-hull left box-14/16
XY estimates have unverified error and cannot authorize physical movement.

For an optional move-only test, after an adequate new fit **and independently measured envelope/start/path/
retraction/stop** are available, enable **Commissioning: solo allineamento con limiti
indipendenti**, enter the envelope path and select one represented right button
inside the fit hull. Fields, left targets, missing/uncertain/inactive controls are
ineligible. Press **Verifica e prepara un movimento**; inspect predicted and rounded
XY, Z=0, error and bounds. Complete the five checks for this one action or cancel.
The 30-s single-use intent does not extend 1.5-s direct evidence; confirmation
rechecks identity/source/geometry/context/files, ACK, controller start and bounds.
It sends one MOVE only, without press, retry or return. Independently measure the
physical tool alignment and record signed actual-minus-requested XY and measurement
uncertainty before preparing another move. Requested Z=0 and DONE do not prove
retraction or physical accuracy. Rejected fits or failed guards mean **no move**.

For one physical short press, use the current workflow at the top of this README.
No preceding move-only action or per-button alignment form is required. Physical
five-second holds remain deferred; no mode acknowledgement is implemented here.

### Record the trial and finish safely

Copy `office_trial.example.json` into the session's ignored local directory. This
is a **manual blank form**, not a runtime schema or generated validation report.
Fill session identity, source revision, actual settings and artifact paths/hashes;
use ISO-8601 times with timezone. Checklist entries start `not_run`; set `pass`,
`fail` or `blocked` with an evidence reference and reason. Record each physical
measurement's method/uncertainty separately from simulated results or declarations.
Set each coordinate row's `evidence_kind` to `measured_physical`,
`operator_declaration`, `simulated` or `recorded` as appropriate. Duplicate
measurement/problem rows as needed. Unknown values stay null.

For a short fixed observation interval, record the GUI's analysis FPS, mean/P95
seconds, overwrite count and visible age samples; record interval length/screen/
lighting and cold/steady/transition condition. FPS/mean cover the observer session;
P95 uses its last at most 256 analyses. Restart observation for a comparable window.
Agree required responsiveness and independent center-error tolerance with the operator
before testing; no detection FPS is promised. Keep the fixed 1.5-s evidence expiry
and maximum 3 mm calibration criterion even if throughput is insufficient.
GUI FPS is not capture, bridge publication, paint or MP4 playback FPS. Age includes
available upstream age and round-trip allowance, not independently measured full
sensor-to-display latency. GUI does not expose age P95, OCR time/calls or policy
skip totals; leave those null unless a separate instrumented run supplies evidence.
For transition latency record the event and first correct current observation in
the same timed recording/clock, plus confirmed-state delay separately; otherwise
mark latency unmeasured. For coordinate problems record native frame index, region,
screen/label, expected independent center and observed pixel/XY, never just a crop.

Export **Esporta registro** (before 2,000 lines are exceeded). Optional **Log JSONL
diagnostico** appends full detection results to
`dmi_robot_config/local/vision_debug.jsonl`; it does not record raw video or complete
latency metrics and adds I/O cost. Enable only for a specific problem, record its
effect on the timing configuration, then stop observation before copying that log
to a uniquely named session artifact. Do not truncate older logs.

For missing natural transitions/TRN/blinking evidence, stop GUI observation and
keep robot commands idle; record a separate unannotated bridge trial from the PC:

```console
python -m dmi_robot_master.integration.record_raw --bridge-url http://PI_LAN_IP:8080/frame.jpg --output-dir runs/office_SESSION_raw --seconds 30 --request-fps 10
```

Replace `SESSION` with a unique name; the directory must not exist. Navigate the
DMI manually using an approved office procedure, never by an autonomous sequence.
Keep `raw.mp4`, `processed_frames.jsonl`, `session.json` and first/last PNGs together,
unchanged. Native resolution is retained; actual receipt cadence/sidecars, not
10-FPS encoding, determine timing. This separate acquisition is not a GUI performance
measurement. Do not copy source recordings into every experiment or overwrite
accepted evidence. No additional debug-frame exports are required.

On any uncertain motion, sensor/contact or stop failure, use the independently
established physical safe-stop/isolation procedure, record the fault and end motion
testing. GUI **Arresta**, timeout, disconnect and Ctrl+C cannot guarantee stopping a
blocking receiver motor routine. Never queue retries or a recovery return-to-origin.
For normal shutdown, wait for the current bounded transaction, **Stop camera**
and wait for workers, export logs/save complete candidates, **Disconnetti**, then
close the GUI. A still-active operation can prevent normal close; do not start a
second owner. With motion physically safe and no active command, Ctrl+C the Pi
receiver and bridge, then use the office power-down procedure. Software process
exit does not certify tool retraction or motor-power isolation. Back up ignored
local records/calibrations before any cleanup.

Offline regression commands (local ignored tests must be supplied separately in
a clean clone; no real devices are used):

```console
python -m pip install "pytest>=9,<10"
python -m pytest tests -q
python -m pytest TapperWare_Flet/tests -q
```

Three known GUI fixture failures remain: attached-script reference/50-ms expectations,
empty TWINS-profile expectation and normal-run 50-ms versus current 100-ms default.
Do not alter production coordinates/durations or weaken guards to satisfy them.
The office checklist remains unexecuted: PC/Pi provisioning, native dialogs/layout,
network/camera cadence/focus, natural transitions/TRN/blinks, detection latency and
center truth, calibration accuracy/coverage/conventions, homing/limits/path/stop,
retraction/contact/accounting and actual move/press/hold behavior all need independent
hardware evidence. In particular Step 8 coverage remains open. Software/fake tests
do not turn any of these into physically validated results.

</details>

<details>
<summary>Earlier feature documentation and technical reference</summary>

## Single press and mode hold (Step 14, offline implementation)

Step 14 originally provided explicitly confirmed **simulated** single-button
presses and five-second holds on eligible blinking modes in left `box_16`.
The current live short-press workflow at the top of this README supersedes that
fake-only single-press restriction. Physical five-second holds remain deferred.
Installed-camera calibration, alignment, contact/retraction/sensors and stop
behavior remain unverified until the office test. The pre-existing static XML workflow keeps its separate
accepted safety/observation controls; it does not consume vision calibration.

Use Demo with the shared fake robot initialized, one SENSE upper-panel source,
a numerically adequate guided candidate collected on that origin, its matching
independent context and the independently declared envelope used for move-only.
All current recorded candidates still fail 3 mm and remain blocked. A saved
candidate is never promoted: `hardware_verified=false`, `action_usable=false`, no
physical coverage. Positive offline cases use synthetic images/correspondences;
those fixtures and tests are local/ignored, not production runtime dependencies.

Select one current right-region measured button and enable simulated pressing.
**Simula una pressione** prepares a 100 ms request (the current SENSE reference
default). For **Simula hold box 16**, select the detected left box; the same known
mode must be confirmed blinking and directly visible there, with power directly
visible in box 14. A retained blink-off identity cannot authorize the hold.
Only the box-16 hold is added on the left; other left/field actions stay unavailable.

Inspect the prepared pixels, predicted/rounded absolute XY, duration, selected mode
and independent bounds, then complete all eight simulation readiness checks for
that single action. Cancel sends nothing. Each intent is single-use and expires
in 30 s; the 1.5-s direct-evidence limit is unchanged. Preparing either a move or
press invalidates any other pending action. Source/session/origin/selection, file,
mode-history or measured-box changes invalidate old confirmations.

The existing command owner checks ACK and internally calculated controller XY,
reloads/revalidates the fit and independent bounds, checks current direct evidence
and sends exactly one `MOVE_AND_CLICK [X,Y,100]` or `[X,Y,5000]` to fake hardware.
Both floating/rounded destination, start point and displacement must fit the bounds.
No retry, return motion or multi-screen sequence follows. Busy input is rejected.
Cancellation retains ownership until the bounded command outcome; detection and
rendering continue while the command and read-only verification are pending.
The fake robot acknowledges immediately: checking a 5000 ms payload does not prove
five seconds of real contact. Real command timeout, travel and retraction timing
remain deployment/hardware work; no existing timeout or calibration limit is relaxed.

A normal button's DONE remains **unconfirmed**. After a mode hold, verification
uses only new source evidence later than DONE, accounting for upstream age. It
requires at least three distinct frames spanning 0.8 s, the same mode steadily in
box 14 replacing power, and a measured empty box 16. The existing mode history must
retain the original power/blink lineage and its reset epoch; loss, ambiguity,
geometry changes, different modes or invalidated history cannot confirm success.
Buffered/pre-completion frames and repeated reads of one frame do not count.
Verification times out after four seconds without sending another command.
`observed_mode_transition` reports camera evidence, not contact, physical accuracy
or proof the robot caused the UI change. Communication/motion uncertainty revokes
readiness and closes the shared owner; unavailable/ambiguous camera feedback keeps
the outcome unconfirmed. GUI Stop cannot interrupt a blocking receiver motor call.

The SENSE inspector also predicts XY for detected boxes 14/16 with the existing
chosen affine/homography model. These remain explicitly unverified, including when
outside the fit hull. Extrapolated box centers never authorize these simulated
presses: an adequate fit and in-hull point are required. Current Driver02 left-box
estimates are outside the keypad hull and cannot press. TWIN/core detector outputs
are unchanged; only opt-in SENSE mode-history reset metadata is added. Natural
blinking footage, native Flet window layout and all physical validation stay pending.

## Selected-target move-only commissioning (Step 13, offline implementation)

Select a current detection in the SENSE upper-panel Vision card to inspect native
pixels, predicted absolute robot XY, result age and calibration status. Ordinary
vision-guided movement remains unavailable: Step 12 candidates retain
`hardware_verified: false`, `action_usable: false` and no physically validated area.
The existing rejected recorded fits cannot move the robot, including commissioning.
No pressing or mode-icon hold is added by this step. Physical validation is pending.

An explicit commissioning-only path can make one operator-confirmed MOVE using a
numerically adequate guided candidate and independently established movement bounds:

1. Configure measured travel limits and the shared robot connection, inspect ACK,
   and complete the existing explicit homing/readiness procedure. For offline work,
   use Demo/fake transport. A recorded source cannot drive a hardware-mode session.
2. Collect and save a guided SENSE candidate after this homing origin. It must pass
   the unchanged maximum 3 mm criterion with independent held-out controls. Load it
   and its matching context in a new observation session on the same origin.
   Do not alter verification flags or replace reference coordinates to obtain a pass.
3. Copy `dmi_robot_config/commissioning_envelope.example.json` into ignored
   `dmi_robot_config/local/`. Fill independently measured inclusive minimum/maximum
   absolute XY, maximum single-move distance, measurement basis, camera identity/
   mount and origin matching the candidate. Both rectangle corners must be inside
   the exclusive configured robot travel limits. No physical defaults are supplied.
   Never derive this envelope from the fitted image/calibration coordinates.
4. Select a currently recognized right-region button represented in the collected
   controls and inside the fitted control hull. Inactive/uncertain marked buttons,
   fields, left controls and unmeasured identities remain inspection-only here.
   Enable commissioning explicitly, enter the envelope path, and prepare a move.
5. Inspect the dialog's current pixels, predicted XY, whole-mm command (nearest mm,
   half upward), model/error and independent envelope. Absolute coordinates already
   include the declared panel/tool convention; the XML panel Y offset is not added.
   Independently verify the tool is retracted, start position is inside the envelope,
   path is clear, physical stop is available, and bounds are independently measured.
   Confirm all five checks for this single movement, or cancel.

Preparation sends no packets. Confirmation is single-use and expires after 30 s;
this does not extend the unchanged 1.5-s direct-evidence limit. The same command
worker checks ACK, reads internally calculated controller XY, reloads the model and
bounds, and resolves the selected identity again from the latest direct evidence
before sending exactly one validated `MOVE [X, Y, 0]`. Both current predicted/rounded
XY and the start position must be inside the independent rectangle, and displacement
must not exceed its maximum. The rectangle contains the straight XY path only if
the declared start is physically correct; controller XY is not independent proof.
Source/session/origin changes, model/bounds edits, stale evidence, mismatched direct
screen evidence or changed coordinates invalidate the intent. Prepare again after
any rejection. A second request is rejected while busy, rather than queued.

No press, automatic retry or automatic return-to-origin follows this command.
A communication/motion failure revokes homing and closes the shared connection;
a pre-send guard rejection sends no MOVE. Detection/rendering continue independently.
The receiver's existing retraction routine and requested Z=0 do not prove physical
retraction: verify it independently before operation. GUI Stop cannot interrupt a
blocking receiver motor routine. DONE is protocol completion, not alignment, contact
or successful DMI input. Native layout, real camera/robot behavior, independent
calibration accuracy and physical alignment remain unverified. The legacy static
XML/photo workflow retains its separate confirmation and observation exclusion.

## Shared robot communication and guided calibration (Step 12)

Step 12 implements the software workflow offline. Hardware commissioning, measured
alignment and physical verification are still pending. Start with
`python TapperWare_Flet/main.py --demo`. **Connetti / ACK** in Demo uses the existing
fake master/slave transport, opens no UDP socket and declares synthetic 1000 ×
1000 mm bounds. These are simulation bounds, never a physical setup. Initialize
Demo, inspect controller responses and disconnect to exercise ownership/cleanup.
Ordinary Demo XML and photo-file viewing remain available.

For a new office deployment, copy `dmi_robot_config/gui_robot.example.json` into
ignored `dmi_robot_config/local/gui_robot.json` and configure the deployed local/
remote IPv4, UDP port, protocol ID and positive integer XY limits in mm. The setup
on this Mac has already been saved from the user-selected PC YAML and coded limits;
verify those bounds independently before homing. Upper bounds are exclusive. IDs must match the existing
Pi protocol (JSON uses decimal integers). Configure a finite timeout of at most
120 seconds appropriate for homing. No deployed IP, port or travel limit is inferred.
The legacy adjacent `pc_cfg.yaml` is no longer the Flet communication source.
Do not run another robot-command client, including `run_robot.py`, alongside this
GUI session. HTTP camera acquisition is a separate protocol and may keep running.

Launch without `--demo`, leave the optional configuration path empty to use the
saved local setup, and press **Connetti / ACK**. Enter a path only for an override.
Connection sends ACK only; it does not home or move. **Controlla ACK** explicitly
rechecks communication. **Leggi XY controller** queries the controller's internally
calculated XY; that is not independent physical alignment or contact evidence and
is never copied into calibration points automatically. The adapter uses the common
protocol, validated RobotCommands/RobotLink and one serialized command worker.
Disconnect before changing connection settings or environment.

**Inizializza hardware** opens a new confirmation dialog. Independently inspect
travel limits, retracted Z/tool, physical stop, clear homing area, origin and mount,
then acknowledge each item and explicitly confirm homing. INITIALIZE can move the
axes. ACK is checked again before it is sent. DONE records controller completion;
it does not establish physical accuracy, calibration validity or press readiness.
Reported checks are operator declarations, not measurements generated by software.
Timeout, ERROR, send failure, malformed response or disconnect revoke readiness;
there is no automatic initialization/motion retry or recovery parking.

Camera preview/detection run independently of the command worker. Connecting,
disconnecting or homing clears previous mm mappings and the calibration draft;
pixel observation can continue. An in-flight command is not canceled on disconnect:
bounded completion is awaited and the same owner then closes its socket. GUI Stop
is not a physical emergency stop and cannot interrupt a blocking Pi motor routine.
The existing static-coordinate XML workflow remains available only after stopping
observation, completing homing/readiness checks and explicitly confirming legacy XML
mode for that run. It uses database coordinates and the existing panel Y offset;
it never consumes a vision target or a calibration model. The entire plan is checked
against configured bounds before any XML movement is sent. TAKE/GET photos also
require stopped observation and use this same shared UDP owner, writing to the GUI
photo folder. A camera ERROR keeps known homing; a communication failure revokes it.
These preserved functions have only been tested with fake hardware here. New
vision-selected Move and Press remain deferred to Steps 13/14; rejected or unverified
calibrations authorize no vision actions.

For calibration, copy `dmi_robot_config/guided_calibration.example.json` into ignored
local storage and fill independent camera identity/settings/mount revision, robot
origin/axis convention, absolute panel/tool/point conventions and measured XY limits.
Set `camera.source_kind` to the actual source. Recorded identity is
`simulation:` followed by the absolute video path. Bridge settings require the
actual `bridge_url`; local-camera settings require `camera_index` and
`requested_size` (the GUI currently requests `[null, null]`). Preserve receiver
rotation 0, no mirror and no crop. Record original frame size in settings when known;
the workflow also stores actual native dimensions. `conventions.coordinates` must
remain `absolute_robot_xy_mm`. Include the panel/tool offset exactly once in the
independently measured XY; do not add the GUI panel Y offset again.

Enter this independent context path in the Vision panel, start one SENSE source,
then choose **Nuova raccolta**. The image must supply measured joined SENSE regions;
TWIN geometry is rejected. Choose a currently recognized button/confirmation field,
enter independently measured absolute X/Y and confirm the visible center/measurement
for each point. The collector re-resolves the selected identity from the latest
observation, checks direct right-button/field evidence and the unchanged 1.5-second
age limit, records source/session/origin metadata and rejects geometry/session changes.
Do not enter predictions from the fitted model as independent measurements.
No robot motion occurs during collection; use independently established safe
measurement procedures outside this GUI until the move-only step is available.

Use at least five distinct, spatially distributed **Punto di fit** controls and at
least one different **Controllo tenuto fuori dal fit**. Prefer more reliable digits
and wider controls rather than repeated frames of one physical location. Duplicate
identities, pixels or physical XY do not add coverage. Compare affine/homography
residuals: fit controls report leave-one-control-out errors, and check controls stay
outside fitting. The simplest model must meet every independent error/outlier check.
The provisional maximum remains 3 mm; a smaller numerical tolerance is allowed.
Rejected fits remain diagnosable and savable; no points are silently dropped. Remove
and independently recollect an incorrect point, or start a new draft when the source,
origin or conventions change. Editing points invalidates the previous fit.

**Salva candidato** writes schema 3 with all points, context, matrices, residuals,
fit hull and a content hash. Use a new durable local filename; temporary directories
and overwrites are rejected. A numerical pass always retains
`hardware_verified: false`, `action_usable: false` and no physically validated area.
No checkbox or edited verification flag can promote this schema to an action model.
To inspect predicted XY, restart observation with the saved model and matching
independent context; source, frame size, geometry and origin must agree. Out-of-hull
predictions are inspection only. Existing executable and Step 10 calibration schemas
retain their original contracts. Back up local measurements/calibration separately;
they are intentionally excluded from Git.

The three existing GUI reference-fixture failures remain documented in STATE.md.
Updated camera/observation tests reflect the intentional shared-owner and hardware
action guards; they do not assert physical camera or motor success. New fake-hardware
and Flet tests cover ACK-only connection, readiness/homing confirmation, errors,
serialization, cleanup, concurrent preview and collection/fit/no-overwrite save.
Native window layout, actual IP/ports, homing/limits/Z/contact/stop behavior,
independently measured held-out mm accuracy and live hardware response remain for
office validation. The older sections below describe historical GUI features;
the Step 12 guards above govern current hardware operation.

## SENSE live observation (Step 11, offline implementation)

Run this GUI from its place in the complete repository; the vision and integration
packages and `dmi_computer_vision/data/icons/` are required. Install
`python -m pip install -r TapperWare_Flet/requirements.txt` in the same environment.
The existing OCR engine (Tesseract with English data) is also required; see the
vision package README. Launch from any directory using an absolute path:
`python /path/to/DMI_R-D_ALTEN/TapperWare_Flet/main.py --demo`.

Select **SENSE TOUCHSCREEN**, panel **superiore**, then enter an absolute recording
path in **Visione SENSE** and press **Avvia osservazione**. Demo/browser accepts
recordings only and never opens a real camera. Replay uses the recording's native
resolution and encoded FPS; playback timing is not camera cadence or a latency
benchmark. The live camera frame and matching annotated detection frame are
separate; slow analysis may leave the former updating while the latter expires.
Results older than 1.5 seconds (including supplied upstream age) lose their targets
and annotation. Stop, EOF, source/analysis failure and model/panel/environment
changes clear observations. Stop workers before starting another session.

For later hardware observation, launch without `--demo`, choose the bridge source
and enter the deployed HTTP(S) `/frame.jpg` URL, or choose a local camera and enter
its acquisition index (SENSE camera 1 on the documented setup). No camera opens
until observation starts. Receiver orientation is unchanged (rotation 0, no mirror);
the bridge must supply correctly oriented frames. Check actual camera identity,
mount/settings and network configuration independently. No live hardware connection
or installed-camera performance has been validated by Step 11.

Optional calibration and independent context JSON paths can be supplied before
starting. Context has `camera` and `origin` objects using the existing calibration
schema. Do not copy a historical model's context as proof of current mounting or
origin. The resolver checks source kind/path or endpoint, size and measured
geometry. The Step 10 rejected models can show mathematically predicted XY only
when replay/context/geometry match; they remain unverified and unusable. Mismatches
show an explicit calibration error and no XY. No GUI panel Y offset is added to
calibrated XY. All Step 11 target selections are inspection only: select again for
the current observation; coordinates in older UI rows cannot authorize movement.
There are no vision Move, Press or Hold controls in this step.

Mode observation uses paired white `modes/box_14` and yellow `modes/box_16`
templates, with `modes/power.bmp` as the default white icon. Identity names such as
`mode_01` refer to the supplied asset pair, not an inferred operational mode name.
Only measured joined-monitor regions are eligible. A bounded time-based history
reports pending, blinking, temporary blink-off, power, steady or unknown. Blink-off
retains its last direct-evidence timestamp; loss, ambiguity, geometry movement or
a capture gap clears history. Steady requires repeated white evidence with an
observed empty yellow box. These states are observations, not acknowledgement or
press success. Natural blinking footage and physical hold verification remain
pending; the five-second hold belongs to Step 14.
`replacement_verified` separately requires the same confirmed blinking identity
and prior direct power evidence, followed by steady white/empty yellow evidence.
Different white identities, reset/loss and expired blink history cannot verify
that replacement. The transition association expires eight seconds after direct
blink confirmation; blink-off never renews it. Geometry is checked against the
history's anchored basis, including cumulative movement.
Power must still be visible when blinking is confirmed. An intervening different
white icon cancels the pending replacement, including a later return to the old
blinking identity.

Runtime communication is bounded in memory; no per-frame JSON transfer is needed.
The optional JSONL debug checkbox appends detailed evaluation results to ignored
`dmi_robot_config/local/vision_debug.jsonl`; leave it off for ordinary observation.
Displayed FPS is local analysis throughput, and P95 covers the latest 256 analyses;
it is not measured camera FPS or GUI paint rate. Source buffers may also overwrite
frames beyond the GUI observer's own overwrite counter.

Step 12 uses one shared command owner for connection, explicitly confirmed homing
and the preserved legacy XML/photo workflow. Pixel observation can continue during
connection/homing; stop observation before legacy XML or photo acquisition. Demo XML
remains simulated. Existing legacy hardware behavior has not been physically
commissioned by this change. Vision-selected movement and pressing are later steps.

Nuova console desktop in italiano: fondo blu scuro, accenti verde menta, pannelli separati per postazione e sequenza, anteprima comandi, avanzamento, tempo trascorso e registro eventi esportabile.

La versione 2.2 aggiunge un monitor animato dell'esecuzione e messaggi operativi
più professionali. Conserva foto automatica, visualizzatore, impostazioni
persistenti e selezione del pannello con offset Y configurabile.

## Avvio rapido

Richiede Python 3.10 o successivo. Apri un terminale nella cartella estratta:

```console
python -m pip install -r requirements.txt
python DmiGUI.pyw --demo
```

In demo, premi **Carica esempio**, **Inizializza demo**, poi **Avvia sequenza**.
`python main.py --demo` è equivalente: entrambi gli avvii standard funzionano
senza l'estensione per il trascinamento.
Su Windows puoi usare anche `Avvia_DEMO.bat` dopo aver installato le dipendenze.
La demo non importa i moduli hardware e non apre connessioni al robot.
La pressione ACK del file di esempio dura 5 secondi anche in demo.

È fissata la versione Flet **1.0.4**. Il codice usa le API di questa versione;
è stata verificata anche la compatibilità con **Flet 0.82.2**. Flet 0.28 non è supportato.
Pillow è incluso nelle dipendenze per leggere e visualizzare le immagini scaricate.

### Aggiornamento alla versione con animazioni

Sostituisci i file dell'applicazione con quelli di questo archivio, includendo
**dmi_activity.py**, **dmi_settings.py**, **dmi_photos.py** e **requirements.txt**.
Le animazioni usano Flet e non richiedono estensioni aggiuntive. Per allineare le dipendenze:

```console
python -m pip install -r requirements.txt
```

Conserva i tuoi moduli hardware, `pc_cfg.yaml`, eventuali modifiche a
`DmiPositions.json` e il file `TapperWare.settings.json`, se già presente.
L'archivio non contiene un file di impostazioni dell'operatore.

### Correzione FilePicker

La versione corretta crea `FilePicker()` senza `on_result`, registra i servizi
nella pagina e carica i file restituiti da `await pick_files()` sul desktop.
Nel browser usa l'evento solo se l'API `PickFiles` è disponibile; altrimenti usa
il selettore asincrono con lettura del contenuto. È compatibile anche il bordo
del menu DMI, la cui API è cambiata tra le due versioni di Flet.

La correzione è inclusa anche in questa versione. Segui le istruzioni di
aggiornamento sopra per includere i nuovi moduli delle foto e delle impostazioni.

### Correzione avvio standard

La prima versione di `main.py` attivava il trascinamento nativo obbligatoriamente.
È stato corretto: ora `main.py` e `DmiGUI.pyw` usano lo stesso avvio standard.
Mantieni aggiornati anche **main.py** e **pyproject.toml**, che rende
l'estensione opzionale.
Anche una richiesta esplicita `--native-drop` con estensione assente lascia
ora aprire la console e segnala di usare **Sfoglia file**.

## Uso con il tuo progetto hardware

Copia nella cartella del progetto questi file:

- `DmiGUI.pyw` — nuovo punto di avvio, sostituisce la GUI Tkinter.
- `dmi_gui.py` — interfaccia Flet.
- `dmi_runtime.py` — validazione XML ed esecuzione dei comandi.
- `dmi_settings.py` — opzioni e offset per pannello.
- `dmi_photos.py` — attesa del download, lettura e anteprima foto.
- `dmi_activity.py` — monitor animato dell'esecuzione.

Installa le dipendenze di `requirements.txt` nello stesso ambiente Python usato dal progetto.
Devono rimanere disponibili i tuoi moduli originali e le loro dipendenze:

```text
YamlCfg.py
ComProtocol.py
Logger.py
DmiMessages.py
DmiControllerMaster.py
pc_cfg.yaml
DmiPositions.json
```

Questi moduli e la configurazione YAML non erano allegati e non sono stati ricreati.
`DmiPositions.json` e `test.xml` nel pacchetto sono copie inalterate degli allegati.
I percorsi di JSON e YAML vengono risolti dalla cartella dell'applicazione,
indipendentemente dalla cartella dalla quale viene lanciato Python.

```console
python DmiGUI.pyw
```

Puoi anche usare `Avvia_HARDWARE.bat`. L'avvio predefinito è in modalità hardware;
se manca un modulo o il controller non risponde, viene mostrato un errore.
Il programma non passa automaticamente alla demo.

La connessione viene creata quando premi **Inizializza hardware**.
Sono conservate le chiamate originali a `ComProtocol`, `DmiControllerMaster.Action`
e `manage_action`, con gli stessi messaggi ACK, INITIALIZE, MOVE e MOVE_AND_CLICK.
La comunicazione gira su un solo worker dedicato: le chiamate sono seriali e
la finestra rimane disponibile durante le attese del controller.

## Monitor animato dell'esecuzione

Il riquadro **Monitor esecuzione**, sopra l'elenco dei comandi, mostra:

- Cursore animato su una griglia, con spostamenti fra le coordinate richieste e
  impulso visivo durante l'invio dei comandi di pressione.
- Step attivo, destinazione, dettaglio operativo e avanzamento a segmenti.
- Indicazione delle fasi di inizializzazione, posizionamento, pressione, attesa,
  rientro, acquisizione e ricezione della foto.
- Scansione animata durante l'acquisizione e il download; conferma visiva
  del completamento solo al termine dell'operazione.

La riga dello step in corso presenta un indicatore di attività e una transizione
di colore; alla conferma del controller mostra un segno di spunta. Un indicatore
rimane visibile anche nella barra dei comandi in basso. Arresto ed errore
terminano gli indicatori di esecuzione.

La griglia è uno **schema dei comandi richiesti**, adattato alle coordinate della
sequenza, incluso l'offset del pannello. Non è una misura o una simulazione
cinematica della posizione reale. Gli impulsi sono un riscontro visivo del
comando inviato, non una conferma fisica di contatto con il pannello.

Le animazioni usano transizioni native di Flet e un aggiornamento grafico
separato dalla comunicazione. Non aggiungono pause ai comandi né cambiano
coordinate, durate, ordine delle chiamate o gestione dell'arresto. Durante le
animazioni vengono aggiornati solo il monitor e gli indicatori, senza
ridisegnare l'intera tabella a ogni fotogramma.

I messaggi della console sono stati uniformati: **In attesa di una sequenza**,
**Sequenza validata**, **In corso**, **Eseguito**, **Operazione completata**.

## Foto automatica e impostazioni

Apri **Impostazioni** dall'ingranaggio in alto a destra e indica la cartella
in cui il tuo `GET_PICTURES` scarica le immagini. Puoi scrivere il percorso
oppure usare **Scegli cartella** sul desktop. I percorsi relativi vengono
risolti rispetto alla cartella dell'applicazione.

La GUI usa il percorso per cercare i file: la destinazione effettiva di download
rimane gestita dai tuoi moduli `DmiControllerMaster` / `ComProtocol`, che non
erano allegati. Non viene modificata una configurazione di download sconosciuta.

Alla fine di ogni sequenza XML riuscita, **dopo il rientro all'origine**, vengono
eseguite in ordine queste chiamate, sullo stesso worker dei movimenti:

```python
dmi_controller.manage_action(
    DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0, 1, 1], DmiMessages.DONE, 0)
)
dmi_controller.manage_action(
    DmiControllerMaster.Action(DmiMessages.GET_PICTURES, [], DmiMessages.PICTURE)
)
```

L'esito viene verificato dopo ciascuna chiamata. Se TAKE_PICTURES fallisce,
GET_PICTURES non viene accodato. Una sequenza arrestata o con errore di movimento
non avvia l'acquisizione.

Prima dell'acquisizione viene registrato lo stato della cartella. Dopo
GET_PICTURES la GUI attende una foto nuova o modificata, sceglie la più recente
per data di modifica e verifica che sia stabile e leggibile. Sono supportati
JPEG, PNG, BMP, GIF, WebP e TIFF; è prevista anche la sovrascrittura dello
stesso nome file. L'anteprima viene ridimensionata, mentre il file scaricato
resta invariato.

La foto si apre automaticamente in una finestra con la scritta
**Operazione completata** e rimane nel riquadro della console. Facendo clic
sull'anteprima la puoi riaprire. Il pulsante **Apri ultima foto** apre invece
manualmente l'immagine più recente già presente nella cartella.

Nelle impostazioni puoi modificare anche il tempo di attesa del file
(predefinito 15 secondi, da 1 a 120) e abilitare la ricerca nelle sottocartelle.
Il tempo di attesa inizia dopo il ritorno di GET_PICTURES; il timeout di
`manage_action` continua a dipendere dal tuo controller.

Se la foto non arriva, non viene mostrata una vecchia immagine come risultato:
la console segnala **Sequenza eseguita · foto non disponibile**. Un problema
della sola fotocamera non invalida l'homing già confermato. Se non hai ancora
configurato la cartella, i comandi foto vengono comunque eseguiti e il programma
ti invita a impostarla per aprire l'immagine.

In demo i due comandi sono simulati. Se nella cartella c'è già una foto, viene
mostrata con l'indicazione **DEMO · foto esistente**; non viene dichiarato un
download reale e non viene creata una falsa foto del collaudo.

## Pannello superiore / inferiore

Il menu **Pannello** si trova nella sezione Postazione. Nelle Impostazioni scegli
il valore dell'offset Y in millimetri (intero, anche negativo) e quale pannello
deve riceverlo. L'altro pannello mantiene X e Y del JSON.

Poiché la richiesta originale indicava due volte «inferiore», l'associazione
è configurabile. I valori iniziali sono:

| Pannello | X | Y |
| --- | --- | --- |
| Inferiore | X del JSON | Y del JSON |
| Superiore | X del JSON | Y del JSON + offset |

L'offset iniziale è **0 mm**. Puoi invertire l'associazione con **Applica l'offset a**.
Il cambio pannello o offset ricompila l'anteprima della sequenza: l'offset si applica
ai movimenti di PRESS, MOVE_TO e WRITE_T9; durate e coordinata X restano inalterate.
Il comando finale di rientro resta sempre `MOVE [0, 0, 0]`.

Cartella, offset, associazione e pannello selezionato vengono salvati in
`TapperWare.settings.json` accanto all'applicazione, senza riscrivere
`DmiPositions.json`. Queste opzioni sono bloccate durante l'esecuzione e
l'acquisizione delle foto.

## Funzioni

- Selezione di SENSE TOUCHSCREEN, SENSE SOFTKEY, TWINS e STEN.
- Selezione del pannello superiore/inferiore con offset Y persistente.
- Acquisizione foto a fine sequenza, attesa del download e visualizzazione automatica.
- Segnalazione delle mappe mancanti. Nel JSON fornito è configurato solo SENSE TOUCHSCREEN.
- Selezione XML tramite finestra nativa e caricamento rapido di `test.xml`.
- Validazione dell'intera sequenza prima di abilitarne l'esecuzione.
- Anteprima con azione, tasto, coordinate, durata e stato di ogni comando.
- Indicatore di avanzamento, conteggio dei comandi completati e cronometro.
- Monitor animato di movimenti, pressioni, step e acquisizione fotografica.
- Visualizzazione delle ultime coordinate **richieste**: non sono una misura della posizione reale.
- Registro con 160 righe visibili e un massimo di 2.000 righe esportabili in `.log`.
- Blocco di modello, ambiente, file e inizializzazione durante le operazioni.
- Arresto da pulsante o tasto **Esc**.
- Blocco della chiusura ordinaria della finestra finché un'operazione è in corso.
- Layout a due colonne sulle finestre ampie; colonne impilate quando lo spazio si riduce.

## Comportamento di arresto ed errore

**Arresta è un arresto della sequenza, non un arresto di emergenza dei motori.**
Non è disponibile, negli allegati, un comando di interruzione del movimento sullo Slave.

Quando premi Arresta, il programma attende l'esito del comando già inviato,
non invia i successivi e richiede `MOVE [0, 0, 0]`. Il ritorno viene considerato
completato solo se il controller restituisce esito positivo. Anche a fine
sequenza viene eseguito e controllato lo stesso rientro.

Le attese XML sono interrompibili. Una chiamata `manage_action` già in corso,
invece, dipende dai timeout implementati nei tuoi moduli. La GUI non finge di
annullarla e non lancia un secondo comando in parallelo.

In caso di errore o timeout durante inizializzazione, movimenti o rientro, la sequenza termina, l'inizializzazione
viene invalidata e **non** viene accodato un movimento automatico di rientro:
l'esito del movimento precedente potrebbe essere incerto. Occorre verificare
la postazione e reinizializzarla. Questa gestione è diversa dall'originale,
che ignorava diversi valori di ritorno di `manage_action`.

## XML supportato

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sequence>
    <command action="PRESS" target="KEY_1" />
    <command action="MOVE_TO" target="KEY_2" />
    <command action="WRITE_T9" target="AB12" />
    <command action="WAIT" duration="250" />
</sequence>
```

`duration` è in millisecondi; per WAIT il valore predefinito è 1000.
PRESS usa la durata del tasto, altrimenti quella del modello e infine 200 ms.
T9 mantiene le pressioni da 40 ms, la pausa fra click da 20 ms e la pausa da
300 ms fra caratteri consecutivi sullo stesso tasto.

Azioni sconosciute, tasti assenti, caratteri T9 non supportati, XML malformati
e durate non valide sono rifiutati prima dell'avvio. L'originale saltava alcuni
di questi errori durante l'esecuzione. I riferimenti `leads_to` vengono risolti
sia per nome della schermata sia tramite il suo `parent`; MOVE_TO non simula
una pressione e quindi non cambia la schermata logica.

Lo script visualizzato viene mantenuto come piano immutabile: modifiche esterne
al file o al JSON richiedono di ricaricarlo. Limiti: 2 MB per XML, 5.000 comandi,
4.096 caratteri per ciascun WRITE_T9. DTD ed entità personalizzate non sono ammesse.

## Trascinamento dei file: opzione aggiuntiva

Nel client Flet standard usa **Sfoglia file**. Il trascinamento di file esterni
richiede l'estensione `flet-dropzone` e la compilazione di un client che la includa.
L'entry point dedicato è **main_native_drop.py**; **main.py** rimane l'avvio standard.

Su Windows, con la toolchain di compilazione Flet/Flutter installata:

Per includere l'estensione nel client compilato, aggiungi
`"flet-dropzone==0.4.0"` all'elenco `project.dependencies` di `pyproject.toml`
oltre alla dipendenza Flet esistente, quindi:

```console
python -m pip install "flet[all]==1.0.4" "flet-dropzone==0.4.0"
flet build windows --module-name main_native_drop
```

Esegui il client prodotto in `build/windows`. Prima di compilare per l'uso
hardware, inserisci anche i moduli originali, `pc_cfg.yaml` e le rispettive
dipendenze Python nel progetto. Il client compilato parte in ambiente hardware;
puoi selezionare Demo dall'interfaccia. Non è incluso un eseguibile Windows
precompilato. La build dell'estensione e il trascinamento nativo non sono stati
collaudati su questo ambiente.

## Anteprima browser facoltativa

```console
python -m pip install "flet[web]==1.0.4"
python DmiGUI.pyw --web
```

L'anteprima è locale su `127.0.0.1:8550`, sempre in demo. La modalità hardware
è disabilitata nel browser. Il caricamento XML usa il contenuto del file
selezionato; l'esportazione del registro è disponibile nella versione desktop.
Su Linux, la finestra di scelta file del client desktop richiede Zenity.

## Verifiche effettuate

La suite inclusa verifica le coordinate e i tempi dell'XML allegato, la
validazione degli errori, il T9, le attese frazionarie, la serializzazione
delle chiamate al controller, l'arresto durante un movimento, gli errori
di inizializzazione/esecuzione/rientro e il cambio di modalità.

Verifica inoltre la costruzione e serializzazione dei controlli con Flet 0.82.2 e 1.0.4
e il flusso dell'interfaccia: carica, inizializza, esegui, cambia modello,
gestisci errore, rimuovi file. Sono verificati anche il caricamento tramite
FilePicker, l'annullamento del dialogo e il blocco del caricamento durante una
sequenza, nei percorsi desktop e browser. Il trasporto grafico è simulato in questi test.

La suite aggiornata comprende **58 test**, passati su entrambe le versioni
Flet. Include salvataggio e validazione delle opzioni, offset su PRESS/MOVE_TO/T9,
assenza di modifiche al JSON, rientro senza offset, firme esatte delle azioni foto,
ordine dei comandi, gestione di errori della fotocamera, nuove immagini e
sovrascritture, file incompleti, mancato download e serializzazione delle
finestre di impostazioni e delle anteprime immagine. I test del monitor
verificano l'aggiornamento durante una chiamata al controller in attesa,
l'arresto delle animazioni dopo un errore o un'interruzione e la conferma
finale solo dopo la ricezione dell'immagine.

```console
python -m pip install pytest
python -m pytest tests -q
```

Non è stato possibile completare l'ispezione visiva in una finestra nativa
in questo ambiente. Anche le finestre native di apertura/salvataggio,
la build Windows e il collegamento al robot restano da verificare sul PC
di destinazione. Non è una dichiarazione di collaudo dell'hardware.

## Riferimenti tecnici

- [API e migrazione a Flet 1.0](https://flet.dev/docs/updates/migrate-to-1-0/)
- [FilePicker](https://flet.dev/docs/services/filepicker/)
- [Animazioni Flet](https://flet.dev/docs/cookbook/animations/)
- [Compilazione Flet](https://flet.dev/docs/cli/flet-build/)
- [flet-dropzone](https://github.com/shiena/flet-dropzone)

</details>
