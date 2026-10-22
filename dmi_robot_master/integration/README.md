# Robot/CV integration

## Monitor-support offline validation

The installed source mapping is camera 0 for the lower separated displays and
camera 1 for the upper connected monitor. Select one per session. Image evidence
still determines screen identity and geometry; each view needs its own calibration.
Connected footage establishes Main and Driver ID only. Level, Train Running
Number, Train Data, Validate Train Data and both Train Data pages need connected
recordings with visible boundaries, fields and controls before coverage is claimed.

From the repository root, use new output directories:

```sh
python3 dmi_computer_vision/scripts/verify_monitors.py --output-dir /tmp/dmi_monitor_corpus_01 --annotations
python3 -m dmi_robot_master.integration.monitor_benchmark --arrangement connected --processing regular --output-dir /tmp/dmi_monitor_regular_01
python3 -m dmi_robot_master.integration.monitor_benchmark --arrangement connected --processing selective --output-dir /tmp/dmi_monitor_selective_01
```

Use `--arrangement separated` for the other controlled replay. These simulations
exercise the existing latest-frame source, detector, policy and target files.
They include drawn same-title field changes, erased controls, brief transitions,
partial regions and recovery; they do not establish additional real screen
coverage. The helper imports no motor transport. Targets remain uncalibrated.
Add `--annotations` equally to both benchmark commands to include native video
encoding and headless preview callbacks. Callback rate is not GUI paint rate.

For a supplied connected capture, add
`--recording dmi_computer_vision/data/videos/dev/dmi_capture_quality_02`.
This uses saved receipt intervals rather than MP4 playback FPS. The source files
remain unchanged; old annotations outside the monitor are masked on replay copies.
Reports separate analysis/OCR cost, queue overwrites, policy skips, processed FPS,
receipt-to-result age, confirmation delays and output bytes. Nested OCR/stage
times must not be added together. Run matched performance trials sequentially.
Full debug JSON and target history are enabled for evaluation in both policies.

The Step 5 review under `dmi_computer_vision/outputs/monitor_support/` records
remaining detection/coverage limits. Passing contracts or recognizing a title
does not establish control alignment or authorize motion. Existing confirmation,
freshness, calibration and four-pixel publication limits remain in force.
Sustained Main-to-Driver replay can confirm Driver ID before its key geometry
agrees with the current image. A focused expected-failure test records this open
transition defect. Complete monitor-support acceptance remains open; see root
STATE.md and the review before treating the static-capture checks as broader support.

## Hardware camera trial: Picamera2/libcamera

For cameras that work with `rpicam-hello`, the bridge defaults to Picamera2.
OpenCV device numbers and Picamera2 camera numbers are different interfaces.
The installed slave reported two IMX708 cameras, numbered 0 and 1, and Picamera2
is already available. Close `rpicam-hello` before starting the bridge. From the
project root on the Pi/Linux slave:

```sh
python3 -m dmi_robot_master.integration.frame_bridge --bind 0.0.0.0
```

The default camera is 1, matching CameraTool2.py. Use --camera 0 for the other
view. Copy both the updated
`frame_bridge.py` and new `picamera_source.py` into the same integration package
on the slave before using this command. Keep the existing package dependencies.
Use --backend opencv explicitly for USB/V4L2 capture devices.

The Picamera2 source copies BGR images into one pending slot, discards replaced
frames, times out on missing frames and releases the camera on exit/startup failure.
It starts no Pi preview or motor controller. Capture defaults match CameraTool2:
2304x1728 BGR output, requested 2304x1728/10-bit sensor mode, continuous autofocus,
ExposureValue -2 EV, requested 30 FPS and both horizontal/vertical flips (180 degrees).
No capture flags are required. Picamera2 selects the closest supported sensor
mode when there is no exact native match; startup JSON reports actual sensor/output
configuration. A request is not proof of delivered capture FPS or field of view.
This profile requires a camera supporting autofocus and exposure compensation.
Width/height may still override output dimensions; the sensor-mode request stays
the CameraTool2 default. Recheck focus, framing and actual mode on the Pi.
JPEG publication defaults to 10 FPS at quality 95, independently of sensor FPS.
The recording tool's MP4/25-Mbps setting is not used for individual JPEG images.
Local receipt timestamps describe callback receipt, not sensor exposure; upstream
sensor/driver delay remains to be measured on hardware.

On the Windows master, from the project root, use the existing receiver:

```powershell
python -m dmi_robot_master.integration.observe --bridge-url http://192.168.1.210:8080/frame.jpg --processing selective --preview --rotation 0 --output-dir C:\Temp\dmi_picamera_trial_02
```

The address is the confirmed Ethernet slave address; verify it on deployment.
Rotation is now applied in the Picamera2 bridge. Remove the previous PC
--rotation 180; use --rotation 0 (the receiver default) to avoid a double rotation.
On macOS use a fresh /tmp/dmi_picamera_trial_02 output path instead of C:\Temp.
Use a new output directory for each attempt.
All later calibration must use the final selected camera, resolution and orientation.
The updated capture profile has fake-device checks only until the Pi trial succeeds.
HTTP format and PC detector behavior are unchanged.

Implemented and tested offline; not validated on hardware. Detector behavior,
GPIO assignments, homing, motor timing and movement routines are unchanged.

# Phase 1 — existing command interface

## PC setup and offline checks

