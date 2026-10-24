# Spec Delta

## MODIFIED Requirements

### Requirement: Character rig and poses

The system SHALL provide a neutral vector stick figure whose accent (cap and shoes) takes the brand
accent colour. It SHALL support the poses `stand`, `wave`, `cheer`, `point`, `shrug`, `slump`,
`think`, `type`, `push`, `shout`, `read`, `wait`, `reach`, `scared` and `walk`, and the props
`desk`, `megaphone`, `box`, `book`, `phone` and `bag`. Hand-held props (`book`, `phone`, `bag`)
SHALL be drawn at the figure's hand and follow it as poses blend. `read` SHALL default to the
`book` prop. An unknown pose or prop SHALL be a `check` ERROR listing the valid ones.

#### Scenario: Pose library sheet

- **WHEN** the pose sheet is rendered (one still per pose)
- **THEN** a contact sheet with 15 labelled poses is written, each figure inside its frame with the accent on cap and shoes

#### Scenario: Unknown pose

- **WHEN** a scene asks for pose `dance`
- **THEN** `check` reports an ERROR listing the 15 poses

#### Scenario: Held prop follows the hand

- **WHEN** a figure holds `phone` while blending from `stand` to `reach`, and stills are taken before and after the blend
- **THEN** the phone is drawn in both stills, and its position moves with the front hand

### Requirement: Cue-driven widgets

The system SHALL provide the widgets `Terminal`, `Checklist`, `Stamp`, `Counter`, `Gauge`,
`Stopwatch`, `FunnelBars`, `TileGrid`, `Badge`, `ProductCard`, `Calendar`, `Balance` and
`ThoughtBubble`. Each SHALL enter at its `at` time, run its own actions at their times (typing,
ticking, checking, striking, filling, pressing, flipping, tilting) and lay out in the aspect's safe
box. Text in widgets SHALL be at least 28 px at 1080 px short side.

#### Scenario: Counter ticks while spoken

- **WHEN** a `Counter` counts from 0 to 1200 between `"@wrote"` and `"@lines"` and stills are taken before, during and after
- **THEN** the stills read 0, a value strictly between 0 and 1200, and 1200

#### Scenario: Checklist stamped

- **WHEN** a `Checklist` with 4 items is followed by a `Stamp` "SKIP IT" at a cue
- **THEN** a still 0.5 s after the cue shows the 4 items and the stamp over them, rotated, in the accent or alert colour

#### Scenario: Widget in every aspect

- **WHEN** the widget sheet is rendered at 9:16, 16:9, 1:1 and 4:5
- **THEN** every widget, including the four new ones, sits inside that aspect's safe box in each sheet

#### Scenario: Product card pressed then gone

- **WHEN** a `ProductCard` has `pressAt` at a cue and `out` 1 s later, and stills are taken 0.5 s after the press and 0.3 s after `out`
- **THEN** the first still shows the button in its pressed state and the second shows no card

#### Scenario: Calendar flips

- **WHEN** a `Calendar` has pages "Hoy" then "Mañana" at a cue, and stills are taken 0.2 s before and 0.6 s after the cue
- **THEN** the first still reads "Hoy" and the second reads "Mañana"

#### Scenario: Balance tilts

- **WHEN** a `Balance` with labels "Cabeza" and "Emoción" tilts `right` at a cue
- **THEN** a still 0.8 s after the cue shows the right pan lower than the left

## ADDED Requirements

### Requirement: Figure moves within its slot

A figure SHALL accept `moves: [{x, at, dur}]`, where `x` is a horizontal position from 0 to 1
inside its slot, `at` a start time (cues allowed) and `dur` the travel time (default 0.8 s). While
moving it SHALL play the `walk` cycle and face the direction of travel, then return to the pose
active at that moment. The figure and its prop SHALL stay inside the slot at every `x`. A move
that starts before the previous one ends, or an `x` outside 0–1, SHALL be a `check` ERROR.

#### Scenario: Walks across

- **WHEN** a figure starts at `x: 0.2` and has a move to `x: 0.8` at 1.0 s with `dur` 0.8, and stills are taken at 0.9 s and 2.0 s
- **THEN** the figure's centre in the second still is to the right of the first, and both figures are inside the figure slot

#### Scenario: Overlapping moves rejected

- **WHEN** a figure has moves at 1.0 s (dur 0.8) and 1.5 s
- **THEN** `check` reports an ERROR naming the scene and the overlapping move

### Requirement: Line icons for the explainer

The icon set SHALL include `book`, `cart`, `heart`, `brain` and `moon`, drawn in the same stroke
style as the existing icons, usable by `Badge`, `ProductCard` and `ThoughtBubble`. An unknown icon
in a widget SHALL be a `check` ERROR listing the valid ones.

#### Scenario: New icons on the widget sheet

- **WHEN** the widget sheet is rendered
- **THEN** the `ProductCard` sample shows the `cart` icon and the `ThoughtBubble` sample shows the `brain` icon
