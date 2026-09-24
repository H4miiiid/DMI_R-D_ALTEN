# OUTPUT_SPEC.md — Structured Output and Coordinates

## 1. Purpose

This document defines the structured output produced by the video-processing pipeline.

The output should be:

- simple
- consistent
- machine-readable
- human-readable
- stable across the project

Detailed UI behavior belongs in `docs/UI_SPEC.md`.

---

## 2. Output Types

Processing a video should eventually produce:

- structured JSON results
- annotated video or frames for visual verification

Generated outputs must remain separate from the original files under `data/`.

---

## 3. Frame-Level Output

Results should be stored per processed frame.

Each frame should include at least:

- frame index
- timestamp
- right-display result
- left-display result

Example:

```json
{
  "frame_index": 120,
  "timestamp": 4.0,
  "right_display": {},
  "left_display": {}
}
```

Each display result includes nullable display geometry. Geometry uses the
original-frame coordinates defined below.

---

## 4. Coordinate System

All final coordinates must refer to the **original input video frame**.

Internal processing may:

- resize
- crop
- rectify
- warp
- transform

but reported coordinates must be mapped correctly back to the original frame.

Use:

```text
[x, y]
```

for points.

For rectangular regions use:

```text
[x1, y1, x2, y2]
```

where:

- `x1`, `y1` = top-left
- `x2`, `y2` = bottom-right

Coordinates should use pixels unless explicitly changed later.

When a visible UI region is rotated or affected by perspective, also report
its four detected corners in clockwise order starting at the top-left. The
axis-aligned `bbox` remains available for rectangular-region consumers, while
`corners` is the authoritative geometry for visual alignment.

---

## 5. Right Display

A typical right-display result should contain:

```json
{
  "geometry": {},
  "state": "Driver ID",
  "title": {},
  "buttons": {},
  "data_field": {}
}
```

### Display Geometry

When a display is localized reliably:

```json
"geometry": {
  "corners": [[1020, 180], [1640, 195], [1610, 1450], [990, 1435]],
  "oriented_box": [[1000, 175], [1640, 190], [1610, 1450], [970, 1435]],
  "bbox": [990, 180, 1640, 1450],
  "center": [1315, 815]
}
```

Corners are ordered clockwise starting at the top-left corner:

```text
top-left → top-right → bottom-right → bottom-left
```

`corners` describes the perspective quadrilateral used for rectification.
`oriented_box` is a detected minimum-area rectangle around the display. It is
used for annotation, follows the display's rotation, and has perpendicular
adjacent edges. `bbox` is the axis-aligned bounds retained for rectangular
region consumers.

If a display cannot be localized reliably:

```json
"geometry": null
```

### State

Known examples:

```json
"state": "Main"
```

```json
"state": "Driver ID"
```

```json
"state": "Level"
```

For an unrecognized screen:

```json
"state": "unknown"
```

An unknown state must not prevent other visible elements from being reported.

---

## 6. Title

When a title is detected:

```json
"title": {
  "text": "Driver ID",
  "corners": [[1020, 180], [1450, 190], [1445, 260], [1015, 250]],
  "bbox": [1020, 180, 1450, 260]
}
```

If no reliable title is available:

```json
"title": null
```

If the title region is reliable but its text is not, preserve the localized
region and return `"text": null`.

Do not fabricate OCR text.

---

## 7. Buttons

Buttons should be reported using stable logical labels when their identity is known.

Example:

```json
"buttons": {
  "button_1": {
    "corners": [[1100, 410], [1220, 414], [1218, 484], [1098, 480]],
    "bbox": [1100, 410, 1220, 480],
    "center": [1160, 445]
  },
  "button_2": {
    "bbox": [1240, 410, 1360, 480],
    "center": [1300, 445]
  }
}
```

The center point is an important required output.

For unknown/new screens, buttons may still be reported even if their semantic identity is not known.

Use neutral labels such as:

```text
button_1
button_2
button_3
```

Do not invent semantic names.

If no buttons are detected:

```json
"buttons": {}
```

---

## 8. Data Field

When a recognized data field is present:

```json
"data_field": {
  "corners": [[1060, 520], [1400, 526], [1398, 656], [1058, 650]],
  "bbox": [1060, 520, 1400, 650],
  "value": "12"
}
```

Another example:

```json
"data_field": {
  "bbox": [1060, 520, 1400, 650],
  "value": "LEVEL 2"
}
```

If no data field exists or it cannot be identified reliably:

```json
"data_field": null
```

Do not fabricate values.

---

## 9. Left Display

The left-display result should contain:

- the 22 logical boxes
- icon association for each box
- analog speed indicator

