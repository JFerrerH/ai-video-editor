## ADDED Requirements

### Requirement: Segments by word anchors

A segment SHALL accept `from` and `to` instead of `in` and `out`. Each is a word anchor `{"word", "after"?}`, matched in the segment's own take the way event word anchors are. `in` and `from` SHALL be mutually exclusive, and so SHALL `out` and `to`. The resolved seconds SHALL appear in `check`'s timeline.

#### Scenario: Both forms given

- **WHEN** a segment has both `in` and `from`
- **THEN** `check` reports an error naming the segment and saying to give one of them

#### Scenario: Word not in the take

- **WHEN** `from` names a word that does not occur in the take after `after`
- **THEN** `check` reports an error naming the segment, the word and the take

### Requirement: Word-anchored edges sit between words

For `from`, the edge SHALL be placed in the pause before the word's start; for `to`, in the pause after the word's end. When the word runs into its neighbour with no pause, the edge SHALL be placed at the quietest 5 ms point between the two words, never inside either.

#### Scenario: Out-point after a word

- **WHEN** a segment has `"to": {"word": "today", "after": 40}`, "today" spans 41.20–41.55, and the envelope is quiet from 41.60 to 42.00
- **THEN** `check` exits 0 and the timeline shows the segment's out at or after 41.55 and before 42.00

#### Scenario: Run-on words

- **WHEN** a segment ends `"to": {"word": "plan"}` and "plan" (10.30–10.44) runs straight into the next word (10.44–10.70) with no pause
- **THEN** the resolved out lies within 10.40–10.48, and no error or warning says the edge is inside a word

### Requirement: Restart kept

`check` SHALL report a segment whose source range contains both the abandoned phrase and the restart of a marked restart (see local-transcription "Restarts are marked"). The message SHALL quote the abandoned phrase, give its range and the restart's start, and name the in-point or split that removes it. A segment with `"keep_restart": true` SHALL get a warning instead of an error. In strict mode it SHALL always be an error ("Strict mode").

#### Scenario: False start inside a segment

- **WHEN** a take has a restart marked with abandoned 37.74–40.62 and again at 41.50, and a segment runs 34.40–48.60
- **THEN** `check` exits non-zero with an error naming the segment, quoting the abandoned words, giving `37.74–40.62`, and suggesting the cut that resumes at 41.50

#### Scenario: Only the restart kept

- **WHEN** the segment starts at 41.50 instead
- **THEN** no restart error is reported

### Requirement: Untranscribed speech kept

`check` SHALL warn for each segment that keeps a range listed in its take's `untranscribed`, naming the segment and the range, and saying there is speech there with no words. In strict mode it SHALL be an error.

#### Scenario: Kept hole

- **WHEN** a take's transcript lists `untranscribed: [[52.1, 53.0]]` and a segment runs 50.0–55.0
- **THEN** `check` warns naming the segment and `52.1–53.0`

### Requirement: Silence is measured against the take's speech

Edge placement and the pause search SHALL treat audio as silent when it is below `max(floor + 9 dB, speech − 25 dB)`. Here `floor` is the take's noise floor and `speech` is the 90th percentile of the take's envelope over its transcript words. Quiet runs separated by 50 ms or less SHALL be merged, since room noise flickers. A run SHALL count as a pause only from 60 ms long.

#### Scenario: Breath after a word

- **WHEN** a word ends at 12.40 by its stamp, its core ends at 12.21, the audio is under the threshold from 12.25 to 12.70 except a 30 ms blip at 12.40, and a segment ends `"to"` that word
- **THEN** the out-point lies between 12.25 and 12.70, and the breath at 12.45–12.60 is not played

### Requirement: Edges start from the word's core and clear clicks

When Whisper stamps a word longer than its letters (it stretches stamps over pauses), the pause search SHALL use the word's core: its start plus 0.025 s per letter + 0.02 s. A placed edge SHALL move on through its pause until the 30 ms the loud-edge check reads beside it is quiet, so a click merged into the pause is never at the cut.

#### Scenario: Click beside the cut

- **WHEN** a 20 ms click sits 0.08 s after a word, inside the pause, and a segment ends `"to"` that word
- **THEN** the out-point lies after the click, and no loud-edge finding is reported

### Requirement: Dead air inside a word-anchored segment is removed

A segment given by `from` / `to` SHALL be split at every pause inside it that is 0.30 s or longer, removing the silence and keeping 0.10 s before and 0.12 s after the surrounding words. A split SHALL only happen when it removes at least 0.08 s, so a split never becomes a jump with nothing taken out. The pieces SHALL keep the segment's zoom and look, and the timeline SHALL list them.

#### Scenario: Pause mid-sentence

- **WHEN** a segment runs from "Resulta" to "maestría" and the speaker pauses 0.62 s after "2020"
- **THEN** the timeline shows two pieces, and the output has no silence there longer than 0.25 s

### Requirement: Scene background agrees with its backdrop

