# STATE.md — Current Project State

## Current Phase

**Phase 11 — implementation accepted by the user**, with the documented
limitations; commit and push approved on 2026-09-28.
**The final system's real webcam has not been tested or validated with the
physical DMI screens.** Laptop-webcam tests using a DMI photograph only checked
capture/preview and exposed a detection limitation; they are not real-system
validation. Automated recording/replay checks also do not replace that testing.

Run `python scripts/run_webcam.py --camera 0` for live preview and streamed JSONL.
Review instructions and artifacts: `outputs/phase11_review/README.md`.
Recorded-video execution remains `python scripts/run_video.py INPUT`, with
source-named files in `outputs/<video-stem>/`. See `docs/OUTPUT_SPEC.md`.

Phase 9's nine-video review and Phase 10 remain approved. Approved baselines are
retained in `outputs/phase9_final/` and `outputs/phase8_revision_final/`.
Generated outputs are local and Git-ignored; original inputs are unchanged.

## Implemented Functionality

- Frame-source-independent pipeline with perspective display localization,
  tracking, per-frame JSON and annotated video.
- Right display: general Tesseract 5 English title OCR selects Main, Driver ID
  or Level. Border-based title, field and button geometry; template numeric OCR.
  Foreground appearance gate pauses right content under obstruction and clears
  history; outer display geometry and left processing continue.
- Five-frame state confirmation, 15-frame changed numeric-value confirmation,
  and at most three missing observations retaining a field value. Unknown
  states use current regions with neutral semantics, not old screen geometry.
- Left display: 22 boxes, speed panel, motion-verified recovery up to three
  frames, and level-0/1/2 asset matching without temporal icon persistence.
- Phase 9 adds output-contract validation, exact JSON regression classification,
  annotation comparisons, finite metadata/JSON checks and video failure tests.
- Serialized outer-display bboxes now enclose both reported fitted outlines.
  Internal tracking bounds and all recognition/rendering behavior are unchanged.
  Video header frame counts are informational; these recordings' headers exceed
  their actual decoded frame counts.
- Shared `FrameProcessor` owns one source's geometry/right/left temporal state;
  recorded and live runners call the same detection and annotation functions.
- Live capture continuously reads into one replaceable pending-frame slot.
  Monotonic receipt timestamps, skipped-frame counts, processing/latency metrics,
  incremental JSONL, annotated preview and a final PNG are implemented.
- Live history resets on a frame-size change or receipt gap over the configurable
  one-second default. Camera open/read failures are explicit; bounded waits,
  Ctrl-C/preview stop, output protection and cleanup are covered.
- Existing recorded-video output layouts and recognition algorithms are unchanged.

## Latest Verification

- All **100 tests pass**; compilation and Git whitespace checks pass. Live tests
  cover shared-state equivalence, gap/size resets, timestamp validation, latest
  frame replacement, no duplicate delivery, timeout/disconnect/open failure,
  release, headless CLI, incremental JSONL, stop/interrupt and preserved output.
- Three complete recordings processed through the refactored video path:
  `driver_id_12` (233), `driverID_to_level` (855), `level_to_main` (894):
  **1,982 frames**, JSON exactly equals approved Phase 9 and all annotated MP4s
  are byte-identical. Contracts and decoded annotation counts pass.
  Report: `outputs/phase11_review/recorded/verification.json`.
- Full `driver_id_12` replay through the live consumer: **233 frames**, all
  detections exactly match Phase 9 excluding receipt timestamps. Live result
  contracts pass; last annotated PNG visually inspected. This is sequential
  recorded replay, not hardware or camera-rate sampling evidence.
  Report: `outputs/phase11_review/live_replay/verification.json`.
- Replay measured **3.94 processed FPS**, mean processing/annotation **249.5 ms**;
  other regression work was running concurrently, so this is not a controlled
  benchmark or a real-time throughput claim.
- Prior Phase 9 evidence covers all nine videos / 3,457 frames, including the
  three supplied level icons. The other six videos were not rerun for Phase 11.

## Limitations / Review Findings

- Laptop-webcam smoke tests use a rephotographed DMI image, not the final
  system camera or physical DMI setup. Latest trial:
  `outputs/webcam_0_20260928_105406_452553/`, 780 processed frames at 1280×720
  in 27.98 seconds, 12 skipped, no run error; neither display localized.
  The saved final image now contains both displays. Diagnostic replay finds
  two blue components, but their convex hulls occupy only 8.82% and 8.77% of
  the frame after color segmentation, below the existing 10% per-display gate.
  Washed-out screen areas fail the saturation mask (minimum HSV S=80); sampled
  interiors have median S=30 left / 82 right. Samples are diagnostic regions,
  not verified geometry ground truth. Both fits return null before OCR runs.
  Capture/preview work; this photo smoke test fails the existing detector.
  Do not treat this test as final-system validation or tune thresholds solely
  to force this one photograph to pass.
- Camera resolution/driver behavior and live UI transitions still need
  validation with the visible DMI setup. Backend open/read can remain blocked beyond
  the consumer timeout; shutdown warns and process exit releases the device.
- Live frame dropping avoids application backlog, but detection throughput is
  below nominal webcam FPS. Temporal confirmation/retention remains based on
  processed observations, so wall-clock delays grow at low FPS. The gap guard is
  conservative and not calibrated on hardware. No dropped-frame accuracy claim.

- Existing numeric matcher/temporal retention can emit incorrect text: in
  `driver_id_235`, frames 229–243 report `275` while the visible value is `235`.
  The approved transition baseline also has `275` readings; recognition code
  is unchanged. Accepted for Phase 9; remains a potential follow-up correction.
- Title uncertainty suppresses buttons for the last 20 frames of `driver_id_5`.
  `level_0_selected` frame 263 has a misplaced thin title outline above the text.
  These visual limitations were disclosed and accepted with Phase 9 approval.
- Blur can trigger conservative obstruction pauses. The gate detects appearance,
  not hand/robot identity; actual robot footage is untested (synthetic coverage
  only). Screen-colored or bright foreground objects may be missed.
- Only three layouts and three supplied icon assets are supported. General field
  OCR is unimplemented; brief numeric entries may be filtered out.
- No numerical real-video geometry ground truth or holdout set exists. Contract
  checks establish structural validity, not localization or OCR accuracy.

## Next Task

Test and validate the final system's real webcam with the physical DMI screens;
this remains outstanding despite approval to commit the implementation.
Any detector robustness change must
be general, supported by representative cases and checked against approved videos.