Use Python 3.10 or newer. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r dmi_robot_master/integration/requirements-pc.txt
PYTHONPATH=tests .venv/bin/python -m unittest test_robot_integration.CommandTests test_robot_integration.ProtocolTests -v
# Full suite in the existing detector development environment (numpy/OpenCV):
python3 -m unittest discover -s tests -v
```

Tkinter must be provided by the Python installation for GUI imports. The tests
stub tkinterdnd2 if needed; the real GUI requires the installed dependency.
Existing detector dependencies remain in root requirements.txt; Phase 1 command
checks need PyYAML, and the real-method offline check also needs numpy/OpenCV
(from that existing environment). No lgpio or Picamera2 installation on the PC.
The checks run here used existing Python 3.13.3, PyYAML 6.0.3, numpy and OpenCV.
They never open a camera, GPIO device or network socket.

For a minimal command-only check without the optional real-method test, install
PyYAML and run the CommandTests and ProtocolTests from tests via unittest.

Imports use repository package names. For a different working directory set
PYTHONPATH to the absolute repository directory. Config paths resolve relative
to the owning source files, not the working directory.

## Deployment commands (deferred, hardware-capable)

After confirming network settings in dmi_robot_config/pc_cfg.yaml and
raspberry_cfg.yaml, from the repository root:

```sh
python3 -m dmi_robot_master.DmiControllerMaster
# On the Raspberry Pi only:
python3 -m dmi_robot_rasp.DmiControllerSlave
```

Launch the .pyw GUI through runpy to preserve repository package imports:

```sh
python3 -c 'import runpy; runpy.run_path("dmi_robot_master/DmiGUI.pyw", run_name="__main__")'
```

The master module only performs the existing ACK handshake; it does not move.
The slave constructs GPIO devices at startup; do not run it on the development
PC. On the Pi, provide lgpio, numpy and OpenCV using the supported OS packages /
Python environment. Picamera2 is still imported by the existing robot module,
so it also must be available there even though camera initialization is disabled.
Confirm Pi OS, GPIO permissions and dependency versions on deployment. Do not
install Pi packages on the PC. Configuration IPs/ports are existing values, not
confirmed deployment settings; PC port 50 may require binding privileges.

## Small command interface

Pass existing controller send/receive functions (fake transport at home) to
DmiControllerMaster, then wrap it with RobotCommands from integration.commands:

```python
commands = RobotCommands(controller, xy_limits_mm=(380, 470), timeout_seconds=5)
ok, data = commands.move(100, 300)       # [MOVE, 100, 300, 0]
ok, data = commands.press(100, 300, 250) # [MOVE_AND_CLICK, 100, 300, 250]
```

Those limits are an offline example from the existing robot constants, not a
measurement of physical travel. Explicitly configure confirmed limits before
hardware use. Coordinates are absolute XY millimeters, with nonnegative values
and exclusive upper bounds; press duration is milliseconds. The current wire
format carries signed 32-bit integers, so fractional millimeters are rejected.
A later conversion must choose and document rounding explicitly. MOVE's third
argument remains the existing nonnegative Z input; the adapter always sends zero.
The robot currently scales Z using the Y conversion, so nonzero Z is unvalidated.

The adapter sends once and requires DONE with empty data. ERROR, malformed
responses, send failure, socket failure and timeout return (False, []), with a
logged reason. It does not retry or distinguish these failures in a new response
schema. A timeout may follow an executed action. Future interactive sessions
must stop further actions on failure, as specified for Phase 5.

Slave dispatch calls live_movement and click; initialize/zero/position/ACK
behavior and shared message numbers are preserved. Invalid command lengths,
noninteger values, negative/out-of-range XY and negative durations are rejected
before a robot operation. Bounds at the slave use existing robot _X/_Y constants;
tighter deployment limits belong in the integration adapter. Existing picture
requests can fail explicitly; they do not imply a working camera.

Shared protocol: DmiMessages command payload inside ComProtocol's source ID,
destination ID, payload length and XOR CRC; UDPSocketManager serializes the word
count as unsigned big-endian 32 bits and values as signed big-endian 32 bits.
The standalone 40/50/60/70 protocol in DmiRobot.py is excluded. Wire format and
message IDs are unchanged. Malformed packet lengths are rejected; empty
nonblocking reads are normal, actual socket errors are propagated. UDP has no
connection/session/action IDs: ACK does not prove readiness, and a late DONE
cannot be correlated to a specific action. No concurrent actions or retries.

## Why existing files changed

- GUI: fix package imports and actual shared config path; close owned socket at
  exit. No widgets, script behavior or GUI stop behavior changed.
- Master: fix config path, use monotonic timeout, stop immediately on ERROR and
  close the socket after the handshake loop.
- Slave: defer Pi imports until hardware startup to permit fake-only PC imports;
  fix method names, validate payloads and catch unknown message IDs; release its
  socket and shared GPIO handle once on normal/exceptional loop exit.
- UDP/common protocol: expose socket cleanup, reject incomplete datagrams and
  propagate real receive errors instead of hiding them until a timeout.
- No changes to DmiRobot, motors, sensors, GPIO pins or detector code.

## Hardware limitations requiring focused follow-up

Camera slots remain None. Robot.click returns True after attempting contact even
when _z_movement did not detect a press. DONE therefore means only that the
existing method returned success, never successful UI input. _z_movement's
extra-contact loop adds 200 to eff_steps per iteration rather than one; this
appears to overcount retraction distance and needs a separate focused review
before a physical press. Lower-bound enforcement and homing/sensor waits in the
base motor code are incomplete. GPIO cleanup after partial constructor failure
is also not established. The GUI may continue scripts after command failure,
and its stop flag is not an immediate hardware stop. These are documented,
not silently refactored in Phase 1. Verify mounting/origin, travel, Z retraction,
contact sensing, homing, stop mechanism and actual camera before physical tests.

Picture assembly/reliability remains legacy behavior, outside this command
integration: failed initial picture responses can leave an unset local path,
and incomplete chunk collection is not reliable. Phase 2 will give acquisition
one owner and use its live frames rather than enabling this legacy camera path.

# Phase 2 — observation and paced live-path replay

Intended processing host: the PC. The user reports two webcams, probably on
Raspberry Pi; type and cabling are not yet confirmed. The integration supports
one selected OpenCV-compatible USB camera on the Pi through the JPEG bridge,
and a local-PC camera as a configurable alternative. Actual host, backend,
index, dimensions, orientation and network address remain deployment settings.
If the devices instead require Picamera2, a source adapter is still needed;
no installed-camera compatibility is claimed without that later confirmation.

From the repository root, using the same configured Python environment as the
detector (numpy, OpenCV, PyYAML; Tesseract plus English data for recognition):

```sh
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --replay-fps 8 --max-frames 12 --debug \
  --output-dir /private/tmp/dmi_robot_observation_01
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
```

Choose a new output directory for every run. The observation command refuses to
overwrite an existing directory. Omit max-frames to replay until EOF; omit
replay-fps to pace at the recording's original FPS. start-seconds skips decoded
source frames before replay, preserving their original index/FPS video time.
Decode is sequential, not a backend-dependent seek. Container counts are not
used to establish EOF. Decoder read failure at the end is treated as EOF;
truncated/corrupt recordings need independent decode inspection.

`ReplayCamera` owns VideoCapture in one worker, timestamps receipt locally and
retains one pending BGR uint8 frame. New frames overwrite an older pending frame.
`process_live`, its existing FrameProcessor and LatestState remain the processing
path. Only the source's read() raising EOFError adds a clean `eof` stop; EOFError
from the detector remains an error. Recognition thresholds/temporal rules are
unchanged. Test-only namespace fixes in vision test_live.py/test_video.py make
existing mocks patch the actual imported modules; they do not change detections.

Outputs:

- results.jsonl: existing compact detector log.
- annotated.mp4: one full-size annotation per processed frame. Playback is fixed
  at 5 FPS for inspection, **not** original video time or measured capture rate.
- processed_frames.jsonl: processed/capture indices, frame dimensions, monotonic
  and UTC source receipt time, original source video time (null for real camera),
  and receipt-to-saved-annotation delay. Match original video time with the input
  recording when evaluating sampled frames.
- last_annotated.png: existing final preview image.
- results_debug.jsonl: optional full detector results with --debug.
- session.json: simulation flag, source settings, counts, skipped captures,
  capture/processed session-average rates and latency. Partial outputs and an
  error report remain when possible after a failure. Counters distinguish
  overwritten frames from index gaps in processed frames; frames captured near
  shutdown may never be processed. pending_frames is cleared on close.

Live receipt-to-result latency includes detection/annotation, excluding saving
and preview; the sidecar also measures receipt-to-saved-annotation time. Neither
includes real sensor/driver buffering. Replay capture rate includes decoding;
reported rates include startup/shutdown and the final processing tail. It is
normal for processing to skip captures. No claim of full-frame processing or
universal screen recognition is made. Unknown states are exported unchanged.

Optional --preview uses the existing OpenCV window on the main thread. Ctrl-C,
Q/Escape (preview only), EOF and errors close source/output resources. A native
backend blocked in open/read may outlive the close timeout; process exit may be
needed. There is no automatic reconnect. Source orientation is configurable via
--rotation 0/90/180/270 (clockwise), then --mirror (horizontal). It defines the
input coordinate system seen by detection: saved centers correspond to that
full-resolution oriented image, never the resized preview. Later calibration
must record the same orientation, mirror and dimensions.

For a confirmed local-PC USB camera only (hardware command, not executed here):

```sh
python3 -m dmi_robot_master.integration.observe \
  --camera 0 --width 1280 --height 720 --preview --max-frames 100 \
  --output-dir /private/tmp/dmi_robot_camera_trial_01
