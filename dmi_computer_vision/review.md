# DMI Detection V2 — Project Review

Reviewed on 6 October 2026, at commit `b85c0e447ff87eaf02eb218a0590899eb7e4907e`.

## 1. Overall assessment

The project is a well-organized extension of the working V1 pipeline. It detects the two DMI displays, understands supported screens, extracts required values and controls, stabilizes results over time, and produces annotations and compact JSONL logs. Recorded video and webcam input use the same detector.

It is a useful foundation for robot integration. The main work still needed is improving recognition reliability and validating the actual robot camera and target computer. The current evidence supports live processing of selected recent frames; it does not establish reliable processing of every camera frame or reliable robot button pressing.

This review covers acquisition, detection, temporal processing, outputs, entry-point scripts, evaluation code, tests, and project documentation. It is a review of the whole project, not a branch diff.

## 2. How the pipeline works

1. **Receive an image.** Recorded input reads frames in order. Webcam input uses a background camera worker with one pending frame. A newer capture replaces an older pending capture when processing is slower than the camera.
2. **Locate the displays.** Blue-color regions and boundary evidence identify the left and right displays. Perspective transforms produce consistent internal views for detection.
3. **Recognize the interface.** The pipeline reads titles, identifies a supported screen, fits button borders, finds fields, and reads their values. Train Data titles on the left help interpret the right display.
4. **Analyze the left display.** Normal screens use the 22-box layout and icon matching. Train workflows use their own title and control handling.
5. **Stabilize observations.** Geometry smoothing, optical-flow tracking, and state/value confirmation reduce fluctuations. History resets after relevant losses, capture gaps, or resolution changes.
6. **Publish results.** Coordinates refer to the original image. JSONL stores snapshots and changes; annotations show detailed geometry. Live callers can optionally expose one current observation through `LatestState`.

The main entry points are [run_video.py](scripts/run_video.py) and [run_webcam.py](scripts/run_webcam.py). The shared processing contract is in [frame_processor.py](src/dmi/pipeline/frame_processor.py).

## 3. What works well

**Clear responsibilities.** Production code is separated into detection, temporal processing, acquisition, orchestration, output, and evaluation. Camera and network integration can be added around the existing detector. Each `FrameProcessor` owns the history of one sequential source.

**Useful screen coverage.** The implementation supports Main, Driver ID, Level, Train Running Number, Train Data, Validate Train Data, and both Train Data pages. Unknown states and missing values are represented explicitly. Unknown-screen handling remains limited to detected structure; it does not automatically understand new button meanings.

**Extensible icon assets.** Supported images are discovered recursively under `data/icons/`, with filenames defining identities. Duplicate identities and invalid assets fail explicitly. Templates are cached, so asset changes require a process restart to take effect.

**Streaming output.** Normal processing retains current state rather than accumulating every result. Logs are flushed incrementally, progress is visible, and recorded runs preserve partial files on interruption. Snapshots remove obsolete elements; updates preserve unchanged information. Debug logs remain optional. See [OUTPUT_SPEC.md](docs/OUTPUT_SPEC.md) for the exact contract.

**A suitable live-state interface.** [LatestState](src/dmi/output/latest_state.py) returns independent copies, expires observations by frame receipt age, and clears them when a session stops or fails. This is a good connection point for a future robot consumer.

**Meaningful regression checks.** Tests cover transitions, missing evidence, geometry, output reconstruction, camera buffering, cleanup, and concurrent state reads. Evaluation distinguishes output validity from recognition accuracy, and recorded replay from physical camera testing.

## 4. Verification and evidence

Fresh checks during this review:

- All **129 tests passed** using `python3 -m unittest discover -s tests -q`.
- A **20-frame** Train Running Number run completed at approximately **4.52 processed FPS**.
- All 20 results passed the output contract and compact reconstruction checks, with **zero semantic mismatches** and the configured 5-pixel coordinate tolerance.
- The annotated video decoded to 20 frames. One annotated frame was inspected: the title, keypad, display boundaries, and left layout were broadly aligned. The empty field was reported with an unknown value.

The short run is a smoke check, not a new accuracy study or performance benchmark. Its artifacts are under `/private/tmp/dmi_project_review_20261006/` and are temporary.

Existing evidence in [EVALUATION.md](docs/EVALUATION.md) reports:

- Six full recordings totaling **4,330 frames** passed end-to-end checks. All **1,982 V1 regression frames** had no unexpected differences after isolating approved changes.
- Compact output was **93.56% smaller** than equivalent full V2 debug JSONL.
- A controlled Driver ID comparison measured **7.75% higher throughput** after the Phase 7 optimization.
- A five-minute simulated camera run captured about **30 FPS** and processed **5.63 FPS**, with at most one pending application frame. Mean receipt-to-result latency was **195 ms**, with a maximum of **1.391 seconds**.

Those results were previously recorded, not reproduced in full for this review. Simulation latency excludes sensor/driver delay and subsequent logging/preview work. No physical robot webcam or Raspberry Pi validation was performed here. Completed development phases in [STATE.md](docs/STATE.md) do not imply completed hardware integration.

## 5. Current limitations

