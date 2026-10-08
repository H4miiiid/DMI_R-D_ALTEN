# Robot/CV integration handoff

## Current status

**Phase 1: Completed offline — accepted.** User approved commit and push on
2026-10-08. Commit/push are being performed to `origin/main`
(`https://github.com/H4miiiid/DMI_R-D_ALTEN.git`). Worktree was clean on `main`
at start. Phase 2 has not started. No physical validation performed.

## Phase 1 implementation

- Fixed GUI package imports and controller/GUI paths to shared dmi_robot_config.
- Slave now calls existing live_movement/click, imports Pi code only at hardware
  startup, validates command payloads and replies ERROR for unknown message IDs.
- Added common command_validation.py and master integration/commands.py:
  explicit XY bounds, absolute integer mm, duration in ms, existing master
  dispatch and DONE requirement; no automatic retries.
- Master stops on ERROR and uses monotonic timeout. Common UDP exposes cleanup,
  rejects truncated datagrams and propagates receive errors. Entry points close
  owned sockets; slave closes its shared GPIO handle once on loop exit.
- Added tests/test_robot_integration.py and integration/README.md plus optional
  PC dependency list. No changes to motors, homing, pins, wire format, detector,
  GUI widgets/script behavior or existing YAML values.

Confirmed against real robot methods with motor calls replaced: XY is absolute;
250 ms reaches _z_click as 0.25 seconds. Shared DmiMessages/ComProtocol is the
integration path; standalone DmiRobot message IDs 40/50/60/70 are excluded.

## Checks actually run

Environment: macOS, Python 3.13.3 from
`/Users/hamiidreza/.pyenv/versions/3.13.3/bin/python`, PyYAML 6.0.3 and existing
numpy/OpenCV. No Pi packages installed; no actual sockets/cameras/GPIO opened.

From repository root:

```sh
python3 -m unittest discover -s tests -q
python3 -m compileall -q dmi_robot_common dmi_robot_master dmi_robot_rasp tests
git diff --check
python3 -m unittest discover -s dmi_computer_vision/tests -q
```

- Phase 1: **12 tests passed**, covering valid dispatch/units, invalid payloads
  and bounds, ACK/initialize/zero/position, ERROR/exception/timeout/disconnect,
  uninitialized camera failure, wire envelope/serialization and cleanup.
- Same 12 tests passed from /private/tmp using repository PYTHONPATH and the
  explicit Python interpreter above. Config/startup paths and GUI imports tested
  with fake transport/robot and a tkinterdnd2 stub. Real GUI rendering and Pi
  construction untested. Installation recipes documented, not freshly installed.
- Compile checks and diff whitespace check passed. PC slave import confirmed it
  loads neither lgpio nor picamera2.
- Additional unchanged vision suite: 129 tests ran; **4 failure reports and
  2 errors**, reproduced. Existing tests import dmi_computer_vision.src.dmi but
  some mocks patch dmi.*, so injected failures do not reach the tested modules.
  Affected cases are FrameSessionTest gap/reset, LiveProcessingTest processing
  failure, and ProcessVideoTest overwrite/interrupt/nonfinite handling.
  Temporary log: /private/tmp/dmi_phase1_vision_checks.log. No vision files changed.
  Earlier runs from the vision directory lacked root PYTHONPATH, and /tmp used a
  different python3 lacking PyYAML; corrected root/explicit-interpreter runs are
  the results above. Future commands must use the configured environment.

## Deferred limitations and next step

Hardware travel/origin/network settings remain unverified. Adapter XY limits are
explicit; slave uses existing 380/470 mm constants, upper bounds exclusive.
Fractional mm are rejected by the integer protocol. Camera slots remain None.
Base click success does not establish contact; contact-loop step accounting
appears to overcount retraction distance. Propose a separate focused contact/Z
fix and fake sensor/motor tests before any physical press. Lower-bound checks,
blocking sensor/homing waits, nonzero-Z scaling, partial GPIO startup cleanup,
legacy picture transfer and late UDP response correlation remain limitations.
GUI stop is not an emergency stop; scripts may ignore failed command results.
Detailed setup/limitations are in dmi_robot_master/integration/README.md.

User decision: proceed with this repository integration; compare deployed PC/Pi
files and local setup during the later robot trial. Deployed behavior may differ
from this checkout. Phase 1 approval authorizes only its commit and push.

Next: complete the approved commit/push to verified `origin/main`, then Phase 2
camera processing integration. Camera interface/host facts may be needed then.
Hardware testing remains deferred until all six phases. Report this commit ID
and push result in chat; record them at the next natural handoff update.
