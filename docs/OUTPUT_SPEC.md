# OUTPUT_SPEC.md — V2 Output Format

## 1. Purpose

This document defines the outputs produced by the V2 DMI pipeline.

V2 should produce:

- an annotated output video
- a compact JSONL log
- optional detailed debug output when explicitly requested

The default JSONL should contain useful state information without repeating nearly identical results for every processed frame.

Detailed UI requirements are defined in `docs/UI_SPEC.md`.

---

## 2. Default Output

Given:

```text
data/videos/dev/train_numbers.mp4
```

the default outputs should use a predictable source-based location such as:

```text
outputs/Version 2/train_numbers/
├── train_numbers_annotated.mp4
└── train_numbers.jsonl
```

Original files under `data/` must never be modified.

---

# 3. JSONL Instead of One Large JSON

The default structured output should use **JSONL**.

Each line is an independent JSON record:

```text
{record 1}
{record 2}
{record 3}
```

This allows the pipeline to:

- write results incrementally
- avoid keeping a complete video result in memory
- preserve already written results during long processing
- support future real-time processing more naturally

The JSONL file is primarily a compact structured log for debugging, validation, and future integration.

---

# 4. Compact Output Principle

Do not write a complete copy of the same UI state for every frame.

For example, avoid:

```text
frame 100 → Train Running Number = 128
frame 101 → Train Running Number = 128
frame 102 → Train Running Number = 128
frame 103 → Train Running Number = 128
```

when nothing meaningful changed.

Write a new record when important information changes or when a new UI state needs to be represented.

Important changes include:

- screen/state change
- title change
- field value change
- button appearance/disappearance
- icon change
- important layout change

Small coordinate jitter alone should not create unnecessary JSONL records.

This is output compaction, not the future backend publication policy.

---

# 5. Record Types

Keep the number of record types small.

Recommended types are:

```text
session_start
snapshot
update
session_end
```

---

## 5.1 Session Start

The first record describes the input.

Example:

```json
{
  "type": "session_start",
  "source": "train_numbers.mp4",
  "width": 2304,
  "height": 1728,
  "fps": 10.0
}
```

---

## 5.2 Snapshot

A `snapshot` contains the current relevant DMI state.

Use it when:

- processing begins
- the active screen changes
- the UI layout changes significantly
- a complete current state is useful

Example:

```json
{
  "type": "snapshot",
  "frame": 120,
  "timestamp": 12.0,
  "right_display": {
    "state": "Train Running Number",
    "title": "Train running number",
    "field": {
      "value": "128"
    },
    "buttons": {
      "digit_1": [1210, 650],
      "digit_2": [1350, 650],
      "digit_3": [1490, 650],
      "close": [1160, 940]
    }
  }
}
```

For compact output, button values may contain only their center coordinates unless additional geometry is useful.

---

## 5.3 Update

An `update` contains only information that changed from the previous stable state.

Example:

```json
{
  "type": "update",
  "frame": 245,
  "timestamp": 24.5,
  "right_display": {
    "field": {
      "value": "12"
    }
  }
}
```

Another example:

```json
{
  "type": "update",
  "frame": 380,
  "timestamp": 38.0,
  "right_display": {
    "state": "Train Data",
    "train_type": "Lambda"
  }
}
```

Do not repeat unchanged information unnecessarily.

---

## 5.4 Session End

The last record may summarize the processing run.

Example:

```json
{
  "type": "session_end",
  "processed_frames": 2400,
  "duration_seconds": 240.0,
  "processing_seconds": 310.4
}
```

Additional performance information may be included when useful.

---

# 6. Coordinate System

All coordinates in final structured output must refer to the **original input frame**.

Internal processing may use:

- crops
- resized images
- rectified displays
- perspective transforms

but final coordinates must be mapped back to original-frame coordinates.

For a center point use:

```text
[x, y]
```

For a rectangular region use:

```text
[x1, y1, x2, y2]
```

where:

- `x1`, `y1` = top-left
- `x2`, `y2` = bottom-right

---

# 7. Right Display Output

Depending on the active screen, relevant information may include:

```json
{
  "state": "Train Data",
  "title": "Train data",
  "fields": {},
  "buttons": {}
}
```

Known V2 states include those defined in `docs/UI_SPEC.md`.

For an unknown screen:

```json
{
  "state": "unknown"
}
```

Unknown state must not prevent detected elements from being reported.

---

## 7.1 Titles

Store the recognized title text when required.