```

Index and dimensions above are examples, not confirmed setup values. The adapter
reuses LatestCamera with a single owner; it rejects URLs instead of assuming the
integer-index adapter can stream. Width/height are requests; actual dimensions
are logged in processed_frames.jsonl. Inspect delivered resolution/orientation
and image quality on hardware. UTC for this adapter is anchored to local wall
clock and mapped from the original monotonic receipt time, so consumer dequeue
cannot make a stale frame appear fresh. The remote bridge treatment is described below.

The source's last_packet exposes the most recently delivered image for a future
still-image consumer; that consumer must copy it and check receipt freshness.
No second device is opened by the robot, and legacy picture capture remains
disabled. This observation command imports no robot transport and sends no motor
commands. All recording artifacts are simulation and cannot provide physical
calibration or evidence of a successful robot press.


## Pi camera bridge (implemented offline, not deployed)

The selected camera has one owner in a Pi process. Its existing LatestCamera
acquisition worker drains the device with one pending frame; FrameBridge stores
only one recent JPEG and its capture index/monotonic age. The PC requests the
current JPEG on demand, not a continuous historical stream. No frame queue can
grow across the network. HTTP requests have a timeout and a 16 MiB JPEG limit.
The bridge index must advance; duplicate replies do not refresh input. Camera
restart (session ID change or index regression), error, stale input or disconnect
fails the session.
There is no automatic retry of a failed observation session or reconnection.

On the Pi (once its camera index and network interface are confirmed):

```sh
python3 -m dmi_robot_master.integration.frame_bridge \
  --bind PI_INTERFACE_ADDRESS --port 8080 --camera CAMERA_INDEX \
  --width CONFIRMED_WIDTH --height CONFIRMED_HEIGHT
```

On the PC:

```sh
python3 -m dmi_robot_master.integration.observe \
  --bridge-url http://PI_ADDRESS:8080/frame.jpg --preview --max-frames 100 \
  --output-dir /private/tmp/dmi_pi_camera_trial_01
```

Replace the uppercase placeholders with confirmed settings. These hardware
commands are documented, not executed here. If there are two webcams, explicitly
choose one index per session; no assumption is made about which sees the DMI.
Do not also enable DmiRobot.take_picture on the same camera. No camera or GPIO
hardware is needed for replay and fake-HTTP development checks.

The PC uses its own monotonic/UTC receipt time. The Pi sends an age measured on
its own monotonic clock, so no cross-host wall-clock synchronization is needed
for this bridge freshness check. PC validation adds the whole request round-trip
to that age conservatively. Both age and round-trip are retained in the sidecar;
local receipt-to-result latency does not include that upstream age. Future
consumers must add those quantities to local receipt age when evaluating remote
target freshness. UTC anchoring reflects each host's wall clock, not exposure
synchronization. Remote capture counters infer the index span since the first PC
observation; native capture FPS is reported null rather than invented.

JPEG encoding at quality 95 may change pixels. Offline JPEG-path Driver ID checks
verify contract/recognition but are not a measured guarantee of camera accuracy.
The bridge is a small observation endpoint on the configured camera-host
interface; it imports no motor/controller code. Network connection and installed
OpenCV camera compatibility are deferred to the physical trial.


Offline recognition limits observed in Phase 2: sampled Driver ID/Level/Main
recordings include explicitly unknown/obstructed observations. One reviewed
Level annotation recognizes the screen but places several control boxes away
from their visible controls, consistent with inherited layout limitations. No
thresholds or temporal behavior were adjusted to hide this. Driver ID and Main
examples are suitable for review, not proof of physical target accuracy.

# Phase 3 — simulation calibration

Calibration fitting and point conversion live in calibration.py; the small
calibrate.py CLI reads a successful Phase 2 simulation observation directory.
It cannot produce a physically verified hardware calibration or send a robot
command. The accepted detector, robot code and reference JSON are unchanged.

The reference is DmiPositions.json → DMI_SENSE_TOUCHSCREEN → screens →
DRIVER_ID_WINDOW → buttons. digit_0..digit_9 match KEY_0..KEY_9 by identity,
regardless of dictionary order. Only that model currently has mapped keys.
Detected centers use the original full-size input image, including its configured
orientation, with no preview scaling. The collector requires all ten keys on
consecutive clear Driver ID observations, resets after missing/ambiguous/unstable
matches or a temporal reset, rejects size changes and summarizes centers by
coordinate medians. Its bounded sample window retains no frame history.

Use the configured detector Python environment, from the repository root:

```sh
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 3 --max-frames 12 --debug \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase3/driver12_NEW
python3 -m dmi_robot_master.integration.calibrate \
  --observation-dir dmi_computer_vision/outputs/robot_integration/phase3/driver12_NEW \
  --output dmi_computer_vision/outputs/robot_integration/phase3/driver12_NEW/calibration.simulation.json \
  --observations 5 --max-spread-px 3 --ransac-threshold-mm 5 \
  --simulation-tolerance-mm 5