Example:

```json
"left_display": {
  "geometry": {},
  "boxes": {},
  "speed_indicator": {}
}
```

---

## 10. Left-Side Boxes

Use stable identities:

```text
box_1
box_2
...
box_22
```

Each box should contain at least:

- bounding box
- center point
- icon state

Example:

```json
"box_5": {
  "bbox": [400, 250, 520, 340],
  "center": [460, 295],
  "icon": "level1_icon"
}
```

For an empty box:

```json
"box_5": {
  "bbox": [400, 250, 520, 340],
  "center": [460, 295],
  "icon": null
}
```

Box identities must remain consistent across frames. The physical mapping is
defined in `UI_SPEC.md` §5.1. Each detected box also includes authoritative
perspective `corners`; the `bbox` encloses those corners. Left-region corners
and centers retain two decimal places in original-frame pixels. The center is
the rectified region center mapped back through the display transform.

Icon recognition searches each detected box for the supplied level assets.
`icon` is `level0_icon`, `level1_icon`, or `level2_icon` when supported by
a sufficiently distinct full-shape match. `icon: null` means no known icon
was confidently recognized: the box may be empty, contain an unsupported
symbol, or have ambiguous/blurred evidence. It is not proof of emptiness.
Recognition uses the current frame; it does not retain an earlier icon after
the evidence disappears. Multiple accepted candidates within one box also
return `null`, because the schema holds only one identity per box.
A box without reliable current or short-term tracked geometry is omitted from
`boxes`; a completely unsupported layout returns an empty collection.

---

## 11. Speed Indicator

At minimum report its location. The speed indicator uses the same `corners`,
`bbox`, and `center` conventions as left-side boxes, and is `null` when its
panel cannot be localized reliably. Its panel extent is defined in `UI_SPEC.md`.

Example:

```json
"speed_indicator": {
  "bbox": [300, 620, 480, 800],
  "center": [390, 710]
}
```

If interpretation of the analog value is added later, it may be added without changing the rest of the output structure.

---

## 12. Unknown and Missing Values

Use explicit `null` values when information is expected but cannot be determined reliably.

Examples:

```json
"title": null
```

```json
"data_field": null
```

```json
"icon": null
```

Use empty collections when the relevant collection exists but contains no detected elements:

```json
"buttons": {}
```

Do not use guessed values merely to make the output complete.

---

## 13. Optional Confidence

Confidence values may be maintained internally when useful.

They should only be exposed in the final JSON if they provide clear value.

Avoid making the output unnecessarily complex.

If confidence is included later, use a consistent range and document it here.

---

## 14. Video-Level JSON

A complete video output may use a structure such as:

```json
{
  "video": "driver_id_12.mp4",
  "frames": [
    {
      "frame_index": 0,
      "timestamp": 0.0,
      "right_display": {
        "geometry": {
          "corners": [[1020, 180], [1640, 195], [1610, 1450], [990, 1435]],
          "oriented_box": [[1000, 175], [1640, 190], [1610, 1450], [970, 1435]],
          "bbox": [990, 180, 1640, 1450],
          "center": [1315, 815]
        },
        "state": "Driver ID",
        "title": {
          "text": "Driver ID",
          "bbox": [1020, 180, 1450, 260]
        },
        "buttons": {},
        "data_field": {
          "bbox": [1060, 520, 1400, 650],
          "value": "12"
        }
      },
      "left_display": {
        "geometry": {
          "corners": [[200, 150], [850, 175], [820, 1460], [180, 1430]],
          "oriented_box": [[190, 145], [850, 170], [820, 1460], [160, 1435]],
          "bbox": [180, 150, 850, 1460],
          "center": [513, 804]
        },
        "boxes": {},
        "speed_indicator": null
      }
    }
  ]
}
```

The exact schema may evolve when implementation begins, but changes should remain backward-consistent when practical.

---

## 15. Annotated Output

Annotated video or frames must represent the same detections stored in the structured result.

Do not draw visual boxes that are not represented in the corresponding structured output.

Annotations may show:

- display regions
- screen state
- titles
- data fields
- buttons
- center points
- left-side boxes
- icons
- speed indicator

Keep overlays readable and useful for user review.

---

## 16. Output Consistency

For the same logical element across frames:

- labels should remain stable
- coordinate conventions must remain unchanged
- JSON structure should remain consistent
- unknown values should use the same representation

Do not change field names or coordinate conventions casually during development.

If the output format changes, update this document and any related evaluation code.

---

## 17. Core Rule

The structured output must describe what the pipeline actually detected.

It must never contain hardcoded or fabricated information simply to match an expected result.
