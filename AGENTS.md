# AGENT.md — Video Screen Understanding Pipeline

## 1. Project Goal

Build a complete, accurate, efficient, and maintainable video-processing pipeline that analyzes a physical interface recorded by a webcam.

The interface contains two main displays:

- **Right display**
- **Left display**

The system must detect and track the relevant UI elements, extract required text, identify icons, calculate required coordinates, draw accurate visual annotations, and produce structured JSON output.

Development must initially use the prerecorded videos available in the project.

After the recorded-video pipeline becomes sufficiently accurate and stable, the same pipeline should be suitable for **real-time webcam processing**.

The highest priorities are:

1. Detection accuracy
2. Bounding-box alignment accuracy
3. Stable behavior across video frames
4. OCR accuracy
5. Correct association between UI elements
6. Processing speed
7. Simple and maintainable code
8. Clean project organization

---

# 2. Important Development Principle

Do **not** assume or follow a predefined detection, alignment, tracking, or bounding-box algorithm simply because it was used previously.

Study the available:

- videos
- example images
- icon assets
- UI structure
- visual behavior across frames

Then determine an appropriate solution based on the actual data.

The implementation should be driven by **measured results**, not by commitment to a particular technique.

Different parts of the interface may require different solutions.

The goal is not to demonstrate a particular computer-vision technique.

The goal is to produce the **most reliable pipeline possible while keeping the implementation reasonably simple**.

---

# 3. Input Data

Inspect the project before implementing anything.

The repository contains or may contain the following types of input data.

## Videos

The `videos/` directory contains prerecorded webcam videos showing the complete interface.

These videos are the primary development and testing source.

They should be examined carefully before choosing how to implement the pipeline.

Pay particular attention to variations such as:

- small camera movements
- screen movement
- slight rotation
- zoom changes
- camera moving closer or farther away
- perspective changes
- lighting changes
- brightness changes
- reflections
- blur
- temporary instability
- UI content changes

Do not assume that pixel coordinates remain identical throughout a video.

---

## Example Images

The `examples/` directory contains example images showing expected UI elements or expected detections.

Use these images to understand:

- what should be detected
- what should not be detected
- expected bounding-box placement
- expected element identities
- expected relationships between UI elements

These examples are references, not absolute hardcoded screen coordinates.

---

## Icon Assets

An icon dataset is available for the icons that may appear on the left display.

Use these assets to identify which known icon appears inside each corresponding UI box.

Do not invent icon labels.

Use stable labels based on the provided icon dataset, for example:

```text
icon_1
icon_2
icon_3
...
```

or meaningful names if the existing dataset already provides them.

---

# 4. Interface Overview

The interface should conceptually be separated into:

```text
FULL SCREEN
│
├── RIGHT DISPLAY
│   ├── Title field
│   ├── Buttons
│   └── Data field
│
└── LEFT DISPLAY
    ├── 22 UI boxes
    ├── Icons that may appear inside the boxes
    └── Analog speed indicator
```

The pipeline should understand these elements consistently across frames.

---

# 5. Right Display Requirements

The right display is a stateful UI that can switch between completely different screens such as Main, Driver ID, Level, and potentially other screens. Each screen can have its own title, buttons, fields, and layout, and the pipeline must recognize which screen is currently active.

## 5.1 Title Field

The right display contains a title field.

The title:

- must be localized correctly
- must be read using OCR
- must be stored in the JSON output

Example:

```json
"title": "Driver ID"
```

The title may change depending on the current interface state.

Do not hardcode the title value.

---

## 5.2 Buttons

Different buttons may appear on the right display.

For every visible button that is relevant to the interface:

- detect/localize it
- assign a stable label where possible
- calculate its center coordinates
- store the center coordinates in the JSON output

The important output for buttons is their **center point**, rather than only their outer rectangle.

Example:

```json
"buttons": {
  "button_1": {
    "center": [1240, 520]
  },
  "button_2": {
    "center": [1315, 520]
  }
}
```