python3 -m unittest discover -s tests -q
```

Choose a new observation directory/file for every run. These demonstrated
settings select a steadier recorded section; the slow replay preserves closely
spaced source frames, with source-video time retained separately. The initial
moving-camera segments failed the 3-pixel stability gate and were left rejected.
The example spread/RANSAC/tolerance values are explicitly development settings;
**5 mm is not a proposed physical acceptance tolerance**. Omit simulation-tolerance
if only an error report is wanted: the resulting artifact remains unaccepted and
conversion rejects it. No detector thresholds or temporal rules were tuned to
make a calibration example pass.

OpenCV fits a planar pixel-to-absolute-XY-mm homography. It needs noncollinear
correspondences. The fitting API accepts five or more named keys, preferably all
ten: each leave-one-key-out validation needs at least four remaining training
points, so four total keys cannot supply independent validation in this API.
RANSAC thresholds use destination mm. Fits with inconsistent keys/outliers,
duplicate points, insufficient inliers, near-collinear geometry or a horizon
crossing the calibrated region are rejected. Per-key, mean and maximum held-out
XY error are saved separately from training residuals. The acceptance gate uses
the maximum held-out error and an explicitly supplied tolerance and explanation.
Small residuals do not establish physical accuracy of the reference positions.

The JSON artifact contains provenance, content-derived calibration ID, model and
screen plane, frame size, camera identity/settings/mount revision, robot
origin/axes, reference-file SHA256, homography, matched identity/pixel/mm points,
observation count/capture indices/stability setting, convex keypad hull, inliers,
training and held-out errors and acceptance status. Recorded files are marked
simulation and hardware_verified=false. They cannot be reused as installed-camera
calibration. Files are never overwritten; a SHA256 identifier detects accidental
content changes, not malicious rewriting or truth of operator assertions.

Python consumer interface:

```python
from dmi_robot_master.integration.calibration import load_calibration, convert_pixel

calibration = load_calibration(
    path, frame_size=actual_frame_size, camera=current_camera_context,
    origin=current_origin_context, hardware=False,
)
xy_mm = convert_pixel(
    calibration, pixel_center, frame_size=actual_frame_size,
    camera=current_camera_context, origin=current_origin_context,
    display='right', screen='Driver ID', hardware=False,
)
```

Pass independently configured **current** camera/origin context to check a saved
artifact; copying that context from the file cannot detect a changed setup.
Validation checks schema/ID, reference hash, frame size, exact settings/mount and
origin context, accepted tolerance, correspondences, hull and independently
recomputed errors/transform. Malformed/invalid artifacts are rejected. Conversion
uses homogeneous coordinates and rejects nonfinite/singular matrices or unstable
division. Output remains floating-point absolute mm; it performs no rounding for
the existing integer robot protocol. Press duration, Z depth and force are outside
this calibration.

Only points inside the matched-key convex hull on the right Driver ID plane can
be converted. Other-display, other-screen and outside-area points raise ValueError;
Phase 4 must export their detected pixels with mm=null rather than extrapolating.
A hull boundary is the limit of interpolation, not evidence of accuracy at every
interior control. Separate screen planes need separate measured calibration.

Later hardware execution must pass hardware=True. Simulation and physically
unverified artifacts are rejected unconditionally. fit_calibration can prepare a
hardware-origin fit only with an explicit live source context; it still leaves
hardware_verified=false. This phase provides no method that certifies hardware
accuracy or enables motion. Physical certification must follow the installed
camera/reference/mount/origin and independent validation review after all six
phases; the first-action workflow must enforce that gate.

Choose physical tolerance from measured usable button size, tool/contact geometry
and robot positioning accuracy before accepting a hardware fit. Verify the stored
key XY positions, home the robot and establish actual origin and axis directions.
Every relevant mounting/image-size/crop/orientation/reference/origin change
invalidates calibration. Mount revisions must be updated explicitly; resolution
alone cannot reveal movement. recheck_keypad compares freshly collected stable
key centers against saved correspondences using an explicit pixel tolerance.
Require that recheck before each physical test and suspected change. A retained
tracked center is not independent fresh evidence: replay examples use stabilized
output and only demonstrate offline fitting; physical collection must verify
recent direct measurements and no occlusion/movement.

Phase 3 review files are inside the project at
`dmi_computer_vision/outputs/robot_integration/phase3/` (already ignored by Git).
Two recorded examples have per-key validation errors and annotated images. These
review outputs, recordings and simulation JSON files are not committed.

# Phase 3A — selective detection and meaningful publication

Regular processing remains the default for accepted replay/calibration behavior.
Select `--processing selective` to enable a measured development profile: maximum
5 detections/s, 0.4 s periodic refresh, 3 s confirmation burst after image-change
or reset/action evidence. Cheap checking uses a 160×120 blurred grayscale image,
compared with the last **detected** image, not the previous capture. Defaults mark
change when at least 0.2% of thumbnail pixels differ by more than 12 intensity
levels. This check is not title recognition and can miss tiny/brief changes;
periodic full detection remains mandatory. All settings are configurable.

```sh
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --processing selective --debug \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase3A/selective_NEW
python3 -m dmi_robot_master.integration.benchmark_policy \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase3A/comparison_NEW
```

A new session/resolution or capture gap forces detection. Call
`policy.request_refresh()` immediately after a completed action to force one
newer-than-action source frame; it retains no queue. Required reset/action checks
may bypass the rate cap; ordinary image-change/confirmation/periodic work obeys
it. The confirmation burst requests ordinary full detections; detector state/value
confirmation counts and temporal thresholds are unchanged. Slow native operations
can still exceed refresh deadlines or cause the existing capture-gap reset.

Live processing gained optional policy/callback hooks, annotation disable and
separate consumed/skipped/detection/annotation counters. Default calls follow the
same accepted path. LatestState updates only after actual detection. Skipped
captures never publish an invented observation or refresh receipt/evidence age.
`--max-frames` counts detections; `--max-captures` counts consumed captures and
has a distinct footer stop reason. CompactWriter still uses its existing schema
and 5-pixel tolerance for rich logs; no second detector/log implementation exists.
Debug envelopes additionally preserve local receipt and source-video times.

`publication.py` supplies a small in-memory pixel projection and change/freshness
policy for Phase 4. Its optional callback receives a full target snapshot on first
observation and meaningful changes, and a lightweight status heartbeat. Review
sink `publication_review.jsonl` demonstrates the callback; it is **not** the
Phase 4 current targets.json file or a backend service. Regular observation can
also enable it with `--publish-changes` to separate publication suppression from
detection scheduling. No calibration/motor usability is inferred in this pixel
projection: targets have usable=false until Phase 4 adds validated conversion.

Target publication tolerance defaults to 4 pixels **per coordinate**. Differences
of 3 and exactly 4 are suppressed; greater differences publish. Compare against
the last published pixel baseline so cumulative drift is retained. Screen/title,
identity/presence, exported field values, visibility, usability, frame/context,
calibration/session changes and loss bypass geometry tolerance. Field-value export
is optional; the CLI pixel projection currently omits values. Latest internal
centers update after every detection even when serialization/publication is
suppressed. The rich compact detector log continues to preserve exported values.

Heartbeat default is 0.5 s, with session/revision, actual last-detection time and
source receipt/evidence age, without all target coordinates. A small background
status worker expires evidence after the configurable 1.5 s limit even if source
read/detection is blocked; healthy-worker expiry granularity is at most 0.1 s plus
OS/callback scheduling. Expiry/failure/stop publish empty targets and status when
possible; consumers must independently expire missing heartbeats after abrupt
process death. There is no real-time scheduling guarantee. Local monotonic time
and upstream Pi capture age + whole HTTP round-trip are used conservatively.
Heartbeat or unchanged image checking cannot renew evidence. Aggregate frame age
still does not establish fresh support for every retained tracked element.

Selective mode disables annotation drawing/encoding by default. `--save-annotations`
and/or `--preview` enable full review output for actual detections; `--debug` is
also optional. A reused preview is explicitly marked with observation age. GUI
calls remain on the main processing thread. No repeated video frames are encoded
for skipped detections. Regular mode continues to annotate all detections.

For a Pi bridge, selective PC requests default to at most 10/s via
`--frame-request-fps`; configure Pi `frame_bridge --frame-fps 10` to also cap JPEG
encoding. The camera acquisition owner continues to drain frames into its latest
slot, selecting recent captures for encoding. Index/receipt metadata belongs to
the selected encoded frame; skipped frames never renew it. Regular bridge/request
behavior remains uncapped unless explicitly configured. These transport caps are
fake-tested, not measured/deployed on a Pi. Two camera/network settings remain
unconfirmed.

`ValidatedCalibration` validates a copied calibration once on creation, then
checks current context and a reference-file stat fingerprint before reuse. It
caches only the latest coordinates per current label set, avoiding repeat refits
and conversions when centers are identical; vanished entries are removed. Context
or reference changes require full validation. Per-action
`revalidate_for_action(...)` always uses the original full validation, including
hardware rejection. Phase 4 will connect this cache to target projection; Phase
3A does not enable movement or certify hardware calibration. Publication tolerance
never changes the accepted Phase 3 fitting/stability/physical validation rules.

Offline evidence is in `outputs/robot_integration/phase3A/` under the vision
project, ignored by Git. Final controlled comparison repeats original decoded
BGR frames through the bounded replay worker: Driver ID → Main → black/loss →
Driver ID. It uses real detector processing with controlled simulation changes;
these changes were not caused by a robot. All results pass output/compact checks.
An earlier re-encoded MP4 fixture lost Driver ID recognition; it was retained as
failed fixture evidence and replaced by original decoded pixels, with no detector
threshold changes. The benchmark records per-phase source-time recognition delay
and conservative receipt-to-result-inclusive delay, calls/time/output bytes.

Final measured example: 169 regular vs 86 selective detector calls (49% fewer),
23.60 vs 16.99 s accumulated detection time (28% less), 0.77 vs 0 s annotation time.
Each mode emitted 12 meaningful target snapshots; selective emitted ~47.3 KB
coordinates plus ~14.4 KB heartbeats. An unsuppressed per-detection pixel projection
would emit 86 snapshots/~356.8 KB in the selective run. That byte comparison is a
counterfactual serialization measurement, not a claim about an existing backend.
No further snapshot savings are claimed against the already change-based regular
publication policy or existing CompactWriter.

Controlled maximum source-time recognition delay was 0.93 s regular / 0.77 s
selective; loss was recognized within 0.07/0.13 s. In the actual Level-to-Main clip,
an initial 4 FPS/0.5 s/2 s-burst profile recognized Main 3.89 source seconds later
than regular. The selected 5 FPS/0.4 s/3 s-burst profile recognized it within 0.14 s
of regular (slightly earlier in that trial). One capture-gap reset occurred in
that actual selective run; timestamps/counts were not altered to hide it. Brief
state events can still be missed. Settings suit these offline examples, not a
universal response guarantee. Early exploratory runs overlapped other checks;
the final controlled pair ran serially on the development Mac/Python environment.

# Phase 4 — current targets and evidence status

`observe --export-targets` connects the Phase 3A publication policy to atomically
replaced `targets.json` and `target_status.json` in the observation directory.
The rich detector logs remain unchanged. There is no backend or motor command.
`--target-history` optionally writes separate full-snapshot targets_history.jsonl
for review; selection never reads that history or publication_review.jsonl.

```sh
python3 -m dmi_robot_master.integration.observe \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 3 --max-frames 12 --debug \
  --export-targets --target-history \
  --calibration dmi_computer_vision/outputs/robot_integration/phase3/driver12/calibration.simulation.json \
  --calibration-context dmi_computer_vision/outputs/robot_integration/phase4/driver12_context.simulation.json \
  --evidence-tolerance-px 3 \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase4/driver12_NEW
