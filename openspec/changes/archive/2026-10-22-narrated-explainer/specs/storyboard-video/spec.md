# Spec Delta

## MODIFIED Requirements

### Requirement: Scene primitives

The system SHALL provide the scene types `TitleCard`, `KineticType`, `StatScene`, `BarChart`,
`ListScene`, `ImageScene` and `BeatScene`. Each SHALL lay out inside the aspect's safe box, take colours from its
background tone (`light`, `dark`, `accent`, `none`), and take fonts from the brand. The 9:16 overlay
components SHALL be accepted as scene types only when the aspect is 9:16.

#### Scenario: Overlay component outside 9:16

- **WHEN** a 16:9 storyboard uses `RingStat` as a scene type
- **THEN** `check` reports an ERROR telling the user to use a scene primitive

#### Scenario: Unknown scene type

- **WHEN** a scene's `type` is neither a scene primitive nor an overlay component
- **THEN** `check` reports an ERROR listing the scene primitives

#### Scenario: BeatScene in every aspect

- **WHEN** a storyboard with a `BeatScene` (headline, figure, one widget) is checked at 9:16, 16:9, 1:1 and 4:5
- **THEN** `check` reports no ERROR for the scene in any of them

## ADDED Requirements

### Requirement: Narration voice

When a storyboard has a `voice` block (`lang`, `preset`, optional `speed`), every scene with
`narration` and no `narration_audio` SHALL get a synthesised clip under `edit/audio/narration/`,
made by a `voice` command. A scene's `narration_audio` (a recorded clip) SHALL be used as is. Without
a `voice` block, `narration` SHALL stay a planning field, as today.

#### Scenario: Clips per scene

- **WHEN** `voice` runs on a storyboard with a `voice` block and 6 narrated scenes
- **THEN** 6 WAV clips with sidecars exist under `edit/audio/narration/`, and a second run reports all 6 as cached

#### Scenario: No voice block

- **WHEN** a storyboard without a `voice` block has `narration` text
- **THEN** `check`, `stills` and `render` behave as before and no narration clip is made

### Requirement: Narration-driven duration

A narrated scene whose `duration` is omitted or `"auto"` SHALL last its transition-in time plus its
clip's duration plus a tail (`tail`, default 0.3 s). Its clip SHALL start when the scene's
transition-in ends. A fixed `duration` shorter than that SHALL be a `check` ERROR.

#### Scenario: Auto duration

- **WHEN** a scene with a hard cut has a 2.10 s clip and no `duration`
- **THEN** `check` prints a duration of 2.40 s for it

#### Scenario: Fixed duration too short

- **WHEN** a scene fixes `duration: 1.5` and its clip is 2.1 s
- **THEN** `check` reports an ERROR naming the scene and the 2.4 s it needs

### Requirement: Narration track

`render` SHALL place every narration clip at its scene's voice start on one track and use it as the
voice in the existing mix (ducking, SFX, loudness). A storyboard with both narration clips and
`audio.voice` SHALL be a `check` ERROR.

#### Scenario: Clips on time

- **WHEN** a narrated storyboard is rendered
- **THEN** the onset of each clip in `edit/audio/narration_track.wav` (first sample above -40 dBFS) is within 1 frame of its scene's voice start printed by `check`

#### Scenario: Two voice sources

- **WHEN** a storyboard sets `audio.voice` and also has a `voice` block with narrated scenes
- **THEN** `check` reports an ERROR asking for one voice source

### Requirement: Word timing

For every narration clip the engine SHALL produce word times (seconds from the scene start) whose
words are exactly the script's words in order, with `*` and `|` marks stripped but punctuation kept.
The times SHALL come from local speech recognition aligned to the script. They SHALL be cached per
clip, and `check` SHALL print the number of words aligned per scene.

#### Scenario: Script words preserved

- **WHEN** a clip for "Ship it in *one day.*" is timed
- **THEN** its word list is `Ship`, `it`, `in`, `one`, `day.` (emphasis flagged on the last two), with strictly increasing times inside the clip's span

#### Scenario: Recogniser misses a word

- **WHEN** speech recognition drops or misspells one word of a line
- **THEN** that word still appears in the list, with a time between its neighbours' times

### Requirement: Word cues

Any time value in a scene's props, pose list or `sfx` SHALL accept `"@word"` (first occurrence of
that word in the scene's narration, case- and punctuation-insensitive), `"@word#n"` (its n-th
occurrence) or `"@word+0.2"` (plus an offset in seconds). The engine SHALL resolve cues to seconds
before rendering. A cue that matches no word SHALL be a `check` ERROR naming the scene and the
cue.

#### Scenario: Widget on a cue

- **WHEN** a widget has `"at": "@users"` and "users" is spoken 1.12 s after its scene starts
- **THEN** the props written for the render have `at: 1.12`

#### Scenario: Missing cue word

- **WHEN** a scene uses `"@revenue"` and its narration does not contain that word
- **THEN** `check` reports an ERROR naming the scene and `@revenue`

### Requirement: Voice checks

`check` SHALL report an ERROR when the `voice` block's language isn't supported or its preset doesn't
belong to that language, and when a narrated scene's clip is missing or stale (its sidecar no longer
matches the text or voice). Each such ERROR SHALL say to run `voice`.

#### Scenario: Edited line

- **WHEN** a narration line is edited after `voice` ran
- **THEN** `check` reports an ERROR for that scene saying to run `voice`, and `stills`/`render` refuse to run
