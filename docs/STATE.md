# STATE.md — Current Project State

## Current Phase

**Phase 8 — complete, verified and visually approved on 2026-09-25.**

Phases 1–8 are complete. The user approved the revised Phase 8 output and
requested cleanup, commit and push. Validation used only the two transition
recordings, as requested. The sole retained generated-output folder is
`outputs/phase8_revision_final/`; older runs and temporary review tools were
removed. Original inputs remain unchanged. Generated outputs are local and
Git-ignored; the approved JSON files are the current regression baseline.

## Implemented Functionality

- Source-independent frame processing, per-frame JSON and annotated videos;
  both physical displays have perspective localization and causal tracking.
- Right screen identity now comes from general English Tesseract title OCR.
  Exact supported title words select Main, Driver ID or Level layouts, fitted
  to observed borders. No title-width/field-shape state guessing remains.
  Expanded original-image OCR crops avoid cutting off a title's first letter.
- A frame-local appearance gate checks for foreground over the active right UI
  before detection/OCR. On obstruction, content annotations disappear, state
  becomes unknown, and all right recognition/region history is cleared.
  Detection restarts on the first clear frame. Outer display geometry and the
  unaffected left display continue. JSON exposes visibility explicitly.
- This fixes the cause of the bad early keypad: an occluded first-frame fit
  used to become a persistent anchor. Unknown/pending transitions use current
  regions and neutral semantics, never the previous screen's geometry.
- Five-frame state confirmation, 15-frame changed numeric-value confirmation,
  and bounded missing-value retention remain. Missing display/field resets
  relevant history. Invalid crossed title fits are omitted.
- Main close-button localization fits a pair of borders by separation, so
  camera/scale changes cannot turn the top border into an assumed bottom edge.
- Left display: 22 box identities, speed panel, up to three-frame motion-verified
  recovery, and evidence-based matching of supplied level-0/1/2 assets.
- Tesseract 5 plus English data is a new runtime dependency; setup is documented
  in PROJECT.md. No custom title vocabulary or video answers are fed to OCR.

## Verification

- 72 applicable tests pass: synthetic geometry, recognition, OCR integration,
  transition/temporal sequences, obstruction/tool shapes, recovery, annotation
  and video I/O. The one test reading an older development video is excluded
  under the user's two-video constraint.
- Both complete transition videos were processed from source: 1,749 frames.
  Full annotation decode counts match JSON. All 40,055 left and 18,803 right
  emitted regions pass finite/convex, bbox and center integrity checks.
- Left-display JSON is unchanged on every frame relative to the previous
  Phase 8 snapshot. Independent right replay matches both full pipeline runs.
- Startup obstruction pauses Driver ID frames 0–60; processing resumes at 61
  (~2.10 s), with confirmed Driver ID at 66 (~2.28 s) after title uncertainty.
  Inspected early clear-frame comparisons show the corrected keypad alignment.
- Driver ID → Level confirms at frame 563, four frames / 0.138 s after the clear
  screen at 559. Level → Main confirms at 532, three frames / 0.103 s after
  clear frame 529. No wrong known state occurs outside mixed redraw frames.
- Obstruction gate pauses 155 and 245 frames respectively; some motion-blur
  pauses are conservative. OCR uncertainty can briefly suppress annotations.
- Agent inspected source/annotation pairs, early before/after grids, occlusions,
  recovery and transition frames, including the corrected Main close button.
- Full-run throughput is 4.12 FPS aggregate (decode/OCR/annotation/encode/JSON,
  with some concurrent diagnostics), not a controlled performance benchmark.
- Compilation and Git whitespace checks pass. Review videos, comparisons,
  metrics and limitations: `outputs/phase8_revision_final/README.md`.
- No numerical real-video geometry ground truth or holdout set exists. Source
  transition boundaries are manual visual observations, not border annotations.
  The previous Phase 8 run is a comparison snapshot, not an approved baseline.

## Limitations / Next Task

- The visibility gate detects appearance inconsistent with the blue UI, not
  hand/robot identity. Robot behavior has only synthetic tool-shape coverage;
  screen-colored objects and bright objects over white fields may be missed.
  Motion blur can conservatively trigger pauses. Actual robot footage is needed.
- Only three UI layouts and three level icon assets are supported. General
  field OCR remains unimplemented; brief numeric entries can be filtered out.
- Real-time performance remains unachieved.

Next development phase: Phase 9 — End-to-End Integration. Not started.