```

The existing Phase 3 simulation calibration and Phase 4 context fixture must be
present. The context fixture was prepared from the actual replay path/delivered
frame dimensions/orientation plus an explicitly unverified simulation mount and
reference-origin convention. For another source, provide an independent JSON
object containing current `camera` and `origin` objects in the calibration schema;
do not adopt camera/origin metadata from a saved calibration as proof of the
installed setup. Context camera identity/settings/mount and robot origin must
match the calibration and current input. Recorded paths are checked explicitly.
Live context must declare the same `source_kind` as the actual adapter. For
`local_camera`, camera.settings must include `camera_index` and `requested_size`
(`[null, null]` if no dimensions were requested); both must match the runtime
adapter selection. For `remote_bridge`, settings must include `bridge_url` matching
the actual endpoint. Delivered dimensions, rotation/mirror and crop checks still
apply. The observation entry point checks its declared source metadata against
the actual adapter before opening it and again for each exported detection. Physical serial identity/mounting still need
the installed-camera trial; a matching index or endpoint is not that certification.
Live hardware calibration remains physically unverified and simulation fits are
rejected on real-source export. Do not invent device/origin settings for deployment.

`--calibration` requires the current context and an explicit evidence geometry
tolerance; it also enables target export. The example 3 px is a development
setting for recorded geometry checks, not a universal physical tolerance or the
4 px publication threshold. Without calibration, export still lists detected
pixel targets, with mm=null and usable=false. Regular/ selective processing and
optional annotations remain available exactly as in Phase 3A.

The file schema keeps session ID, source detection frame index, source receipt
UTC timestamp, confirmed screen, calibration ID and a target list of stable label,
kind, display, original-image pixel, absolute robot mm/null and usable. Additions
are revision, simulation flag, calibration provenance and original frame size.
Digits map to KEY_0..KEY_9; other labels are qualified by display/kind. Buttons,
fields and boxes are exported; first-schema field values/icons are omitted.
`usable` indicates current supporting geometry and valid mapped area, not an
approved pressing kind or physical validation of simulation coordinates.

Only current right Driver ID points inside the validated keypad hull can receive
mm. Left-display/other-screen/outside-hull targets retain pixels with mm=null.
Calibration/context/reference changes, missing direct key evidence or failed
keypad mounting checks remove usability and, on failed calibration/geometry
validation, mm. The conversion cache validates on load/context/reference changes,
retains only current label coordinates, and avoids repeating identical conversion
or refitting invalid unchanged documents. Per-action full revalidation still
belongs in Phase 5; publication cache is never movement authorization.

A small optional FrameProcessor side channel records right-display state,
visibility and directly observed key/field centers from the same detection pass
before temporal region stabilization. Detector results, thresholds, confirmation,
annotations and rich log schema do not change. No second detector pass is run.
Every usable target requires current raw support, complete matched-key mounting
agreement, and agreement between its exported center and that current observation.
Missing/transition/occluded evidence cannot bless a retained center. These checks
establish support from the detector, not correctness of its recognition/borders.

Coordinates are written on meaningful changes under the 4 px policy. Source
receipt timestamps and frame indices in a suppressed snapshot therefore remain
those of the last published coordinates. Status independently records current
actual detection/receipt time, age, session/revision and the labels that still
support the **published** centers. Losing support forces a snapshot even below
4 px: a publication tolerance cannot conceal usability invalidation. Internal
CurrentTargets retains exact latest centers, so it does not use the quantized
published baseline. Freshness includes upstream camera age/round-trip delay.

Both files use temporary serialization in the same directory and os.replace;
readers never see partially written JSON. They are not a two-file transaction:
a brief revision mismatch is possible and must be rejected/read again. Optional
history uses exactly the target snapshot schema. Startup/expiry/loss/failure/stop
replace targets with an empty list when possible. A normal stopped session has
empty targets even if its review history contains valid examples. Abrupt death
may leave old files; consumer expiry handles that without relying on file mtime.
Flushing/atomic replacement does not promise power-loss durability.

Consumer functions in targets.py:

```python
from dmi_robot_master.integration.targets import read_target

