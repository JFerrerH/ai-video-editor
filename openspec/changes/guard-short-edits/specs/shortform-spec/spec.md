# Spec Delta

## ADDED Requirements

### Requirement: No repeated source audio

`check` SHALL report an error when two segments of the same take cover overlapping source time, before or after edge refinement. The error SHALL name both segments with their ranges, the overlap in seconds and the transcript words inside the overlap. A segment with `"repeat": true` SHALL be exempt from this rule.

#### Scenario: Overlap inside the original ranges

- **WHEN** segment 3 is `take1` 26.62–33.92 and segment 4 is `take1` 33.16–39.07, and the transcript has "Entonces te voy a" between 33.16 and 33.92
- **THEN** `check` exits non-zero with an error naming `segments[4]` and `segments[3]`, `0.76 s` and `"Entonces te voy a"`

#### Scenario: Deliberate repeat

- **WHEN** the same two segments are given and segment 4 has `"repeat": true`
- **THEN** `check` reports no overlap error for them

#### Scenario: Different takes

- **WHEN** two segments overlap in source time but come from different takes
- **THEN** no overlap error is reported

### Requirement: Edge refinement keeps contiguous cuts apart

When two segments of the same take touch or nearly touch in source time (the earlier one's out within 0.6 s of the later one's in), edge refinement SHALL NOT move either edge past the other. Each edge SHALL be refined on its own; when that would carry the out past the in, both SHALL be placed at the quietest point between the two original edges and the pair reported as joined (when one of the two is locked, the other SHALL stop at it). A pause trimmed between them SHALL stay trimmed.

#### Scenario: Touching segments

- **WHEN** segment 1 is `take1` 10.00–20.00 and segment 2 is `take1` 20.10–30.00, with speech running to 20.05
- **THEN** after `check`, segment 1's refined out is ≤ segment 2's refined in, and no overlap error is reported

#### Scenario: Trimmed pause kept

- **WHEN** segment 1 is `take1` 0.45–1.05 and segment 2 is `take1` 1.45–3.05, with silence from 1.00 to 1.50
- **THEN** the edges are refined as if the segments were apart (none reported as joined) and the silence between the refined edges is not played

### Requirement: No edge inside a word

`check` SHALL report an error when an unlocked edge that edge refinement could not move to silence lies inside a transcript word. The error SHALL name the segment, the edge, the word and its range, and the nearest word boundaries on each side. A locked edge inside a word SHALL be a warning.

#### Scenario: In-point inside a word

- **WHEN** segment 7's in-point is 57.50, no silence is found before it, and "empezar" spans 57.28–57.64
- **THEN** `check` exits non-zero with `segments[7].in 57.50 is inside "empezar" (57.28–57.64): use 57.28 or 57.64`

#### Scenario: Locked edge

- **WHEN** the same in-point has `"lock_in": true`
- **THEN** `check` exits 0 and lists the same message as a warning

### Requirement: Loud edges

`check` SHALL measure each edge's energy over the take's noise floor. Above 12 dB on an unlocked edge it SHALL be an error; above the warning threshold (9 dB) and up to 12 dB, or on a locked edge, a warning. Messages SHALL say in words which edge is loud and by how much.

#### Scenario: Loud head

- **WHEN** an unlocked in-point lands where the envelope is 20.9 dB over the floor
- **THEN** `check` exits non-zero with an error naming the segment, `in`, `+20.9 dB` and that the cut starts in the middle of sound, and no message contains `<-- check`

### Requirement: Event props are validated

`check` SHALL validate every event's props against its component's schema and the shared event props. Unknown keys, missing required keys, wrong types, values outside an enum or range, and numbers given as strings SHALL be errors naming the event index, its type, the field path and the expected type.

#### Scenario: Number as a string

- **WHEN** a `StatScene` event has `"value": "400.000"`
- **THEN** `check` exits non-zero with an error naming `events[N].props.value`, that it must be a number, and that it got the string `"400.000"`

#### Scenario: Unknown prop

- **WHEN** a `KineticType` event has a prop `"colour"`
- **THEN** `check` exits non-zero naming `events[N].props.colour` as an unknown field

### Requirement: Prop times resolve inside the event

`check` SHALL resolve every time prop (number or anchor) to seconds from its event's start before writing overlay props. A resolved time outside `[0, duration)` SHALL be an error stating the value, the event's start and duration, and, when the value falls inside the event as an output time, the event-relative value it probably meant. Strings in time fields SHALL be errors.

#### Scenario: Output time given as event time

- **WHEN** an event starts at 17.5 s, lasts 3.0 s, and has `lines[0].at: 18.2`
- **THEN** `check` exits non-zero with an error naming `events[N].props.lines[0].at`, `18.2 s`, `3.0 s` and the hint `0.7`

#### Scenario: Word anchor in a prop

