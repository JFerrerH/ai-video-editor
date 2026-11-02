# live-stage Specification

## Purpose
Short-form frames are composed in one Remotion composition (the stage) from the cut footage, so graphics can move the camera, sit behind the speaker, and recur as story objects, instead of floating above a fixed picture.

## Requirements

### Requirement: The frame is composed on the stage

A shortform render SHALL compose each output frame in one Remotion composition, from the cut base video, the speaker cut-out, the events and the captions. The audio SHALL be the shortform mix. The output SHALL be at −14 ±1 LUFS, as today.

#### Scenario: Plain spec

- **WHEN** a spec has no `camera` and no `layer` on any event
- **THEN** the render shows the base full-frame with every event drawn over it, as before this change, and no `overlay.mov` is written

### Requirement: Camera moves

A spec MAY have `camera`: a list of `{kind, start, end, amount?}`, with `kind` one of `push`, `pull`, `side` or `corner`. `start` and `end` are output seconds or word anchors. Moves SHALL NOT overlap, and `push` `amount` SHALL be at most 0.08. The footage and the speaker cut-out SHALL get the same transform at every frame. `split` and any other kind SHALL be rejected, naming the allowed kinds.

#### Scenario: Overlapping moves

- **WHEN** a `side` move runs 11.3–17.9 and a `push` starts at 17.0
- **THEN** `check` exits non-zero naming both moves and their overlap

#### Scenario: Split asked for

- **WHEN** a move has `"kind": "split"`
- **THEN** `check` exits non-zero saying split screen is not available and listing `push`, `pull`, `side` and `corner`

### Requirement: Event layers

Every event MAY have `layer`: `front` (default), `behind` or `panel`. A `behind` event SHALL be drawn under the speaker's cut-out, so the speaker covers it. A `panel` event SHALL be drawn under the footage, and SHALL only be allowed while a `corner` move is on.

#### Scenario: Word behind the head

- **WHEN** a `BehindWord` event with `layer: "behind"` overlaps the speaker's head box
- **THEN** in its still, the pixels inside the person matte show the speaker, not the word

#### Scenario: Panel without corner

- **WHEN** a `PhonePanel` event has `layer: "panel"` and no `corner` move covers its time
- **THEN** `check` exits non-zero naming the event and saying a panel needs a `corner` move

### Requirement: Recurring objects

Events of the same component MAY share `object: "<id>"`. `check` SHALL report an error when two events with the same id differ in the component's identifying props, and SHALL list each object's appearances in the timeline.

#### Scenario: Thesis card comes back

- **WHEN** three `DocCard` events share `object: "thesis"` with the same `kicker`, `title` and `italic` and different `fillTo`
- **THEN** `check` passes and the timeline lists "thesis" at the three start times

### Requirement: Captions follow the camera

While a `corner` move is on, captions SHALL render in ink above the speaker bubble. Caption emphasis SHALL be dropped for a word that a `Stickers` or `BehindWord` event shows on screen at the same time.

#### Scenario: Corner move

- **WHEN** a `corner` move runs 57.65–61.40
- **THEN** every caption word in that span is drawn in ink and its box ends above the bubble's top edge