# Read only while the observation session is running. This sends no commands.
target = read_target(observation_directory, "KEY_5", max_age_seconds=1.5,
                     hardware=False)  # Explicit simulation/preview consumer.
```

The reader rejects missing/malformed files, duplicate/absent labels, mismatched
session/revision, stale/future/inconsistent UTC/evidence status, unsupported old
centers, absent mm/calibration and unusable targets. hardware=True also rejects
simulation. Both statuses and snapshots are required: touching a file, heartbeat
alone or a fresh unrelated frame cannot authorize old coordinates. Supported
labels plus the revision identify recent evidence for those exact published
centers; source/status age must remain within the configured limit.

Files are produced using the processing PC's local UTC receipt/heartbeat clock.
The Pi contributes its monotonic capture age; its wall clock need not match for
that age calculation. Cross-host file consumers need aligned UTC clocks and
must include file-transfer delay; a reader detects future/inconsistent clocks
and fails closed. Local in-memory reads use monotonic age. Do not relax clock
checks merely to make unsynchronized deployment appear fresh.

A caller can retain `CurrentTargets()` and pass `current_targets=store` to
`observe(..., export_targets=True, ...)`; `store.get()` returns an independent
current full snapshot or None before observation, after expiry/failure/stop.
It uses the latest actual detection instead of a historical file. It is a small
future-app interface. Phase 5's LabelActions supplies label preview and validated
single-action dispatch without adding a backend.

Phase 4 review evidence is inside `outputs/robot_integration/phase4/` under the
vision project. driver12/targets_example.simulation.json is a labelled historical
review example, not an actionable current file. It includes simulated mm values;
up to all ten keys were usable in one recorded observation. The strict 3 px raw
keypad recheck invalidated several other observations, exposing raw geometry
jitter hidden by stabilization; no threshold was loosened to hide it. The actual
Level-to-Main selective replay exported Level/Main/unknown pixels with mm=null.
Both runs retained correct source timestamps and ended with empty current targets.
Physical accuracy, wider-monitor coordinates, camera/device compatibility and
successful UI pressing remain unvalidated.


Phase 4 review corrections: publisher.current() and tick() sample the production
monotonic clock only after taking their lock, so waiting behind a blocked
publication cannot return an expired observation or emit a false fresh status.
An explicitly supplied now is a deterministic simulation/test clock, not the
production read path. Regression fixtures block publication while advancing the
clock beyond expiry. Live source binding rejects kind/index/requested-size/endpoint
mismatches even when the supplied context and pixel geometry fit the calibration;
source metadata participates in negative-cache invalidation/recovery checks.

# Phase 5 — one-label terminal session

## Short live-session command

Configure `run_robot.json` beside `run_robot.py` once, then run from the project root:

```sh
python3 -m dmi_robot_master.integration.run_robot test_01
```

This starts the existing `press_label` session with live detection, annotated
preview and terminal label input together. Enter `KEY_1` at the terminal prompt;
enter `quit` to end the session. Use another name for each trial. Results go to
`/tmp/dmi_robot/test_01`, with sibling `test_01_progress.log` and
`test_01_button_tests.jsonl`. Existing outputs are rejected, not overwritten.
`/tmp` is temporary storage and may be cleaned by the OS; copy useful trials to
permanent storage. `~/tmp` would be a different folder under your home directory.

The Pi camera bridge and robot UDP receiver must already be running. Do not run
`observe.py` alongside this session: `press_label` owns its own live processing.
The supplied config requests regular processing, preview, receiver rotation 0
and physical UDP pressing. Verify the bridge URL and both hosts' UDP settings;
the repository PC YAML may still contain deployment addresses/ports needing updates.

Fill the null settings with the installed camera's verified calibration and
matching context paths, hardware-checks path, reviewed pixel evidence tolerance
and measured exclusive XY upper limits in mm. Paths are relative to the JSON
file, or can be absolute (`~` is supported). Do not use simulation calibration
or invent readiness flags. The template intentionally fails before opening any
camera or socket until these settings are supplied. All existing physical gates
remain in `press_label`; the launcher does not home or calibrate the robot.
The known transition/control-alignment defects and physical validation work
remain unresolved by this launcher.

For another camera/calibration profile, pass `--config /path/to/settings.json`.
The camera index is selected on the Pi bridge; it is not inferred by this launcher.
Preview is enabled by default; set `"preview": false` in the configuration to
disable it. The original long command remains available for advanced options.

Start one program; acquisition/detection and target export run while the terminal
accepts KEY_0..KEY_9. It never asks for coordinates or runs an XML sequence.
Default mode is dry-run, default transport is fake; the banner names both.

```sh
python3 -m dmi_robot_master.integration.press_label \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 1.5 \
  --calibration dmi_computer_vision/outputs/robot_integration/phase3/driver12/calibration.simulation.json \
  --calibration-context dmi_computer_vision/outputs/robot_integration/phase4/driver12_context.simulation.json \
  --evidence-tolerance-px 3 --max-x-mm 380 --max-y-mm 470 \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase5/terminal_NEW
