# shortform-spec Specification

## Purpose
Describe a vertical short made from talking-head footage entirely as validated data (`edit/short.json`), so it can be checked and rendered without running project code, with the same result as the equivalent `build.py`.

## Requirements

### Requirement: Spec file format

A short-form project SHALL be describable by one JSON file, `edit/short.json`, holding the brand, sources with face centres, segments, caption settings, emphasis phrases, overlay events, SFX and public files. Every field `templates/shortform_build.py` exposes SHALL have a JSON form. Unknown fields SHALL be errors.

#### Scenario: Template spec checks clean

- **WHEN** `edit/short.json` is the unmodified starter written by `tools/new_project.py --shortform`, with its one source present and transcribed
- **THEN** `check` exits 0 and reports one segment and the planned duration

#### Scenario: Unknown field

- **WHEN** a segment in `edit/short.json` contains a field `"filter": "..."`
- **THEN** `check` exits non-zero and names the field and the segment index

### Requirement: Declarative time anchors

Wherever an event start, event end or SFX time is given, the spec SHALL accept either a number (output seconds) or an anchor: a word in a take (text, optional source time it must follow, start or end edge), or a segment's start or end. Each anchor takes an optional offset in seconds. Anchors SHALL resolve against the transcript and the edge-refined cut.

#### Scenario: Word anchor

- **WHEN** an event starts at `{"word": "launch", "take": "take1", "after": 12.0}` and "launch" is spoken at source 13.40 s inside segment 2
- **THEN** the resolved start equals the output time `build.py` would get from `p.word("take1", "launch", 12.0)`

#### Scenario: Anchor not in the cut

- **WHEN** a word anchor names a word that falls in footage the cut removes
- **THEN** `check` reports an error naming the event, the word and the take, and renders nothing

### Requirement: Check without side effects

`check` SHALL validate the spec and print the planned timeline (per segment: take, in/out after edge refinement, output start, zoom, look) and the edge, edge-energy, echo and SFX reports. It SHALL return errors and warnings as lists. It SHALL write no files outside `edit/`, and it SHALL write no video.

#### Scenario: Errors listed

- **WHEN** the spec references an SFX name that does not exist in the shared SFX library and an overlay type that is not in the overlay registry
- **THEN** `check` exits non-zero and both errors appear in its error list

#### Scenario: Warnings don't fail

- **WHEN** two SFX are 0.2 s apart
- **THEN** `check` exits 0 and the SFX spacing warning appears in its warning list

### Requirement: Inputs confined to the project

Every file a spec names (sources, public files, transcripts) SHALL resolve inside the project after following symlinks, or inside the shared assets. A brand SHALL be a kit slug that exists under `brands/`, or `none`. Overlay event props SHALL NOT name files directly; they reference public files by their staged name.

#### Scenario: Source outside the project

- **WHEN** a source path is `../other-project/take1.mov`
- **THEN** `check` rejects the spec and nothing is read from that path

#### Scenario: Unknown brand

- **WHEN** the spec names brand `does-not-exist`
- **THEN** `check` reports that the brand kit is missing, instead of falling back to another brand

### Requirement: Size limits

A spec SHALL be rejected if the planned output is longer than 180 s, or it has more than 120 segments, 200 overlay events or 200 SFX.

#### Scenario: Too long

- **WHEN** the segments add up to 240 s of output
- **THEN** `check` rejects the spec and states the limit

### Requirement: Render matches build.py

Rendering a spec SHALL produce a preview (720x1280) or final (1080x1920) MP4 at -14 LUFS (±0.5), through the same short-form engine `build.py` uses. A spec and a `build.py` that describe the same edit SHALL produce outputs with equal duration (±1 frame) and matching frames at every cut.

#### Scenario: Ported project

- **WHEN** an existing `build.py` short is rewritten as `edit/short.json` and both render the final
- **THEN** the durations match within one frame, stills at each segment's midpoint are visually identical (PSNR ≥ 40 dB), and both measure -14 LUFS ±0.5

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