- **Recognition can be confidently wrong.** Documented examples include `235` read as `275` and `12` read as `17`. Digit recognition uses generated font templates; titles and some text fields use Tesseract. Temporal confirmation cannot correct a repeated wrong observation.
- **Some button borders are unreliable.** The validation recording contains a roughly 98-pixel close-button center jump while the visible UI barely changes. Valid geometry and a recognized button name do not establish an accurate physical target.
- **Detection depends on the expected appearance.** Color thresholds and known layout proportions guide fitting. Glare, blur, exposure changes, viewing angles, or robot-arm occlusion may reduce reliability. Display localization currently returns neither display if it cannot successfully fit both.
- **Live processing skips captures.** The latest-frame buffer avoids a growing backlog, but short UI events may be missed. A one-frame application buffer does not eliminate camera-driver buffering.
- **Confirmation depends on processed-frame count.** Defaults include five frames for state changes and fifteen for field-value changes. At 5 processed FPS, these correspond roughly to one and three seconds of evidence, depending on the transition path. Some initial values are accepted immediately. Snapshot freshness does not reveal when a retained field value was last directly observed.
- **Headless mode still draws annotations.** `--no-preview` removes the GUI callback, but [process_live](src/dmi/pipeline/live.py) still annotates every processed frame and saves the last annotated image on exit.
- **Operational recovery is incomplete.** Camera failure ends the session; automatic reconnection is absent. A native camera backend blocked in open/read may outlive the close timeout. JSONL files grow for the duration of a session, without rotation, and flushing does not guarantee survival of power loss.
- **Deployment setup is incomplete.** The root has no README, dependency manifest, or installable package configuration. Scripts insert `src/` into the import path, and icon lookup assumes the repository layout. Tesseract and English language data are required, but its installation guidance is incomplete.
- **Accuracy coverage is incomplete.** Existing recordings are valuable regression evidence, but there is no complete labeled ground-truth dataset. Lambda/No recognition is not established by those recordings. Detailed Train Data summary extraction remains outside the implemented scope.

## 6. Improvements for a more robust pipeline

Prioritize these changes while preserving the accepted baseline:

1. **Create a small labeled robot-camera test set.** Include motion, glare, occlusion, screen transitions, and similar-looking digits. Measure value errors, button-center errors, missed transitions, and response delay separately.
2. **Fix raw OCR and border failures first.** Add tests for general failure conditions, strengthen digit ambiguity rejection, and require stronger local border support. More smoothing should follow better detection rather than conceal wrong results.
3. **Expose evidence age and quality.** Report when each field/control was last observed, whether geometry is measured or tracked, and whether a transition is pending. Consumers need more than a fresh frame timestamp to decide whether a result is usable.
4. **Evaluate time-based confirmation.** Combine a minimum observation count with elapsed-time bounds so behavior remains predictable when processing speed changes. Compare against existing transition and OCR regressions before changing defaults.
5. **Measure and reduce repeated work.** Profile on the target computer. Consider a true annotation-disabled mode, change-triggered OCR with periodic refresh, and reuse of unchanged icon regions. Invalidate reused evidence on motion, screen changes, gaps, or occlusion.
6. **Improve deployment and long-run operation.** Add dependency/setup instructions, a startup check for OCR/assets/camera access, configuration for asset paths, log rotation, and explicit camera recovery. Incrementally extract screen definitions from the large layout module when new screens justify it.

## 7. Practical suggestions for robot webcam use

Start with observation on the actual robot, then add actions after measuring recognition and positioning errors.

- **Use a stable camera view.** Keep both displays visible and large enough for digit reading. Test focus, exposure, lighting, and vibration with the robot stationary and moving. Confirm the actual delivered resolution; requested camera dimensions are not checked for acceptance by the current adapter.
- **Run an initial headless session.** From the repository root, use a fresh output directory:

  ```sh
  python3 scripts/run_webcam.py --camera 0 --no-preview \
    --max-frames 100 --output-dir outputs/robot_camera_trial_01
  ```

  Inspect the log and final annotated image. This command checks acquisition and processing; it does not enable robot communication.

- **Reuse the existing interfaces.** Have the robot application retain a `LatestState` object and pass it to `process_live(..., latest_state=store)`. Read `store.get(max_age_seconds=...)` from a separate consumer thread. The current webcam CLI does not expose this integration itself.
- **Keep transport outside detection.** If the robot uses a different camera API or a remote stream, implement a source adapter returning BGR `uint8` images, increasing capture indices, and local monotonic receipt timestamps. Bound buffering to recent frames. The current `LatestCamera` accepts local numeric camera indices, not stream URLs.
- **Separate perception from robot commands.** Validate the expected screen, target identity, geometry, and evidence freshness before acting. Treat `None`, unknown states, occlusion, and pending transitions as reasons to wait and observe again. Avoid performing slow network calls in the detection loop.
- **Calibrate button positions.** Output centers are image pixels, not robot coordinates. Establish the camera-to-screen and robot relationship, account for camera movement, and verify the expected UI change after each action before continuing.
- **Choose hardware from measured requirements.** Measure CPU, memory, temperature, disk growth, and response latency on the intended Raspberry Pi or robot computer. If it cannot meet the required response time, evaluate a nearby processing computer while including network delay in the measurements.
- **Test recovery and sustained use.** Include camera disconnection, blocked capture, consumer failure, restart, and long sessions. A separate capture process is worth evaluating if a blocked native backend must be forcibly restarted. Run longer hardware trials before relying on the five-minute simulation as operational evidence.

The recommended next step is a labeled physical robot-camera trial that establishes acceptable recognition error and action latency, followed by a small consumer using `LatestState` and calibrated button positions.
