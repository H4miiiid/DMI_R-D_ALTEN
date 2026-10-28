# Python vision interface

Use `dmi_computer_vision.src.dmi.api` from a Python application. The repository
root must be on Python's module search path (run from that directory, or set
`PYTHONPATH` in the calling application's environment). The interface uses the
existing NumPy/OpenCV/Tesseract dependencies; it starts no GUI, camera, socket,
robot controller or background worker. Tesseract needs its English language data.
Keep the existing tracked `dmi_computer_vision/data/icons/` assets alongside the
package when deploying it; asset paths are relative to the owning files.

```python
import time
import cv2

from dmi_computer_vision.src.dmi.api import CapturedFrame, VisionSession

capture = cv2.VideoCapture("recording.mp4")
try:
    with VisionSession("recording:example") as vision:
        index = 0
        while True:
            ok, image = capture.read()
            if not ok:
                break
            # In a live application, use the acquisition adapter's original
            # received_at instead of assigning a new time to a queued frame.
            packet = CapturedFrame(image, index, time.monotonic())
            observation = vision.process(packet)
            print(observation.result["right_display"]["state"])
            print(observation.direct_evidence["right_buttons"])
            current = vision.latest()  # None if stopped/failed/expired
            index += 1
finally:
    capture.release()
```

The example ages locally decoded frames. It is an offline example, not a live
camera benchmark or physical calibration. Hold the supplied image immutable until
`process` returns. Acquisition adapters remain the sole owners of their cameras.

## Observations and freshness

`process(CapturedFrame)` calls the same `FrameProcessor` used by recorded and live
processing. `Observation.result` retains the established rich detection schema;
all corners, bounding boxes and centers are in the original input-image pixels.
`frame_size` is `(width, height)`. No annotation, JSON files or pixel-to-mm
conversion is performed by this method.

`Observation.direct_evidence` is the existing current-pass support, before temporal
confirmation. For example, `right_field_value` may be null while the rich result
still contains an earlier confirmed value. Direct support and confirmed output
must not be treated as interchangeable, nor can a retained value renew evidence.
The detector's OCR, state/value confirmation and SENSE/TWIN behavior are unchanged.

The observation carries source/session identity, capture index, monotonic receipt
and completion times, upstream age, frame size and the existing temporal reset
reason. Its dictionaries belong to the caller. Holding or modifying an observation
does not update the session's latest snapshot or make historical content current.
`age_seconds()` measures age only; it does not assert that the session is active.

`latest(max_age_seconds=1.0)` returns a detached `LatestState` compact snapshot,
extended with `source_id`, `session_id` and `upstream_age_seconds`. Its `state` key
contains the established compact detection schema. Age starts at acquisition
receipt, includes analysis time, and adds `IntegrationFrame`'s optional
`remote_capture_age_seconds` and `transport_round_trip_seconds`. Reading it does
not refresh timestamps. The requested lifetime must be positive and at most
1.5 seconds; a slow analysis may return an observation while `latest()` is already
expired. A fresh unknown/null detection replaces prior content normally.

Freshness describes input timing. It proves neither recognition correctness,
enabled state, calibration coverage, robot readiness nor a successful press.
Current SENSE natural-transition/Train Running Number coverage remains pending
the raw evidence identified in root `STATE.md`.

## Ownership and lifecycle

- Use `with VisionSession(source_id)` or explicit `start()` / `close()`.
  Close is idempotent, invalidates latest state and releases native OCR resources.
- One owner serializes processing and lifecycle calls. Concurrent calls raise
  immediately. `latest()` is safe for another thread and does not wait for image
  analysis. A GUI should run this synchronous processing on its existing worker;
  UI rendering/acquisition remain independent.
- For a selected source/camera/panel change, call `reset(source_id="new source")`
  on that owner, or close and start a new session. Reset discards temporal history,
  closes OCR resources, clears the latest snapshot and issues a new session ID.
  Source IDs identify acquisition only; image evidence still decides geometry.
- Capture indices and receipt times must increase within a session. The existing
  processor invalidates history on frame-size changes or capture gaps (default
  one second). Inspect `temporal_reset` and invalidate dependent application state.
- Input/analysis failure closes the session and clears latest state. Start a new
  session explicitly to recover; there are no automatic retries. If acquisition
  fails outside `process`, exiting the context or calling `close` invalidates it.

## Existing observation runner

The same module also exports `process_live`, `LiveRunSummary` and `LatestState`
directly from their existing owners. `process_live` retains its existing source,
output, processing-policy and preview callbacks; this is an alias, not another
pipeline. Raw `LatestState.get()` retains its local receipt-age contract; the
additional upstream-age accounting above belongs to `VisionSession.latest()`. Use it when the application needs the existing bounded-source runner and
compact logs. The caller still opens/closes the source. Supply no preview for
headless use. Its existing file/output and freshness contracts are unchanged.

Annotation remains in `dmi_computer_vision.src.dmi.output.annotation`; acquisition
stays in the existing camera/bridge adapters. The Flet GUI and other applications
can use this interface rather than implementing detection themselves. Wiring Flet
workers and command ownership is reserved for the later GUI steps.

## Calibration boundary

This vision interface exports original-pixel detections, not calibrated targets.
The existing math and guarded projection remain separately owned by
`dmi_robot_master.integration.calibration` and `targets.TargetProjector`.
Their legacy right Driver ID/keypad restrictions and physical-validation limits
remain in force. They are not a validated whole-SENSE transform.

After reference/calibration validation in the later roadmap steps, a separate
target-resolution adapter can consume `Observation.result`, `direct_evidence`,
`frame_size` and source/session context using those existing implementations.
Source/session changes and temporal resets must invalidate dependent calibration
or target context. Step 8.A neither installs a calibration nor broadens projection
coverage or action eligibility. Robot commands never belong in the detector API.
