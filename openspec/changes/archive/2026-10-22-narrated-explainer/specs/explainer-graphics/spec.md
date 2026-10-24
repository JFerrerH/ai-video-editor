# Spec Delta

## Purpose

The vector vocabulary for narrated explainers: a headline that builds with the voice, a neutral
character with a pose library, cue-driven UI widgets, grid backgrounds and a progress bar, all
aspect-aware and coloured from the brand.

## ADDED Requirements

### Requirement: Voice-synced headline

A `BeatScene` SHALL show its narration as a headline inside the top of the safe box. Each word SHALL
appear at its spoken time and not before. The words of the current phrase SHALL stay in ink until
the phrase ends. A new phrase SHALL start after `.`, `?`, `!` or `|` in the narration, or after 7
words, and SHALL replace the previous one. `|` SHALL NOT be displayed.

#### Scenario: Word appears on time

- **WHEN** the word "zero" is spoken at 1.40 s into a scene and stills are taken at 1.30 s and 1.50 s
- **THEN** the 1.30 s still shows no "zero" in the headline and the 1.50 s still shows it

#### Scenario: Phrase break

- **WHEN** a narration reads "Write the plan. Ship the work."
- **THEN** a still taken after "Ship" is spoken shows "Ship" without "Write the plan."

### Requirement: Emphasis pill

Words wrapped in `*…*` in the narration SHALL be displayed without the asterisks, in the accent
colour's pill with white text, and SHALL pop in (scale overshoot settling within 0.3 s). At most one
emphasis group per phrase SHALL be allowed; `check` SHALL warn on more.

#### Scenario: Marked word

- **WHEN** a narration reads "in *one day.*" and a still is taken 0.4 s after "one" is spoken
- **THEN** the still shows "one day." in white on an accent-coloured pill, and no asterisks

### Requirement: Character rig and poses

The system SHALL provide a neutral vector stick figure whose accent (cap and shoes) takes the brand
accent colour. It SHALL support the poses `stand`, `wave`, `cheer`, `point`, `shrug`, `slump`,
`think`, `type`, `push` and `shout`, and the props `desk`, `megaphone` and `box`. An unknown pose or
prop SHALL be a `check` ERROR listing the valid ones.

#### Scenario: Pose library sheet

- **WHEN** the pose sheet is rendered (one still per pose)
- **THEN** a contact sheet with 10 labelled poses is written, each figure inside its frame with the accent on cap and shoes

#### Scenario: Unknown pose

- **WHEN** a scene asks for pose `dance`
- **THEN** `check` reports an ERROR listing the 10 poses

### Requirement: Pose changes and idle motion

A figure SHALL accept a list of poses with start times (cue words allowed). It SHALL blend between
poses within 0.4 s and SHALL never be perfectly still for more than 1 s: a subtle idle sway or
breathing motion continues while a pose is held.

#### Scenario: Pose change on a cue

- **WHEN** a figure goes from `stand` to `cheer` at `"@done"` and stills are taken 0.1 s before and 0.5 s after that word
- **THEN** the first still shows arms down and the second shows arms raised

#### Scenario: Held pose still moves

- **WHEN** two stills 1 s apart are taken during a held pose
- **THEN** the figure's pixels differ between them (mean absolute difference over the figure's box > 0.5 on 0–255)

### Requirement: Cue-driven widgets

The system SHALL provide the widgets `Terminal`, `Checklist`, `Stamp`, `Counter`, `Gauge`,
`Stopwatch`, `FunnelBars`, `TileGrid` and `Badge`. Each SHALL enter at its `at` time, run its own
actions at their times (typing, ticking, checking, striking, filling) and lay out in the aspect's
safe box. Text in widgets SHALL be at least 28 px at 1080 px short side.

#### Scenario: Counter ticks while spoken

- **WHEN** a `Counter` counts from 0 to 1200 between `"@wrote"` and `"@lines"` and stills are taken before, during and after
- **THEN** the stills read 0, a value strictly between 0 and 1200, and 1200

#### Scenario: Checklist stamped

- **WHEN** a `Checklist` with 4 items is followed by a `Stamp` "SKIP IT" at a cue
- **THEN** a still 0.5 s after the cue shows the 4 items and the stamp over them, rotated, in the accent or alert colour

#### Scenario: Widget in every aspect

- **WHEN** the widget sheet is rendered at 9:16, 16:9, 1:1 and 4:5
- **THEN** every widget sits inside that aspect's safe box in each sheet

### Requirement: Grid backgrounds

`BeatScene` SHALL draw a `light` or `dark` background with a faint square grid and a soft vignette,
taking its colours from the brand palette. Grid lines SHALL stay subtle: within 6% luminance of the
background.

#### Scenario: Dark beat

- **WHEN** a `BeatScene` has `bg: "dark"`
- **THEN** a still shows a dark background with grid lines whose luminance differs from the background by more than 0 and at most 6%

### Requirement: Progress bar

A `ProgressBar` overlay event SHALL draw a thin accent bar along the top edge whose length is the
elapsed fraction of the video.

#### Scenario: Half way

- **WHEN** a still is taken at half the video's duration
- **THEN** the bar spans 50% ±1% of the frame width