Labels should remain consistent across frames whenever the same logical button is present.

---

## 5.3 Data Field

Some right-display screens contain a data field.

Examples include values such as:

- Driver ID numbers
- Level values
- other values displayed in the same UI region

When the data field exists:

1. locate it correctly
2. read its contents using OCR
3. clean the OCR result only when appropriate
4. store the final value in JSON

Example:

```json
"data_field": {
  "value": "1042"
}
```

or:

```json
"data_field": {
  "value": "LEVEL 3"
}
```

If the field is not present, the JSON should clearly represent that state rather than inventing a value.

For example:

```json
"data_field": null
```

---

# 6. Left Display Requirements

The left display is largely structurally consistent, although its visual contents may change depending on selections made on the right display.

It contains:

- **22 distinct boxes**
- **1 analog speed indicator**
- optional icons appearing inside the boxes

---

# 7. Left Display Box Detection

All 22 boxes must be identified.

Use stable logical labels:

```text
box_1
box_2
box_3
...
box_22
```

The mapping between physical boxes and their labels must remain consistent across frames.

For every box calculate at minimum:

- bounding box
- center point

The JSON output must contain the center coordinates.

Example:

```json
"box_2": {
  "center": [540, 310]
}
```

The box localization must remain accurate even when the webcam moves slightly or the screen becomes slightly larger or smaller in the video.

Do not rely on the assumption that a box always occupies exactly the same image pixels.

---

# 8. Icon Detection Inside Left-Side Boxes

Icons may appear inside one or more of the 22 boxes.

For every box:

1. determine whether an icon is present
2. determine which known icon it is
3. associate the icon with the correct box

The most important result is the relationship:

```text
box -> icon
```

For example:

```json
"box_2": {
  "center": [540, 310],
  "icon": "icon_3"
}
```

This means:

> `icon_3` is currently visible inside `box_2`.

If a box contains no icon:

```json
"box_2": {
  "center": [540, 310],
  "icon": null
}
```

Never assign an icon merely because the system is uncertain.

False icon assignments should be avoided.

---

# 9. Analog Speed Indicator

The left display also contains one analog speed indicator.

It must at minimum be correctly localized and tracked with the rest of the interface.

Store its position in the structured output.

For example:

```json
"speed_indicator": {
  "center": [420, 710]
}
```

Keep its handling modular so that additional interpretation of the analog indicator can be added later without redesigning the rest of the pipeline.

---

# 10. Camera Movement and Geometry

The videos come from a webcam.

Most recordings will have relatively similar:

- camera distance
- viewpoint
- screen position
- lighting

However, the pipeline must **not depend on the camera being perfectly fixed**.

It must tolerate reasonable changes such as:

- camera moving slightly left/right
- camera moving slightly up/down
- screen shifting inside the frame
- camera moving closer to the screen
- camera moving farther from the screen
- moderate zoom changes
- small orientation changes
- small perspective changes

If the interface becomes larger, smaller, or moves in the video, the detected UI geometry must follow it.

Bounding boxes must remain attached to the actual UI elements.

A previous coordinate should never be considered correct simply because it matched an earlier frame.

---

# 11. Temporal Stability

Video is not a collection of unrelated images.

Use information from neighboring frames when useful to obtain stable results.

The pipeline should avoid:

- bounding boxes jumping unnecessarily
- center points oscillating strongly
- OCR changing randomly between frames
- icons appearing/disappearing because of a single bad frame
- UI identities changing between neighboring frames

At the same time, stabilization must not prevent the system from reacting to real changes.

For example:

- a newly appearing icon should eventually be detected
- a disappearing icon should disappear from the result
- a changing title should update
- a changed data value should update
- screen movement should cause the geometry to move accordingly

Aim for a balance between **stability and responsiveness**.

---

# 12. Bounding-Box Quality

Bounding-box alignment is extremely important.

A detection should not be considered successful merely because the target element is somewhere inside a large rectangle.

Bounding boxes should closely represent the actual intended UI region.

Check for:

- left border alignment
- right border alignment
- top border alignment
- bottom border alignment
- center-point accuracy

Avoid boxes that:

- include large unnecessary surrounding regions
- overlap neighboring UI elements incorrectly
- drift across frames
- remain fixed while the screen moves
- become incorrectly resized because of temporary brightness or reflections

---

# 13. Visual Debug Output

During development, create an annotated version of processed frames or videos.

The visualization should clearly show relevant detected elements, such as:

- left display
- right display
- title field
- data field
- buttons
- left-side boxes
- icon assignments
- speed indicator
- center points where useful

The visualization exists to make verification easy.

Keep it clean.

Do not cover the interface with unnecessary debug text.

---

# 14. JSON Output

Create structured JSON output corresponding to processed video frames.

The format should remain stable throughout the project.

A recommended high-level structure is:

```json
{
  "video": "example_video.mp4",
  "frames": [
    {
      "frame_index": 0,
      "timestamp": 0.0,

      "right_display": {
        "title": "Driver ID",

        "buttons": {
          "button_1": {
            "center": [1240, 520]
          }
        },

        "data_field": {
          "value": "1042"
        }
      },

      "left_display": {
        "boxes": {
          "box_1": {
            "center": [510, 280],
            "icon": null
          },

          "box_2": {
            "center": [570, 280],
            "icon": "icon_3"
          }
        },

        "speed_indicator": {
          "center": [430, 720]
        }
      }
    }
  ]
}
```

This is a conceptual schema.

Small improvements to the structure are allowed when they clearly improve maintainability.

However, keep the output:

- simple
- consistent
- human-readable
- easy for another program to consume

Do not unnecessarily duplicate information.

---

# 15. Coordinate System

Use one clearly documented coordinate convention.

Unless there is a strong reason otherwise, coordinates should correspond to the **original video frame**.

This is important.

Internal processing may resize, crop, transform, or otherwise manipulate an image, but reported final coordinates must map correctly back to the selected output coordinate system.

For center coordinates:

```text
[x, y]
```

where:

```text
x = horizontal coordinate
y = vertical coordinate
```

Verify coordinate mapping visually before considering a stage complete.

---

# 16. Development Workflow

Work incrementally.

Do **not** attempt to build the entire pipeline in one large implementation.

A suitable development progression is:

## Phase 1 — Understand the Data

Before writing the main pipeline:

- inspect all videos
- inspect representative frames
- inspect examples
- inspect icons
- understand UI states
- understand common variations
- identify difficult cases

Document conclusions only in the final report unless a development note is absolutely necessary.

---

## Phase 2 — Basic Video Pipeline

Create the smallest reliable pipeline capable of:

- loading a video
- iterating through frames
- preserving frame metadata
- generating output
- generating an annotated preview

Test this before continuing.

---

## Phase 3 — Main Screen Geometry

Establish reliable understanding of the two-display layout.

Verify that the system continues to work when:

- screen position changes
- scale changes slightly
- camera position changes slightly

Do not continue if the base geometry is unstable.

---

## Phase 4 — Right Display

Implement and validate:

- title localization
- title OCR
- button localization
- button center coordinates
- data-field localization
- data-field OCR

Test different right-side UI states.

---

## Phase 5 — Left Display Structure

Implement and validate:

- all 22 boxes
- consistent box numbering
- accurate box centers
- speed-indicator localization

Verify that box identities remain consistent when the screen moves.

---

## Phase 6 — Icon Recognition

Add recognition of icons appearing inside the left-side boxes.

Validate:

- correct icon identity
- correct box assignment
- empty boxes
- multiple icons appearing in different boxes
- icon appearance/disappearance

---

## Phase 7 — Temporal Stability

Evaluate consecutive frames.

Improve:

- geometric stability
- OCR stability
- icon stability
- responsiveness to genuine state changes

Avoid introducing excessive delay.

---

## Phase 8 — End-to-End Recorded Video Test

Run the complete pipeline on the available recorded videos.

Check:

- geometry
- OCR
- icons
- JSON
- annotations
- performance
- failure cases

Do not move to real-time preparation while major recorded-video failures remain.

---

## Phase 9 — Real-Time Readiness

After recorded videos work reliably, prepare the pipeline so the frame source can later be changed from:

```text
recorded video
```

to:

```text
live webcam
```

without rewriting the core detection pipeline.

Measure processing performance.

Avoid expensive operations that provide little accuracy improvement.

---

# 17. Test-Gated Development

Every major phase must have a small validation test.

Tests should be **lightweight and meaningful**.

Do not create a huge testing framework.

Examples of useful checks include:

- expected number of boxes found
- stable box labels
- coordinate sanity checks
- OCR expected-value checks on selected reference frames
- known icon recognition checks
- icon-to-box association checks
- geometry checks on representative frames
- processing success over a short video sequence

The purpose of testing is to determine whether the implementation actually works.

---

# 18. Failure Rule

A failed phase must not simply be patched repeatedly until the code becomes complicated.

If a phase performs poorly:

1. identify why it failed
2. determine whether the underlying assumption was incorrect
3. reconsider the design
4. rebuild that phase cleanly when necessary
5. rerun its lightweight tests

Prefer replacing a weak design over accumulating many special-case fixes.

Do not continue building later phases on top of an unreliable foundation.

---

# 19. Regression Rule

Whenever a later change improves one case, verify that it does not damage previously working cases.

A change should be accepted only when it improves the intended behavior without introducing significant regressions elsewhere.

Keep a small representative reference set covering:

- different videos
- different screen states
- different scales
- different lighting conditions
- different icons
- different OCR values

Use this reference set throughout development.

---

# 20. Code Simplicity

Keep the implementation as simple as reasonably possible.

Avoid:

- giant Python files
- dozens of tiny Python files
- unnecessary classes
- unnecessary abstraction layers
- duplicated logic
- dead experimental code
- deeply nested configuration systems
- premature framework development

At the same time, do not put the entire project into one unmaintainable script.

Aim for a **small number of focused modules**.

A module should exist because it represents a clear responsibility, not simply to split code.

---

# 21. Project Structure

Keep the repository neat.

A structure similar to the following is preferred:

```text
project/
│
├── AGENT.md
│
├── README.md                  # only if already present or genuinely required
│
├── videos/
│   └── ...
│
├── examples/
│   └── ...
│
├── icons/
│   └── ...
│
├── src/
│   ├── main.py
│   ├── detector.py
│   ├── ocr.py
│   └── utils.py
│
├── tests/
│   └── test_pipeline.py
│
├── outputs/
│   ├── json/
│   └── videos/
│
└── final_report.md
```

This is an example, not a requirement to create every listed file.

**Create fewer files when fewer files are sufficient.**

Do not create empty folders or placeholder modules simply because they appear in this example.

---

# 22. File Creation Rules

Before creating a new file, ask:

> Does this responsibility genuinely require a separate file?

If not, keep the implementation in an existing appropriate module.

Do not create files such as:

```text
notes1.md
notes2.md
progress.md
phase1_report.md
phase2_report.md
experiment.md
temporary_solution.py
new_detector.py
new_detector_v2.py
new_detector_final.py
new_detector_final2.py
```

Replace obsolete implementations instead of accumulating versions.

Use Git history for history.

Keep the working tree clean.

---

# 23. Configuration

Do not scatter important constants throughout the code.

If configuration is needed, keep it centralized and minimal.

Examples include:

- input paths
- output paths
- processing options
- thresholds
- debug mode
- frame sampling options

Do not expose dozens of tunable parameters unless they are genuinely useful.

The normal pipeline should run with sensible defaults.

---

# 24. Performance

Real-time webcam processing is the final target.

Therefore performance matters from the beginning.

During development measure approximately:

- processing time per frame
- effective FPS
- expensive pipeline stages

Do not sacrifice major accuracy simply to achieve high FPS during early development.

The priority order is:

```text
correctness
    ↓
stability
    ↓
accuracy
    ↓
performance optimization
```

Once correctness is established, optimize bottlenecks without damaging detection quality.

---

# 25. Avoid Unnecessary Processing

Not every operation necessarily needs to run at exactly the same frequency.

Design the system intelligently so that expensive work is only performed when necessary, provided that doing so does not reduce required accuracy or responsiveness.

Keep real-time use in mind while designing the recorded-video pipeline.

---

# 26. Logging

Logging should be useful but not noisy.

Useful examples:

```text
Video opened
Frame processing started
Screen geometry established
OCR result changed
Icon state changed
Output saved
Processing FPS
Detection failure
```

Avoid printing hundreds of low-value debug messages for every frame.

Detailed diagnostics may be enabled through a debug option when necessary.

---

# 27. Error Handling

The pipeline must fail gracefully.

Handle cases such as:

- unreadable video
- missing frame
- temporarily unclear UI
- OCR failure
- missing icon
- partially visible screen
- failed geometry estimation

Do not silently produce confident incorrect values.

When reliable information is unavailable, prefer an explicit unknown/null result.

For example:

```json
"title": null
```

instead of guessing.

---

# 28. Confidence and Uncertainty

Where useful, internally maintain information about detection certainty.

The final JSON does not need to become unnecessarily complicated, but ambiguous results should not automatically become confident labels.

When the system cannot determine an element reliably:

- preserve the last result only when logically justified
- otherwise output an unknown state

Never fabricate values to make the JSON look complete.

---

# 29. Ground Truth and Reference Frames

Select a small number of representative reference frames from the videos.

The reference set should cover different situations such as:

- different right-side titles
- different data values
- different buttons
- empty left-side boxes
- left-side boxes containing icons
- different icons
- screen movement
- different screen scales
- lighting differences

Use these frames repeatedly to evaluate improvements and regressions.

Do not manually tune the system only for one frame.

---

# 30. Accuracy Before Cosmetic Appearance

Annotated videos are useful for validation, but visual appearance alone does not prove the pipeline is correct.

Always verify underlying data:

- coordinates
- element labels
- OCR values
- icon identities
- box associations

A visually attractive overlay with incorrect JSON is still a failed result.

---

# 31. No Hardcoded Test Answers

Do not make tests pass by hardcoding expected:

- coordinates
- titles
- data values
- icon identities

based solely on the test videos.

The implementation should genuinely infer the interface state from the input.

Known reference values may be used for validation, but not as shortcuts inside the production pipeline.

---

# 32. Maintain Separation Between Input and Output

Never modify original:

- videos
- examples
- icon assets

All generated files must go into clearly separated output directories.

For example:

```text
outputs/json/
outputs/videos/
```

Temporary files should be deleted when no longer needed.

---

# 33. Expected End-to-End Behavior

Given a video frame, the pipeline should conceptually perform:

```text
Input Frame
     │
     ▼
Understand Screen Geometry
     │
     ├───────────────┐
     ▼               ▼
Right Display     Left Display
     │               │
     │               ├── 22 Boxes
     │               │      │
     │               │      └── Icon State
     │               │
     │               └── Speed Indicator
     │
     ├── Title
     │     └── OCR
     │
     ├── Buttons
     │     └── Center Coordinates
     │
     └── Data Field
           └── OCR
     │
     ▼
Temporal Stabilization
     │
     ├── JSON Result
     │
     └── Annotated Frame
```

This diagram describes responsibilities only.

It does not prescribe how the individual problems must be solved.

---

# 34. Acceptance Criteria

The project should not be considered complete merely because the code runs.

A successful pipeline should demonstrate the following.

### Screen Geometry

- right and left displays are correctly understood
- geometry follows reasonable camera movement
- geometry follows reasonable scale changes
- bounding boxes remain aligned

### Right Display

- title region is correctly localized
- title OCR is reliable
- visible buttons are detected
- button center coordinates are accurate
- data fields are correctly localized
- data values are correctly extracted

### Left Display