- **WHEN** a `ListScene` event starts at output 20.0 s and `items[1].at` is `{"word": "plata", "take": "take1"}` spoken at output 21.3 s
- **THEN** `check` exits 0 and the written overlay props hold `items[1].at` = 1.3

#### Scenario: Unit in a string

- **WHEN** `lines[0].at` is `"0.5s"`
- **THEN** `check` exits non-zero naming the field and that it must be seconds or an anchor

### Requirement: Entrances finish inside the event

`check` SHALL compute when each reveal cue's entrance finishes (from the schema, explicit or default cues) and SHALL report an error when one finishes at or after the event's end, naming the event, the cue and both times.

#### Scenario: Late last item

- **WHEN** a 2.0 s `ListScene` event has 4 items with default cues, the last starting at 2.3 s
- **THEN** `check` exits non-zero naming `events[N]`, `items[3]` and that it appears after the event ends

### Requirement: Render failures name the event

When Remotion fails during `stills` or `render`, the error SHALL name the event index and type being drawn, the output time, and the first Remotion error line, instead of the command line. When several events are on screen at that time, the engine SHALL find which one fails on its own.

#### Scenario: Failing component in stills

- **WHEN** an event's props make its component throw at output 1.55 s (for example a NaN cue injected past validation in a test)
- **THEN** the `stills` error contains `events[N]`, the component's type, `1.55` and the Remotion error message, and does not start with `FAILED: npx remotion`

### Requirement: Caption phrase breaks at sentence joins

Caption phrases SHALL also break after a word ending in `;`, `:` or `…`, and before a word that starts with a capital letter when the previous word is lowercase and unpunctuated, unless the take's transcript never has that word in lowercase (a name), or it is the English pronoun "I".

#### Scenario: Whisper segment join

- **WHEN** the cut's words are "nuestro dinero Entonces te voy a" and the transcript has "entonces" in lowercase elsewhere
- **THEN** "dinero" ends one caption phrase and "Entonces" starts the next

#### Scenario: Proper noun kept

- **WHEN** the transcript has "Lisboa" only capitalised and the cut contains "vivo en Lisboa desde"
- **THEN** "en Lisboa desde" stays in one phrase (subject to the length limits)

### Requirement: Captions don't cover scene text

For each full-layout event, the engine SHALL measure the lowest row its content reaches once its entrance has finished. When that row reaches the caption band, captions during that event SHALL move below the content if they fit above the bottom safe zone, else above it if they fit below the top safe zone; when neither fits, `stills` SHALL report a warning naming the event and both positions.

#### Scenario: Stat label in the caption band

- **WHEN** a `StatScene` label reaches 1270 px and captions sit at 1250 px
- **THEN** in the event's still, no caption pixel overlaps the label's measured box, and the still for an output time outside the event shows captions at 1250 px

### Requirement: Legibility probe

For every event whose schema marks viewer text, `stills` SHALL compare the event drawn alone at its still time with the same event with its text props emptied. When the text adds fewer changed pixels than a fixed minimum, it SHALL warn `events[N] (<type>) shows almost no text at <t> s`.

#### Scenario: Text moved out of frame

- **WHEN** a `KineticType` event passes `check` but its `frame` prop moves it below the bottom of the picture (`{"y": 1900}`), and `stills` runs
- **THEN** the result's warnings include `events[N] (KineticType) shows almost no text`

#### Scenario: Readable title

- **WHEN** the same event has no `frame` prop and `lines[0].at: 0.2`
- **THEN** no legibility warning is reported for it

## MODIFIED Requirements

### Requirement: Stills of the finished short

Short-form `stills` SHALL write PNG frames of the composited short (cut, overlays and captions) at given output times into `edit/stills/`, or at each segment's midpoint when no times are given. In both cases it SHALL also write one still per overlay event once its entrance has finished: at `start + min(1.2 s, 0.6 × duration)`, or later when the event's reveal cues finish later (one frame after the last, inside the event), named with the event index, type and time (`ev02_KineticType_018.70.png`). It SHALL do this without rendering the full video.

#### Scenario: Default stills

- **WHEN** `stills` runs on a spec with 6 segments, no events and no times
- **THEN** 6 PNGs appear in `edit/stills/`, each 540x960 or larger, and no `final.mp4` is written

#### Scenario: Event stills with chosen times

- **WHEN** `stills` runs with times 23 and 24.5 on a spec whose events[2] is a `KineticType` from 17.5 s lasting 3.0 s
- **THEN** `edit/stills/` holds the two requested stills and `ev02_KineticType_018.70.png`

#### Scenario: Event still after a late cue

- **WHEN** a 3.0 s `ListScene` event starts at 20.0 s and its last item enters at 2.3 s
- **THEN** its still is taken after that item has finished entering (at 22.77 s or later), not at 21.2 s
