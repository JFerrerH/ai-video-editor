# person-matte Specification

## Purpose

A grey matte video (white = person) for a time window of a clip, used to place text behind the speaker, produced the same way on macOS and on Linux.

## Requirements

### Requirement: Matte video contract

Given a source clip, a start time and a duration, the system SHALL write a grey matte video (the mask carried in luma, neutral chroma; ProRes 422) at the source resolution and the requested frame rate, whose frame 0 corresponds to `start` and whose duration matches the requested duration within one frame.

#### Scenario: Window of a talking-head clip

- **WHEN** a matte is made for a 1080x1920 clip with `--start 8.0 --dur 3.7` at 30 fps
- **THEN** the output is 1080x1920, 30 fps, 111 ± 1 frames

#### Scenario: Person is white, background is dark

- **WHEN** a frame of the matte is compared with the source frame at the same time, for a shot where the speaker is centred
- **THEN** the mean matte value inside the face region (centre of the frame) is ≥ 200 and in the top-left 10% corner is ≤ 50

### Requirement: Backend per platform

The system SHALL use the platform's built-in person segmentation on macOS and an open, commercially licensed segmentation model elsewhere, chosen at runtime; a `--backend` option SHALL force either. A missing backend SHALL exit non-zero with the install command instead of a traceback.

#### Scenario: Linux default

- **WHEN** a matte is requested on Linux without `--backend`
- **THEN** it is produced with the open model and the command exits 0

#### Scenario: Optional dependency missing

- **WHEN** a matte is requested on Linux without the matte dependencies installed
- **THEN** the command exits non-zero and prints `uv sync --group matte`

### Requirement: Behind-the-speaker text on any platform

The short-form engine's behind-the-speaker events SHALL use this matte on both platforms without per-platform settings in the project.

#### Scenario: Same build file on Linux

- **WHEN** a short-form build with one `behind: true` event is rendered on Linux
- **THEN** the render completes and a still taken mid-event shows the text layer present outside the person region (pixel difference against a render without the event is non-zero there)
