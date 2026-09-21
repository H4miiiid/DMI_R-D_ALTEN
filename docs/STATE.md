# STATE.md — Current Project State

## Purpose

This file records the current verified development phase and a short technical summary of completed phases.

Keep it concise and update it as the project progresses.

Do not use it as a detailed development diary.

---

## Current Phase

**Phase 1 — Understand the Data**

Read and follow the corresponding phase in:

`docs/WORKFLOW.md`

Use the related project documents referenced there for requirements and completion conditions.

---

## Completed Phases

None yet.

For each completed phase, briefly record:

- phase name
- status: `Completed`
- main files created or modified
- important functions, methods, or components implemented
- key verified result
- important remaining limitation, only if the next phase needs to know it

Example:

```text
### Phase 2 — Basic Processing Pipeline — Completed

Files:
- src/dmi/pipeline.py
- scripts/run_video.py

Implemented:
- process_frame()
- video frame loop
- JSON result generation
- annotated video output

Verified:
- representative development videos process from start to finish

Limitation:
- UI detection is not implemented yet
```

Keep each completed-phase summary short.

---

## After Completing a Phase

When the current phase is verified:

1. move it to `Completed Phases`
2. mark it as `Completed`
3. briefly record the important files, functions, methods, or components added or changed
4. record the main verified result and any important limitation
5. set the next phase from `docs/WORKFLOW.md` as the new `Current Phase`
6. keep this file concise
7. follow the Git workflow in `AGENTS.md`

Do not advance to the next phase until the current phase satisfies its completion conditions.