Example:

```json
"title": "Train running number"
```

If the title cannot be read reliably:

```json
"title": null
```

---

## 7.2 Fields

Only fields required by `docs/UI_SPEC.md` need to be included.

Example:

```json
"fields": {
  "train_type": {
    "value": "Gamma"
  }
}
```

Train Running Number:

```json
"fields": {
  "train_running_number": {
    "value": "128"
  }
}
```

Validate Train Data:

```json
"fields": {
  "validation": {
    "value": "Yes"
  }
}
```

Field geometry may also be included when useful for debugging or downstream use.

---

## 7.3 Buttons

Buttons should use stable logical names when known.

The compact default representation should prioritize the center point:

```json
"buttons": {
  "gamma": [1200, 610],
  "lambda": [1450, 610],
  "close": [1130, 930],
  "enter_data": [1480, 930]
}
```

If full geometry is required later, it may be represented as:

```json
"gamma": {
  "center": [1200, 610],
  "bbox": [1100, 560, 1300, 660]
}
```

Do not invent semantic button names on unknown screens.

---

# 8. Left Display Output

For V1-style left-display layouts, relevant output may include:

- logical box IDs
- box centers
- icon associations
- speed indicator

Compact example:

```json
"left_display": {
  "boxes": {
    "box_1": {
      "center": [320, 410],
      "icon": null
    },
    "box_2": {
      "center": [470, 410],
      "icon": "level1_icon"
    }
  }
}
```

During Train Data workflows, only the required elements defined in `docs/UI_SPEC.md` should be reported.

Do not force the 22-box representation onto a different left-display layout.

---

# 9. Icons

When an icon is confidently identified:

```json
"icon": "level1_icon"
```

When no supported icon is present:

```json
"icon": null
```

Icon labels should come from the supported asset set under:

`data/icons/`

---

# 10. Unknown and Missing Values

Use `null` when information exists conceptually but cannot be determined reliably.

Example:

```json
"value": null
```

Use an empty collection when no elements of that type are detected:

```json
"buttons": {}
```

Do not fabricate values only to keep the JSON complete.

---

# 11. Geometry and Small Jitter

Internal detections may vary slightly between frames.

For example:

```text
[1200, 600]
[1202, 599]
[1199, 602]
```

Such small movement should not automatically create separate compact JSONL records.

The compact logger may use reasonable geometric tolerance when deciding whether the structured state meaningfully changed.

Full-precision detections should remain available internally for annotation and debugging.

Exact compaction tolerances should be validated in `docs/EVALUATION.md`.

---

# 12. Optional Verbose Debug Mode

When detailed investigation is required, an optional mode may save per-frame structured output.

Example:

```text
train_numbers_debug.jsonl
```

Verbose mode may contain:

- every processed frame
- full bounding boxes
- detection confidence/evidence
- intermediate geometry
- OCR observations
- timing information

This should not be the default output because it may become very large.

---

# 13. Annotated Video

The annotated video should represent the detections used by the structured output.

Depending on the active UI state, annotations may show:

- display boundaries
- title
- fields and OCR values
- buttons
- button centers
- left-display boxes
- icons
- speed indicator

The annotated video may contain per-frame geometry even when the compact JSONL does not store every small geometric change.

Keep annotations readable.

---

# 14. Incremental Writing

JSONL records should be written while processing is running.

Do not wait until the complete video has finished before writing all structured output.

Long-running processing should also show visible progress, for example:

```text
Processing: 1240 / 2400 frames
Elapsed: 02:43
Processing FPS: 7.6
```

Progress reporting should not significantly slow the pipeline.

---

# 15. Future Backend Use

The V2 JSONL format is not itself the final backend communication protocol.

However, its state representation should be designed so the same compact detection result can later be passed to a real-time publisher.

Conceptually:

```text
Detection
    ↓
Temporal stabilization
    ↓
Structured DMI state
   / \
JSONL  Future backend publisher
```

Do not couple detection logic directly to network communication.

---

# 16. Output Consistency

Across the project:

- use stable state names
- use stable button names
- use stable field names
- keep coordinate conventions unchanged
- use `null` consistently
- avoid unnecessary duplicate records
- keep JSONL valid even if processing stops before the video ends

Any intentional schema change must also update this document.

---

## Core Rule

The default V2 output should provide the **important stable information from the DMI without reproducing the complete detection state for every frame**.

Keep detailed frame-level information available only when it is genuinely useful for debugging or evaluation.
