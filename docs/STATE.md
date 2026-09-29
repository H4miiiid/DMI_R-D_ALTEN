# STATE.md — Current Project State

## Purpose

This file records the current V2 development phase and a concise technical summary of completed phases.

Keep it short and update it as the project progresses.

Do not use it as a detailed development diary.

---

## Current Phase

**Phase 1 — Project and Code Structure**

Read and follow the corresponding phase in:

`docs/WORKFLOW.md`

Use `AGENTS.md` for the target code organization and general engineering rules.

The goal of this phase is structural only: reorganize the existing V1 implementation without intentionally changing detection behavior.

---

## V1 Baseline

V1 is the accepted starting point for V2.

Key baseline facts:

- end-to-end recorded-video and webcam processing exists
- `Main`, `Driver ID`, and `Level` are supported
- left-display 22-box detection and existing icon support are implemented
- recorded and live processing share the same core frame-processing path
- 100 tests were passing at the end of V1
- measured replay performance was approximately 3.94 processed FPS

Important known V1 limitations:

- real physical DMI webcam validation is still outstanding
- processing speed is below the desired real-time target
- some OCR and geometry instability remains
- existing structured output is too verbose for the intended V2 workflow

---

## Completed V2 Phases

None yet.

For each completed phase, briefly record:

- phase name and `Completed` status
- main files or modules created, moved, or modified
- important functions or components added or changed
- main verified result
- important limitation only if later phases need to know it

Example:

```text
### Phase 1 — Project and Code Structure — Completed

Files:
- src/dmi/detection/...
- src/dmi/pipeline/...
- src/dmi/output/...

Changed:
- existing V1 modules reorganized by responsibility
- imports, scripts and tests updated

Verified:
- V1 tests still pass
- representative videos still produce equivalent results

Limitation:
- no functional V2 improvements implemented yet
```

---

## After Completing a Phase

Before a phase can be marked as completed:

1. implement the intended work
2. run the relevant tests and evaluation
3. generate the required outputs for review
4. ask the user to review and approve the phase
5. address any user feedback if needed

Only after user approval:

6. move the phase to `Completed V2 Phases`
7. mark it as `Completed`
8. briefly summarize the important technical changes and verified result
9. set the next phase from `docs/WORKFLOW.md` as the new `Current Phase`
10. update `docs/STATE.md`
11. commit the changes
12. push to the remote repository

Do not update the phase as completed, commit, or push before user approval.