```

Wait for a current observation, then enter `KEY_5`, for example. Dry run prints
pixel/mm/rounded command and any rejection reason, sending no command. Geometry
jitter can make a recognized key unusable: rejection is intentional, not a reason
to relax physical gates. Add `--mode simulated-press` to send exactly one validated
request to a fake robot. `--fake-response DONE|ERROR|TIMEOUT|DISCONNECT` and
`--fake-delay` support offline trials. Press ms defaults to the current 200 ms
reference example; XY bounds are explicitly required (380/470 here are repository
simulation bounds, not verified hardware travel). Use fresh output names.

Modes: dry-run, simulated-press, move-only, physical-press. With fake transport,
move-only and physical-press exercise the corresponding command payloads and are
explicitly labelled FAKE/SIMULATION. They establish neither movement nor pressing
on hardware. Simulated press cannot use a real motor transport. A valid label in
press modes requests one press; writing targets.json never triggers action.

`actions.py` handles preview/request/validation and owns at most one action worker.
Requests received while command or UI verification is outstanding are rejected,
not queued. Detection/target publication continue during motor/network waits.
The selected label is resolved immediately when entered, and re-resolved again
before dispatch after file/refit checks. Session/calibration changes, loss of
support, unusable/duplicate/type/display/wrong-screen targets, stale input,
outside-keypad positions and out-of-travel coordinates reject without dispatch.
Commands require full current calibration/source/context/reference validation,
complete fresh raw key recheck and matching mm. Cached publication cannot authorize
an action. Integer protocol conversion is explicitly nearest whole mm with .5
rounded upward; both floating and rounded positions must satisfy exclusive XY
upper bounds. This rounding remains to be assessed against physical button/tool
accuracy before enabling movement.

`action_transport.py` reuses existing master/slave and RobotCommands. FakeTransport
uses a fake robot through the existing slave method mapping; TIMEOUT can follow
an executed fake action, illustrating why no retries are allowed. RobotLink traces
DONE/ERROR/timeout/disconnect/send/malformed-response failures. Only DONE with the
expected empty payload is completion. Failure latches the session against further
commands; restart only after operator review. Existing UDP action-ID/correlation
limitations remain; at most one outstanding action and no automatic retries.

DONE does not prove UI input. Press completion requests a processing-policy refresh,
then waits for a newer source observation received after completion, conservatively
accounting for Pi age/HTTP round-trip. A known directly observed/confirmed Driver ID
value implies an expected appended digit. Confirmation requires that expected
value in both raw and confirmed data on a newer frame. Unknown baseline, wrong/
missing value, session/calibration change, timeout or shutdown yields unconfirmed.
Replay/fake transport only reports `expected_change_observed_in_simulation`, never
physical causality. The small added raw-field-value side channel is used only for
verification; target files still omit field values. Recognition errors can remain.

The main thread owns detector processing and optional `--preview` OpenCV GUI.
A daemon thread owns blocking terminal input; a separate bounded action worker
owns communication/verification. Progress and controller warnings go to a separate
`<session>_progress.log`, results stay near the input prompt, and one JSONL action
record logs label/source frame/calibration, pixel/float/command mm, mode/transport,
response and observed outcome in `<session>_button_tests.jsonl`. quit/EOF/Ctrl-C
signal coordinated stop, clear targets and release camera/output/transport resources.
A blocked stdin reader can remain until process exit but owns no device and cannot
launch an action after shutdown. A native camera/action backend blocked indefinitely
may require process exit, with outcome reported unconfirmed. Software quit is not
an immediate hardware stop; it cannot undo an already issued movement/press.

## Physical execution (implemented policy, deferred trial)

No UDP, GPIO or real camera operations were executed for Phase 5. Later,
`--transport udp` requires explicit --mode move-only or physical-press, a live
source, confirmed PC robot YAML via --robot-config, and --hardware-checks JSON.
That JSON must assert actual verified facts, not placeholder defaults:

- homed, xy_limits_verified, z_retracted, contact_sensing_checked;
- stop_mechanism_available, origin_and_mount_verified, contact_routine_reviewed;
- move_only_alignment_reviewed additionally for physical-press.

Simulation/unverified calibration/targets cannot pass hardware execution even
with those flags. Verify real camera context/source identity, origin/axes/reference
positions, bounds, retraction/contact and physical stop before any command. Review
and resolve the known contact/Z accounting defect separately before asserting the
contact routine reviewed flag. Inspect move-only alignment with the tool retracted
before authorizing the first press. Flags record operator checks; they do not
perform homing, read sensors, certify a camera or provide an emergency stop.
All six phases plus 3A must finish offline before this physical procedure.

Offline checks: all four modes/payloads, single outstanding action, target change
before send, calibration/context/stale/wrong screen/hull/bounds rejection, fake
ERROR/timeout/disconnect failure latch, post-action evidence, log/shutdown races,
EOF/quit/Ctrl-C and main-thread preview ownership. Controlled synthetic observations
validate the verification logic; hardware-policy fixtures are synthetic test
assertions and never physical calibrations. Existing detector/motor thresholds,
timing, GPIO pins and wire protocol remain unchanged.

Actual replay evidence under vision outputs/robot_integration/phase5/:
replay_press_button_tests.jsonl records one KEY_5 fake request at [150,250] mm,
DONE, newer camera observation, UI unconfirmed (recorded value stayed 12).
replay_dry_button_tests.jsonl records a dry-run geometry rejection, NOT_SENT.
Both current target files are empty after quit. Source progress/compact/debug
logs remain for inspection; generated evidence is ignored by Git.

# Phase 6 — complete offline verification

From the repository root in the configured detector environment:

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s dmi_computer_vision/tests -q
python3 -m dmi_robot_master.integration.verify_offline \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase6/verification_NEW
```

Choose a new output directory. The verification command accepts only an output
path: its inputs are existing recordings and its transport is always fake. It
collects a fresh development calibration from stable Driver ID observations,
then independently resolves KEY_4, KEY_5 and KEY_6 and sends one simulated press
per request through the existing master/slave protocol. A rejected dispatch or
failed response fails the run without retry. Preview may wait for usable current
geometry; it never makes the stored calibration or targets physically valid.

