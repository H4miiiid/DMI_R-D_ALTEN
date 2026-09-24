# STATE.md — Current Project State

## Current Phase

**Phase 7 — Temporal Stability: complete and visually approved.**

Phases 1–7 are complete and visually approved. The user approved Phase 7,
accepted its reported limitations, and authorized committing and pushing.
Approved Phase 7 artifacts: `outputs/phase7_validation/README.md`.

**Phase 8 — Transitions has not started.** The user explicitly requested that
work stop after committing and pushing Phase 7; await further instruction.

## Implemented Functionality

- Source-independent `process_frame()` and recorded-video processing produce
  per-frame JSON and original-resolution annotated MP4s with overwrite protection.
- Both physical displays have perspective localization and causal stabilization.
- The right display recognizes Main, Driver ID, and Level, localizes titles,
  buttons, and fields, reads numeric values, and stabilizes geometry/OCR.
  Title text comes from state classification; OCR is not general text OCR.
- The left display detects 22 stable box identities and the speed panel using
  exposure-normalized border evidence and UI topology. Motion-verified optical
  flow bridges at most three missed region measurements.
- `icons.py` rectifies each detected left box independently and compares bright
  foreground shapes with supplied level-0/1/2 assets and generic stroke-width
  variants. Match strength and separation govern abstention. No box identity,
  filename, reference-frame coordinates, or previous icon supplies the answer.
- Icon labels appear in JSON and the corresponding box annotations. `null`
  means no confident known-icon match, not verified emptiness. There is no icon
  temporal persistence, so genuine changes are not delayed by a history buffer.
- `scripts/evaluate.py` runs full-video validation against an approved baseline.

## Phase 7 Implementation

- Right-field OCR retains its previous value for at most three consecutive
  unreadable observations within an unchanged recognized state, then returns
  `null`. Missing OCR or uncertain state breaks changed-value confirmation.
- Missing field clears value history. Missing physical right-display geometry
  resets all right-display recognition/geometry history immediately; fresh
  recognition is accepted on reacquisition.
- Existing geometry stabilization, icon recognition, 15-frame numeric-change
  confirmation, and five-frame state debounce remain in place. Full state
  transitions remain Phase 8 work.
- Seven new sequence tests and a labeled 35-frame synthetic loss/recovery demo
  check bounded expiry, reset, and responsiveness. These limits count frames.

## Latest Verification

- **55 tests pass**, including the seven new temporal sequence tests and all
  earlier geometry, icon, recognition, and annotation checks. Python compilation
  and `git diff --check` pass.
- All **1,708 frames in seven complete videos** processed; all annotated videos
  fully decoded with frame counts matching JSON.
- Final-source replay produces **exactly the approved Phase 6 JSON for every
  frame**, including icons, geometry, and right-display results.
- All emitted left regions pass finite/convex geometry, enclosing-bbox, and
  center-inside-region checks. Complete left layouts remain **1,701/1,708**.
- Selected-level recordings: level 0 recognized in **262/264** frames, level 1
  in **262/262**, level 2 in **239/239**; each association is `box_4`.
  No known level-icon assignments occur in the other four recordings or boxes.
- This end-to-end run averaged **5.46 FPS**, including decode, annotation,
  encoding, and JSON writing, with concurrent validation work. This is not a
  controlled performance comparison with Phase 6 (5.96 FPS); still not real-time.
- Agent inspected representative Phase 7 annotations and synthetic expiry,
  disappearance, and recovery frames. The 35-frame synthetic demo was fully
  decoded and assertions verified its expected behavior. The user approved
  the visual output and accepted the reported limitations.

These are development prediction counts and regression/consistency results,
not holdout accuracy or real-video border-error measurements. There are no
verified machine-readable real-video coordinates or holdout sets.

## Known Limitations and Next Task

- Level-0 selected frames **0–1** return `icon: null` because blur makes the
  asset scores insufficiently distinct. Recognition starts at frame 2.
- Previously accepted left-layout gaps remain: `driver_id_12` frames 36–38;
  `level_0` frames 26–28 and 34. Unsupported regions are omitted.
- Only the three supplied level assets are recognized. Power/scroll symbols
  remain unsupported; low exposure, heavier blur, and unseen symbols may cause
  abstention or need additional validation. Real icon transitions are not in
  the current recordings; change/removal tests are synthetic.

Next: await the user's instruction. Phase 8 transition work is not authorized
to start in this task.
