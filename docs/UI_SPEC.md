# UI_SPEC.md — Interface Structure and Behavior

## 1. Purpose

This document defines the UI elements that the pipeline must recognize, detect, annotate, and extract from the DMI displays.

V2 extends the V1 interface with new Train Data and Train Running Number screens while preserving support for the existing screens.

This document defines **what should be detected**, not which computer-vision method must be used.

---

## 2. Input and Visual References

Development videos are stored under:

`data/videos/dev/`

V2 includes:

- `train_data_gamma.mp4`
- `validate_train_data.mp4`
- `train_numbers.mp4`

Previous V1 videos remain valid development and regression inputs.

Reference screenshots for the new layouts may be stored under:

`data/reference/`

Use reference images to understand screen structure and expected borders, but do not use them as fixed pixel-coordinate templates.

---

# 3. Display Behavior

The physical interface contains:

- **Left display**
- **Right display**

Both displays may change their content depending on the active workflow.

V2 must therefore not assume that the left display always contains the previous 22-box layout.

Known UI states now include:

- `Main`
- `Driver ID`
- `Level`
- `Train Data`
- `Validate Train Data`
- `Train Data (1/2)`
- `Train Data (2/2)`
- `Train Running Number`

Other screens may still appear and must remain processable as unknown/new states.

---

# 4. Existing V1 Screens

Existing behavior for:

- `Main`
- `Driver ID`
- `Level`

must continue to work.

This includes the previously supported:

- titles
- buttons
- fields
- OCR values
- left-display boxes
- icons
- speed indicator
- unknown-screen handling

V2 changes must not unnecessarily regress these screens.

---

# 5. Train Data

The `Train Data` workflow uses both displays.

## 5.1 Left Display

Expected elements:

- title: `Train data`
- selected train type summary
- bottom grey `Yes` button

The pipeline should detect and annotate:

- title
- `Yes` button
- button center

The other summary text does not currently require detailed extraction unless needed later.

---

## 5.2 Right Display

The top field contains:

```text
Train type | Gamma
```

or:

```text
Train type | Lambda
```

The selected value is dynamic.

The pipeline must:

- detect the field
- read the selected value using OCR
- store the value in structured output

Expected values currently include:

- `Gamma`
- `Lambda`

Middle buttons:

- `Gamma`
- `Lambda`

Bottom buttons:

- `close` — X button
- `enter_data` — Enter Data button

All required buttons should be detected and annotated with their center points.

---

## 5.3 Train Data Transitions

From this screen:

```text
Yes
 ↓
Validate Train Data
```

and:

```text
Enter Data
    ↓
Train Data (1/2)
```

The pipeline should recognize the resulting screen change rather than keeping the previous state through temporal smoothing.

---

# 6. Validate Train Data

## 6.1 Left Display

Expected title:

`Validate train data`

The display also shows a summary of the selected train data.

The summary values do not currently require detailed OCR.

---

## 6.2 Right Display

The top grey field contains the currently selected confirmation value.

Typical values:

- `Yes`
- `No`

This value must be read using OCR and written to structured output.

Expected buttons:

- `No`
- `Yes`
- `close` — X button

The `Yes` and `No` buttons modify the value shown in the grey field.

The pipeline must therefore distinguish between:

- the two selectable buttons
- the dynamic value displayed in the field

All buttons should be detected and annotated with their center points.

---

# 7. Train Data (1/2)

## 7.1 Left Display

Expected title:

`Train data (1/2)`

The screen contains several train-data summary values.

These values are **not required for OCR in V2 at this stage**.

The bottom grey `Yes` button should be detected and annotated.

---

## 7.2 Right Display

The upper part contains several train-data fields and values.

These values are not currently required for extraction.

The lower part contains a numeric keypad:

```text
1  2  3
4  5  6
7  8  9
Del 0  .
```

Additional bottom buttons include:

- `close` — X
- `left_arrow`
- `right_arrow`
- `select_type`

The pipeline should detect and annotate these buttons and their center points.

Pressing the right arrow may move to:

```text
Train Data (1/2)
        ↓
Train Data (2/2)
```

---

# 8. Train Data (2/2)

## 8.1 Left Display

Expected title:

`Train data (2/2)`

The left display continues showing the train-data summary.