The full Driver ID-to-Level recording runs through the same live path with
selective processing, original image coordinates and bounded latest-frame capture.
Both recognized screens must reach output; without a calibration for that source,
their targets remain pixels with mm=null and usable=false. Stopped sessions must
clear targets. Contract validation, compact reconstruction and full annotation
video decoding run for all three observation sessions. No detector thresholds,
temporal confirmation or calibration tolerances are altered.

`verification.json` records environment, independent calibration errors, selected
actions/packets, screen counts, resets, contracts and processing/latency summaries.
`button_tests.jsonl` records the three actions. Each observation directory retains
compact/debug logs, receipt/video-time sidecar, annotations, session summary and
current target/status files; actions/transition also retain target history.
Partial evidence remains if a run fails. These generated files are Git-ignored.
Saved annotations need visual review; contract checks establish output consistency,
not recognition accuracy or physical center accuracy.

Verified run on 2026-10-12: macOS ARM64, Python 3.13.3, OpenCV 5.0.0, existing
Tesseract/numpy environment. All 101 integration and 129 vision tests passed.
Evidence is under vision `outputs/robot_integration/phase6/run03/`: 12 calibration,
7 action-session and 421 transition detections (440 total) passed contracts,
compact reconstruction and annotation decode checks. Simulation held-out error
was mean 0.653 mm/max 1.119 mm against stored JSON. Actual selected fake packets
were [1,100,250,200], [1,150,251,200], [1,200,251,200]; the latter Y values reflect
current detection and the documented rounding. All three received DONE and a
newer observation; field value stayed 12, so all UI outcomes remained unconfirmed.

Full transition: 855 captured, 619 consumed, 236 overwritten and 198 policy-skipped
captures, 421 actual detections in 111.41 seconds (7.67 capture/3.78 processed FPS).
Receipt-to-result latency averaged 239.7 ms, max 424.0 ms; mean detector/annotation
time per detection was 188.1/5.3 ms. No temporal history resets occurred. Recognized
observations: 192 Driver ID, 146 Level, 83 unknown (79 obstructed). First confirmed
Level observation used source-video time 19.56 s; no ground-truth transition-delay
bound is claimed. Startup/decoding/shutdown and annotation saving are included in
session rates; sensor/driver/network delay is excluded from this local replay.
Brief transitions may be missed. This run is verification, not a new optimization
comparison; retain Phase 3A's accepted comparative measurements.

Reviewed images: `run03/actions/Driver_ID_review.png`, and
`run03/transition/Driver_ID_review.png` / `Level_review.png`. Titles, fields and
keypad/Level layout align broadly in those samples; reviewing three images does
not establish accuracy over every frame. Existing OCR/dropouts/border instability
and physical limitations remain. Both current target files finish empty.

For an interactive default dry run using the newly generated simulation fit:

```sh
python3 -m dmi_robot_master.integration.press_label \
  --replay dmi_computer_vision/data/videos/dev/driver_id_12.mp4 \
  --start-seconds 2.5 --replay-fps 1.5 \
  --calibration dmi_computer_vision/outputs/robot_integration/phase6/run03/calibration.simulation.json \
  --calibration-context dmi_computer_vision/outputs/robot_integration/phase6/run03/context.simulation.json \
  --evidence-tolerance-px 3 --max-x-mm 380 --max-y-mm 470 \
  --output-dir dmi_computer_vision/outputs/robot_integration/phase6/terminal_NEW
```

Enter one KEY_n or quit. Substitute your successful verification directory if
different; choose a new terminal directory. Add --mode simulated-press only for
an explicit fake press request. Geometry rejections remain valid outcomes.

`tests/test_offline_integration.py` exercises the actual observe → FrameProcessor →
target projection/publication → CurrentTargets → LabelActions → master/slave →
fake robot path with controlled synthetic detector observations. Three separate
key selections produce expected integer-mm/ms packets and require a newer raw
and confirmed field value after DONE. Additional cases reject wrong screen,
removed key, invalid calibration, travel bounds, old file/evidence and camera
failure; ERROR, timeout and disconnect latch commands while observation continues.
Earlier tests retain duplicate/hull/source-context/simulation rejection, 3/4-pixel
jitter, drift, busy-action, refresh and terminal cleanup coverage.

Controlled observations check the verification logic. Real-recording UI outcomes
remain unconfirmed when the expected append is not observed: prerecorded input
cannot establish robot causation. DONE also does not prove UI input. Simulated
mm fitting, 380/470-mm bounds, 3-pixel evidence tolerance, 5-mm fit acceptance and
200-ms presses are development settings, never proposed physical acceptance facts.

## Small application interface

Reuse the existing interfaces; no backend transport or autonomous navigation is
implemented. Keep a `CurrentTargets` and `LatestState`, pass them to `observe`,
and retain a `LabelActions` wired to those same objects and the selected RobotLink:

```python
snapshot = targets.get()             # Exact latest targets, or None on expiry/loss.
preview = actions.preview('KEY_5')    # Pixel/mm/command center or rejection reason.
requested = actions.request('KEY_5') # One validated request; never queues a label.
```

`observe(..., export_targets=True, current_targets=targets, latest_state=state,
calibration_path=..., calibration_context=..., evidence_tolerance_px=...,
processing_policy=policy, stop_event=stop)` owns acquisition and publication.
`LabelActions(targets, state, link, calibration_path=..., context_path=...,
source_info=..., policy=policy, mode=SessionMode.DRY_RUN, stop_event=stop,
on_result=callback)` uses that same session. Current context comes from independent
camera/origin metadata; physical use must also provide actual-source checking and
verified hardware readiness. The working examples are `run_terminal` in
press_label.py and the recording-only verify_offline.py.

Run observation independently of blocking input/communication. Optional GUI
preview stays on the main thread. `request` returns a pending result for an accepted
asynchronous command; its completion arrives via `on_result`, or `last_result`
after completion. Use the callback to update an application, with its own UI thread
handoff if needed. A dry run returns synchronously and sends nothing. `preview`
never authorizes a later send: `request` re-resolves and revalidates current evidence.
Keep one outstanding request and handle explicit rejection; never retry a press
on timeout. On shutdown set the shared stop event, close actions and join observation;
the session clears current targets and releases source/output resources. A callback
must not close its own action worker or block indefinitely.

## Later physical trial

Use the observation/bridge and terminal commands above after confirming the installed
camera, dependencies and network. Fit a new calibration on the installed fixed camera;
the replay calibration must be rejected by physical execution. Establish actual axis
directions/reference keys, measured bounds/tolerance, retraction/contact/homing and
physical stop. Review the known contact/Z defects separately. Inspect real annotations
and freshness first, then dry run, reviewed move-only alignment and one explicitly
selected physical press with newer-camera UI verification. Keep wider controls and
the other screen uncalibrated until separately measured and validated. Offline
completion does not establish camera compatibility, physical accuracy or pressing.
