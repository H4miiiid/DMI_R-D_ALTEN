# UI_SPEC.md — Interface Structure and Behavior

## 1. Purpose

This document defines the visual structure and expected behavior of the physical interface shown in the input videos.

The interface contains two main regions:

- **Right display**
- **Left display**

The pipeline must understand these regions consistently across video frames.

This document defines **what should be detected and understood**, not which computer-vision algorithm should be used.

---

## 2. Visual References

Annotated reference images may be used to understand the expected UI regions, element identities, borders, and annotation style.

Current references include:

- Left display: `data/reference/overlays/left_rectified_annotated_01.png`
- Right display: `data/reference/overlays/right_rectified_annotated_01.png`
- Example Main screen: `data/reference/overlays/main0_01.png`

Additional annotated examples may be added for individual right-display states such as:

- `Main`
- `Driver ID`
- `Level`
- other useful screen examples

When new reference images are added, document their paths in this section.

These images are **visual references**, not fixed coordinate templates.

The pipeline must not assume that elements always appear at exactly the same pixel coordinates as the examples.

---

## 3. General Interface Behavior

The interface is recorded by a webcam.

Its appearance may vary because of:

- small camera or display movement
- camera-distance and scale changes
- small rotations or perspective changes
- lighting and brightness changes
- reflections
- blur
- temporary instability

Detected geometry must follow the real visible interface.

A previously correct pixel coordinate is not automatically correct for another frame.

---

# 4. Right Display

The right display is a **stateful UI** that can switch between different screens.

Known examples currently include:

- `Main`
- `Driver ID`
- `Level`

Other screens may appear later.

Each screen may contain a different combination of:

- title
- buttons
- data fields
- other bordered UI elements
- displayed text or values

The pipeline must understand the visible structure rather than depending only on a fixed list of known screens.

### 4.0.1 Observed Development Layouts

The current development recordings show these stable screen structures:

- `Main`: a title, a two-column grid of menu buttons, and a close button near
  the lower-left of the display. The visible menu labels include `Start`,
  `Driver ID`, `Train Data`, `Level`, `Train running number`, `Shunting`,
  `Non-Leading`, `Maintain Shunting`, and `Radio Data`. One grid cell is
  visibly empty.
- `Driver ID`: a title, a light data field, a numeric keypad, and a bottom row
  of action controls. The development recordings show values `5`, `12`, and
  `235`.
- `Level`: a title, a light data field, a three-column option grid, an
  additional ellipsis control, and a close button. The current recording shows
  `Level 0` in the field.

These observations describe current coverage, not a closed list of layouts or
values.

---

## 4.1 Screen State

The pipeline should identify the current right-display state whenever possible.

Known states should use stable names:

```text
Main
Driver ID
Level
```

If the visible screen does not correspond reliably to a known state, classify it as an **unknown/new screen** rather than forcing it into a known category.

An unknown screen must **not stop further processing**.

Screen recognition and UI-element detection are separate responsibilities.

Therefore:

```text
Known screen
    ↓
Recognize state + detect its visible elements

Unknown/new screen
    ↓
Unknown state + still detect visible elements
```

The current state may change during a video.

Real state changes should be detected without unnecessary frame-to-frame flickering.

---

## 4.2 Unknown and New Screens

The pipeline must remain useful when a previously unseen right-display screen appears.

For a new or unknown screen:

- mark the screen state as unknown/new
- continue locating the right display
- detect visible title regions when possible
- apply OCR to visible title text when possible
- detect visible buttons
- calculate button centers
- detect other clearly bordered UI regions when their role can be determined safely
- annotate detected elements normally

Do not ignore the screen simply because its layout was not previously documented.

For example, if an unknown screen visibly contains:

```text
Title
Button
Button
Button
```

the pipeline should still detect and annotate those elements even though the overall screen state is unknown.

Visible borders and UI structure should be used to localize elements where reliable.

Do not invent semantic labels for elements whose meaning is unknown.

A new screen can later be added as a known state once its structure and meaning are understood and documented.

---

## 4.3 Title

The right display contains a title region when the active UI screen provides one.

The title should be:

- localized correctly
- read using OCR
- associated with the current screen

Known examples include:

```text
Main
Driver ID
Level
```

For an unknown screen, the title should still be detected and read when visible.

The title value must come from the visible interface.

Do not hardcode it based on the video filename or previous state.

Temporary OCR noise should not cause unnecessary title changes.

---

## 4.4 Buttons

Different buttons may appear depending on the active screen.

For every relevant visible button, determine:

- its location
- its logical identity when known
- its center point

Buttons should still be detected on unknown screens when their visible geometry can be identified reliably.

If the semantic identity of a button is unknown, preserve the detection without inventing a meaning.

Button geometry must follow the real visible button when:

- the camera moves
- the display shifts
- scale changes

Do not keep an old button position when the actual interface has moved.

---

## 4.5 Data Fields

Some right-display screens contain a data field.

Examples include:

- Driver ID values
- Level values
- values appearing on other screens

When a known data field exists, determine:

- whether it is present
- where it is located
- its displayed value

If an unknown screen contains a clearly visible bordered field, it may still be localized and annotated when reliable, but do not assign an unsupported semantic meaning to it.

If no data field is present, do not invent one.

OCR cleaning may be used when justified, but uncertain text must not be converted into a fabricated result.

---

# 5. Left Display

The left display is structurally more stable than the right display.

It contains:

- **22 logical UI boxes**
- optional icons inside those boxes
- **1 analog speed indicator**

Its position and scale in the camera frame may change.

The pipeline must maintain consistent logical identities for these elements across frames.

---

## 5.1 Left-Side Boxes

All 22 logical boxes should be identified using stable identities:

```text
box_1
box_2
box_3
...
box_22
```

The mapping between each physical box and its logical label must remain consistent.

For every box determine at least:

- location
- center point

The detected geometry should closely follow the intended visible borders.

Avoid boxes that:

- include large unrelated areas
- overlap neighboring boxes incorrectly
- drift unnecessarily
- remain fixed while the display moves
- resize because of temporary brightness changes rather than real geometry changes

The current annotated reference indicates how the 22 non-speed regions are
grouped:

- 9 vertically stacked sidebar regions
- 4 first-row status regions plus 1 power region
- 1 merged second-row status region plus 4 additional second-row regions
- 1 main lower region
- 2 scroll-control regions

The Phase 5 mapping follows the physical regions in the annotated reference:

- `box_1`–`box_9`: sidebar regions R1–R9, from top to bottom
- `box_10`: isolated first-row status region at the left of the speed panel
- `box_11`–`box_13`: the three adjacent first-row status regions, left to right
- `box_14`: power region at the right of that row
- `box_15`: merged leftmost region of the second status row
- `box_16`–`box_19`: the remaining four second-row regions, left to right
- `box_20`: main lower region
- `box_21`: upper scroll-control region
- `box_22`: lower scroll-control region

The unusually tall sidebar R2 is one logical region. Empty-looking regions
retain their identities. This mapping is based on the reference's named regions;
its generated annotations were visually approved by the user in Phase 5.

---

## 5.2 Icons

Icons may appear inside one or more left-side boxes.

Known icon assets are stored under:

`data/icons/`

For every box determine:

- whether an icon is present
- which known icon it is
- which box contains it

The important relationship is:

```text
box → icon
```

For example:

```text
box_5 → level1_icon
```

An empty box should remain:

```text
box_5 → null
```

Do not assign an icon when evidence is insufficient.

Only use icon identities supported by the available assets or documented UI definitions.

The current assets and recordings cover `level0_icon`, `level1_icon`, and
`level2_icon`. Each appears in the same left-sidebar region in its corresponding
selected-level recording. The asset bitmaps are clean UI renderings; the video
appearance is affected by camera blur, scale, perspective, and brightness.

---

## 5.3 Analog Speed Indicator

The left display contains one analog speed indicator.

At minimum:

- localize it
- maintain its identity
- track its position with the display

The localization represents the rectangular `LEFT_SPEED` panel shown in the
reference, not a tight circle around the dial. Its lower portion intentionally
contains the first-row status and power regions; this overlap is part of the
reference's region definitions. The reported center is the panel center, not
a measurement of the needle pivot.

Detailed interpretation of its analog value may be added later if required.

---

# 6. Geometry and Bounding Boxes

UI geometry must follow real visual movement.

The system should tolerate reasonable:

- horizontal and vertical movement
- scale changes
- camera-distance changes
- small rotations
- perspective changes

Bounding boxes should closely represent the intended visible UI regions.

Check:

- left border
- right border
- top border
- bottom border
- center point

Stable geometry should produce stable detections.

Real movement should cause the detections to move accordingly.

---

# 7. Temporal Behavior

Video frames are related over time.

Temporal information may be used to improve stability.

Avoid unnecessary:

- bounding-box jumping
- center-point oscillation
- OCR flickering
- icon flickering
- screen-state flickering

At the same time, stabilization must not hide genuine changes.

The system should react when:

- the screen state changes
- a new/unknown screen appears
- a title changes
- a data value changes
- a button appears or disappears
- an icon appears or disappears
- the display physically moves

The goal is a balance between **stability and responsiveness**.

---

# 8. Screen Transitions

Transitions may occur between known or unknown right-display states.

Examples include:

```text
Main → Driver ID
Driver ID → Level
Level → Main
Known Screen → Unknown Screen
Unknown Screen → Known Screen
```

Transition handling does not need to be completed before stable individual-screen processing works reliably.

The pipeline should eventually avoid:

- rapid state oscillation
- keeping an old state too long
- switching states because of one unclear frame
- stopping element detection while a new state is being identified

Detailed transition evaluation belongs in:

`docs/EVALUATION.md`

---

# 9. Unclear Frames

Some frames may be difficult to interpret because of:

- blur
- reflection
- camera movement
- partial visibility
- brightness changes
- poor OCR visibility

When reliable information is unavailable, prefer an unknown or null result rather than inventing a confident detection.

Previous-frame information may be preserved only when temporally justified.

---

# 10. Visual Annotation

Generated annotated frames and videos should make verification easy.

Useful annotations may include:

- right-display region
- left-display region
- screen state
- title region and OCR text
- data-field region and value
- buttons
- button centers
- other detected bordered UI regions
- left-side boxes
- icon identities
- box centers
- speed indicator

Unknown screens should still receive normal visual annotations for elements that were detected successfully.

Keep annotations readable and avoid excessive debug text.

Visual annotations must correspond to the same detections represented in the structured output.

---

# 11. Core UI Requirements

The final pipeline should maintain these properties:

1. known right-display states are identified when reliable
2. unseen screens remain processable as unknown/new states
3. detection continues even when the screen state is unknown
4. visible titles are localized and read when possible
5. visible buttons are detected and their centers calculated
6. data fields are localized and read when their role is known
7. unsupported semantic meanings are not invented
8. all 22 left-side boxes retain stable identities
9. left-display geometry follows real movement
10. icons are assigned to the correct boxes
11. empty boxes remain empty
12. the speed indicator remains localized
13. stable frames produce stable results
14. genuine UI changes are detected without excessive delay

Detailed output representation belongs in:

`docs/OUTPUT_SPEC.md`

Detailed evaluation rules belong in:

`docs/EVALUATION.md`