A full-frame event whose scene draws on a dark background (`bg: "dark"`) SHALL get a dark backdrop. `check` SHALL report an error when an event's props ask for a dark scene on a light backdrop, or the reverse, naming the event and the prop to change. Light text on the cream backdrop is the case found in the 2026-11-02 prototype.

#### Scenario: Dark scene, light backdrop

- **WHEN** a `StatScene` event has `"bg": "dark"`, `"full": true` and no `"dark": true`
- **THEN** `check` exits non-zero naming the event and saying to set `"dark": true` or drop `"bg": "dark"`

## MODIFIED Requirements

### Requirement: No edge inside a word

`check` SHALL report an error when an edge, locked or unlocked, lies inside a transcript word after edge refinement and on sound (any of the 30 ms around it above the take's silence threshold). An edge in silence inside a word's stamp SHALL NOT be reported: Whisper stretches stamps over the silence before a word, and a cut there clips nothing. The error SHALL name the segment, the edge, the word and its range, and the nearest word boundaries on each side. When both boundaries run into a neighbouring word with no pause, it SHALL also say so and give the nearest pause. A lock SHALL NOT turn this error into a warning. A lock only keeps an edge on sound *between* words.

#### Scenario: In-point inside a word

- **WHEN** segment 7's in-point is 57.50, no silence is found before it, and "empezar" spans 57.28–57.64
- **THEN** `check` exits non-zero with `segments[7].in 57.50 is inside "empezar" (57.28–57.64): use 57.28 or 57.64`

#### Scenario: Locked edge

- **WHEN** the same in-point has `"lock_in": true`
- **THEN** `check` still exits non-zero with the same error

#### Scenario: Locked edge in an early stamp

- **WHEN** a locked in-point lies inside the stamp of a word but in the silence before its sound
- **THEN** no inside-a-word error is reported

#### Scenario: Locked edge between words

- **WHEN** a locked in-point lies between two words where the envelope is 20 dB over the floor (music under speech)
- **THEN** `check` exits 0 and lists a loud-edge warning that says it is locked

### Requirement: Legibility probe

For every event, `stills` SHALL compare the event drawn alone at its still time with the same event with every glyph drawn transparent (layout unchanged, numbers and SVG text included). Glyphs with no letter or digit (an emoji, a caret) are not text. Two findings SHALL be reported:
- when the text adds fewer changed pixels than a fixed minimum, the warning `events[N] (<type>) shows almost no text at <t> s`;
- otherwise, both renders are composited over the source frame the event plays on, at the same output time. Then, over the changed pixels, the WCAG contrast between the text render and the emptied render is measured (median relative luminance of each), so text floating over footage is measured against the footage. Under 4.5:1 for text under 48 px tall, or under 3:1 for larger text, the warning is `events[N] (<type>) text contrast <r>:1 at <t> s is under <min>:1`.

In strict mode both SHALL be errors.

#### Scenario: Text moved out of frame

- **WHEN** a `KineticType` event passes `check` but its `frame` prop moves it below the bottom of the picture (`{"y": 1900}`), and `stills` runs
- **THEN** the result's warnings include `events[N] (KineticType) shows almost no text`

#### Scenario: Readable title

- **WHEN** the same event has no `frame` prop and `lines[0].at: 0.2`
- **THEN** no legibility warning is reported for it

#### Scenario: Pale text on a white card

- **WHEN** a test component draws `#E8FD5A` text on a `#FFFFFF` card and `stills` runs
- **THEN** the warnings include `text contrast` with a ratio under `3:1` for that event

#### Scenario: Bare white number on a bright wall

- **WHEN** a floating stat with no card draws a white number over a source frame whose wall behind it has a luminance above 0.7
- **THEN** the warnings include `text contrast` for that event, measured against the footage, not against a transparent canvas

### Requirement: Loud edges

`check` SHALL measure each edge's energy over the take's noise floor and compare it with the take's silence threshold ("Silence is measured against the take's speech": floor + 9 dB, or speech − 25 dB in a very quiet room). More than 3 dB above the threshold on an unlocked edge SHALL be an error; above the threshold and up to 3 dB over it, a warning. An edge placed in measured silence SHALL never be reported loud. Messages SHALL say in words which edge is loud and by how much. An in-point at the very start of a take's media (source time 0) SHALL count as clean, because nothing precedes it, and SHALL not be reported. In strict mode a warning here SHALL be an error ("Strict mode").

#### Scenario: Loud head

- **WHEN** an unlocked in-point lands where the envelope is 20.9 dB over the floor
- **THEN** `check` exits non-zero with an error naming the segment, `in`, `+20.9 dB` and that the cut starts in the middle of sound, and no message contains `<-- check`

#### Scenario: Take starts mid-word

- **WHEN** a segment's `in` is 0.0 and the take's audio is loud at 0.0
- **THEN** no loud-edge error or warning is reported for that in-point