Detailed OCR of these summary values is not currently required.

The bottom grey `Yes` button should remain detectable.

---

## 8.2 Right Display

The upper section contains additional train-data values.

These values do not currently require extraction.

Visible selection buttons may include:

- `G1`
- `GA`
- `GB`
- `GC`
- `Out of GC`

Bottom controls include:

- `close` — X
- `left_arrow`
- `right_arrow`
- `select_type`

Detect and annotate the visible buttons and their center points.

The page-navigation buttons must remain distinguishable from the train-data selection buttons.

---

# 9. Train Running Number

The `Train Running Number` screen is structurally similar to the existing `Driver ID` screen.

## 9.1 Right Display

Expected title:

`Train running number`

The title must be detected and read using OCR.

A grey input field appears below the title.

Its value is dynamic and must also be read using OCR.

The current V2 development video contains examples such as:

- `1`
- `12`
- `128`

These are examples only and must not be hardcoded as the only possible values.

Expected keypad:

```text
1  2  3
4  5  6
7  8  9
Del 0  .
```

Bottom button:

- `close` — X

The pipeline must detect and annotate:

- title
- input field
- OCR value
- keypad buttons
- close button
- button center points

---

# 10. Left Display Modes

The left display can now appear in different layouts.

### Normal / Existing Layout

For relevant V1 states, continue supporting:

- 22 logical boxes
- icon associations
- speed indicator

### Train Data Workflow

During Train Data states, the left display may instead contain:

- title
- summary text
- grey confirmation button

Do **not** force the 22-box layout onto these screens.

Detection should follow the actual active UI state.

---

# 11. Unknown and New Screens

A screen that is not one of the known states must not stop processing.

For an unknown screen:

- mark the state as unknown
- continue locating both displays
- detect visible bordered UI regions where reliable
- detect title regions when possible
- apply OCR when appropriate
- detect buttons and center points
- annotate successfully detected elements

Do not invent semantic names for elements whose meaning is unknown.

---

# 12. OCR Requirements

OCR is required for dynamic values that matter to the structured output.

Current V2 examples include:

- screen titles
- Train Type value: `Gamma` / `Lambda`
- Validate Train Data value: `Yes` / `No`
- Train Running Number input value

Do not hardcode expected OCR values from filenames or known video content.

If a value cannot be read reliably, report an unknown/null result rather than fabricate it.

---

# 13. Button Detection

For required visible buttons, provide:

- detected border/region
- stable logical identity when known
- center point

Button geometry should follow the visible screen borders.

Examples include:

- numeric keypad buttons
- Gamma / Lambda
- Yes / No
- X / close
- Enter Data
- arrows
- Select Type
- G1 / GA / GB / GC / Out of GC

Do not use remembered coordinates when the real display moves.

---

# 14. Temporal Stability

V2 should improve stability across consecutive frames.

Reduce unnecessary:

- display shaking
- box shaking
- button-border shaking
- center-point movement
- OCR flickering
- state flickering
- field-value flickering

Temporal smoothing should improve stable detections without delaying genuine UI changes excessively.

For example:

```text
Train Data
    ↓
Train Data (1/2)
```

must still be recognized promptly when the screen actually changes.

Do not use smoothing to hide incorrect underlying detections.

---

# 15. Annotation Requirements

Annotated output should clearly show the detections represented in the structured result.

Depending on the active state, annotations may include:

- display boundaries
- screen state
- titles
- OCR text
- dynamic fields and values
- buttons
- button center points
- left-display boxes
- icons
- speed indicator

Do not annotate UI elements that are intentionally outside the current V2 extraction scope as though they were verified detections.

Keep annotations readable and consistent.

---

# 16. Core V2 UI Requirements

V2 should:

1. preserve existing `Main`, `Driver ID`, and `Level` behavior
2. recognize the new Train Data workflow states
3. recognize `Train Running Number`
4. detect required titles, fields and buttons
5. OCR required dynamic values
6. provide button center points
7. handle both normal and Train Data left-display layouts
8. continue processing unknown screens
9. reduce unnecessary geometry and OCR instability
10. react correctly to genuine screen transitions

Structured output conventions are defined in:

`docs/OUTPUT_SPEC.md`

Validation and regression rules are defined in:

`docs/EVALUATION.md`