### Requirement: Any 9:16 source size

The short-form engine SHALL accept SDR 9:16 sources of any resolution (aspect within 1% of 9:16) by working in a 1080x1920 frame, with face centres given in source pixels. It SHALL reject horizontal sources, other aspect ratios and HDR sources with a message that names `conform`.

#### Scenario: 4K vertical source

- **WHEN** a source is 2160x3840 SDR and its face centre is (1090, 1800)
- **THEN** a static 1.0 zoom keeps the face at the same relative position as the same take at 1080x1920 with face (545, 900)

#### Scenario: Horizontal source

- **WHEN** a source is 1920x1080
- **THEN** `check` reports that the source must be conformed to 9:16 first, and names the `conform` operation

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

`check` SHALL report an error when an edge, locked or not, lies inside a transcript word and on sound (the 30 ms around it above the silence threshold); an edge in the silence of a stretched stamp clips nothing and SHALL NOT be reported. The error SHALL name the segment, edge, word, its range and the nearest boundaries, and the nearest pause when both boundaries run into a neighbour. A lock SHALL NOT make it a warning: a lock only keeps an edge on sound *between* words.

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

### Requirement: Loud edges

`check` SHALL compare each edge's energy with the take's silence threshold ("Silence is measured against the take's speech"). More than 3 dB above it on an unlocked edge SHALL be an error; above it by up to 3 dB, a warning; an edge in measured silence is never loud. Messages SHALL say which edge is loud and by how many dB over the room tone. An in-point at source time 0 SHALL count as clean. In strict mode a warning here SHALL be an error.

#### Scenario: Loud head

- **WHEN** an unlocked in-point lands where the envelope is 20.9 dB over the floor
- **THEN** `check` exits non-zero with an error naming the segment, `in`, `+20.9 dB` and that the cut starts in the middle of sound, and no message contains `<-- check`

#### Scenario: Take starts mid-word

- **WHEN** a segment's `in` is 0.0 and the take's audio is loud at 0.0
- **THEN** no loud-edge error or warning is reported for that in-point

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

For every event, `stills` SHALL draw it alone at its still time with and without its glyphs (same layout), over the source frame it plays on, and report:
- too few changed pixels: `events[N] (<type>) shows almost no text at <t> s`;
- WCAG contrast over the changed pixels (median luminance of each render) under 4.5:1 for text under 48 px tall, else 3:1: `events[N] (<type>) text contrast <r>:1 at <t> s is under <min>:1`.

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

### Requirement: The low look

A segment MAY have `look: "low"`. Its picture SHALL be black and white with added contrast, and it MAY have `freeze` (0.3–0.5 s) of its last frame. The segment's voice SHALL be band-limited, keeping roughly 220 Hz to 2.4 kHz (so the consonants stay audible), with a light short echo and level make-up. A `low` segment SHALL be 1.0–3.0 s long and have a static zoom. A spec SHALL have at most one `low` segment.

#### Scenario: One short low line

- **WHEN** one 2.1 s segment has `look: "low"` and `freeze: 0.4`
- **THEN** that span of the preview is greyscale, holds its last frame for 0.4 s, and its words are recognised by re-transcription

#### Scenario: Two low segments

- **WHEN** two segments have `look: "low"`
- **THEN** `check` exits non-zero saying the low look is used at most once

### Requirement: Zoomed segments keep their length at any frame rate

A segment with a zoom SHALL last as long as its audio whatever the source's frame rate. A still inside it SHALL always find its frame. A frame that can't be made SHALL be an error naming the output time and the segment.

#### Scenario: A 24 fps take with a punch-in

- **WHEN** a 24 fps take has a 2.5 s segment with a punch zoom
- **THEN** the segment renders 2.5 s of video at 30 fps, and a still 0.05 s before its end exists
