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
