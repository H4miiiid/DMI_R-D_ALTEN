# Robot/CV integration — Phase 1

Implemented and tested offline; not validated on hardware. Detector behavior,
GPIO assignments, homing, motor timing and movement routines are unchanged.

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