- all 22 boxes are identified
- box numbering is consistent
- center coordinates are accurate
- icons are correctly identified
- icons are assigned to the correct boxes
- empty boxes remain empty
- analog speed indicator is localized

### Video Stability

- boxes do not unnecessarily jump
- OCR does not unnecessarily oscillate
- icons do not flicker excessively
- genuine changes are detected promptly

### Output

- JSON structure is valid
- coordinate convention is consistent
- annotated output matches JSON
- no fabricated values are produced

### Software Quality

- project structure is clean
- number of source files remains small
- code is understandable
- duplicated/dead code is removed
- lightweight tests pass
- processing performance is measured

---

# 35. Final Report

Create exactly one main development report:

```text
final_report.md
```

Do not create separate reports for every phase.

The final report should explain:

## Project Overview

What the pipeline does.

## Dataset/Input Analysis

What was observed in the videos, examples, and icon assets.

## Architecture

How the final pipeline is organized.

Explain responsibilities rather than simply listing filenames.

## Development Steps

For every major phase explain:

- what problem was solved
- what was implemented
- why the final approach was selected
- what was tested
- what failed during development
- what was changed after failures

Keep this concise but informative.

## Detection Results

Describe the final quality of:

- screen geometry
- right-side UI
- left-side boxes
- icons
- OCR
- coordinate accuracy

## Stability

Explain behavior when:

- camera moves
- scale changes
- lighting changes
- UI content changes

## Performance

Report measured processing performance such as:

```text
average processing time/frame
approximate FPS
main remaining bottleneck
```

## Testing

List the lightweight tests performed and their outcomes.

## Known Limitations

Be explicit about any remaining weak cases.

Do not hide failures.

## Real-Time Webcam Readiness

Explain whether the current pipeline is ready for live webcam input and what, if anything, still needs improvement.

---

# 36. Working Style

Follow this loop throughout the project:

```text
Inspect
   ↓
Understand
   ↓
Implement Small Step
   ↓
Test
   ↓
Evaluate Visually + Numerically
   ↓
PASS? ── Yes ──> Continue
   │
   No
   ↓
Understand Failure
   ↓
Redesign / Rebuild
   ↓
Test Again
```

Do not rush through phases simply to finish the pipeline.

A later stage built on inaccurate geometry is not useful.

---

# 37. Core Rules

Throughout the project remember:

1. **Accuracy is the highest priority.**
2. **Bounding boxes must follow the real screen geometry.**
3. **Do not assume the webcam is perfectly stationary.**
4. **Do not hardcode results from particular videos.**
5. **Do not prescribe a detection method before understanding the data.**
6. **Choose solutions based on measured performance.**
7. **Keep box identities consistent across frames.**
8. **Keep JSON coordinates consistent with the original frame coordinate system.**
9. **Prefer null/unknown over fabricated detections.**
10. **Test every major stage before continuing.**
11. **Rebuild a fundamentally weak stage rather than endlessly patching it.**
12. **Check regressions after every significant change.**
13. **Keep code simple.**
14. **Keep the number of Python files small.**
15. **Keep the repository clean.**
16. **Do not accumulate experimental versions of files.**
17. **Use recorded videos first.**
18. **Design with eventual real-time webcam use in mind.**
19. **Optimize performance only after establishing reliable behavior.**
20. **Create only one final development report: `final_report.md`.**

---

# 38. Final Objective

The final system should take webcam-style video and reliably transform it into structured information describing the state of the physical interface:

```text
Video
  ↓
Accurate Screen Understanding
  ↓
Right UI + Left UI
  ↓
OCR + Buttons + Boxes + Icons + Coordinates
  ↓
Stable Structured JSON
```

The implementation should remain **accurate, fast, compact, understandable, and easy to extend**.

When choosing between a complicated solution that provides negligible improvement and a simpler solution with equivalent reliability, prefer the simpler solution.

When a more sophisticated solution provides a meaningful and measurable improvement in detection or alignment accuracy, prioritize accuracy.
