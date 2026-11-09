## ADDED Requirements

### Requirement: Graphics stay inside their card and the frame

In measure mode, every visible text node and every element that draws a background, border or image SHALL be measured with its box. Each SHALL sit inside the box of its card (the nearest ancestor that draws a background) and inside the frame, with 2 px of tolerance; text SHALL also keep between the top limit (100 px) and the bottom safe limit (1536 px), while a shape (a drawer at the bottom of the frame) is held only to the frame. An element that breaks either SHALL be a finding of kind `outside` naming the event, the field or element, the box and the edge it crosses. In strict mode it SHALL be an error.

#### Scenario: Label wider than its column

- **WHEN** a ratio-bars event's third label is a 12-letter word in a column narrower than the word
- **THEN** `check --strict` with stills fails with an `outside` error naming that label and the card's right edge

#### Scenario: Bar taller than its card

- **WHEN** a bar's height plus its label exceeds the card's inner height at the bar's entrance finish
- **THEN** an `outside` finding names the bar and the card's top edge

#### Scenario: Everything inside

- **WHEN** every text node and shape of an event sits inside its card and the safe area
- **THEN** no `outside` finding is reported for it

### Requirement: Layout is measured at every entrance

Each event SHALL be measured at the finish of every reveal cue it has (`cue_finish`) and at its still time, so an element that appears later is measured once it is on screen. Measurements at times after an event's `x-still-before` cue SHALL be skipped.

#### Scenario: A late item

- **WHEN** a list's third item enters 4 s after the event starts and overflows its card only then
- **THEN** the overflow is reported, with the time of that item's entrance finish

### Requirement: Captions keep clear of the head when they move

When captions move above or below a graphic to clear it, the new caption band SHALL also clear the speaker's head box at that moment. If no position clears both, the finding SHALL be of kind `face`, naming the event and the time, with the fix (fewer words, `"full": true`, or a `corner` or `side` move), and the captions SHALL NOT be placed over the head.

#### Scenario: Drawer at the bottom of a medium shot

- **WHEN** a drawer's card reaches the caption band and the only band above it crosses the speaker's eyes
- **THEN** `check --strict` with stills fails with a `face` error for captions at that event, and no caption position over the head is written

### Requirement: Cuts have air

An out-point SHALL have at least the edge refinement's `post` seconds of silence after the last word before the next sound, and an in-point at least its `pre` seconds before the first word. An edge with less SHALL be a finding of kind `no_air` giving the edge, the silence there and the next sound's start. In strict mode it SHALL be an error, except for the video's last out-point, which the tail handles.

#### Scenario: A real pause

- **WHEN** the next word starts 0.4 s after the kept sentence's last word
- **THEN** no `no_air` finding is reported

#### Scenario: No pause in a hand-made spec

- **WHEN** a segment's out-point sits 0.10 s before the next word in the source, in the middle of the short
- **THEN** `check --strict` fails with a `no_air` error giving the edge, 0.10 s, and the next word's start

### Requirement: Plans name the sentence for a cut with no air

In `plan_build`, a `no_air` error SHALL name the kept sentence at that edge and say to keep the neighbouring sentence or end at another one, and SHALL be reported before any still is rendered.

#### Scenario: Next word 0.1 s away

- **WHEN** a kept sentence ends 0.10 s before the next word in the source, and the plan keeps that sentence but not the next in the middle of the video
- **THEN** `plan_build` is refused with a `no_air` error naming the sentence, before any still

### Requirement: The video ends with a tail

The last segment SHALL hold its final frame for a tail after the last word, and the audio SHALL fade out over the cut's available silence, so the video never ends within the tail of the last word. The tail's length SHALL be a constant measured from approved reference shorts, recorded in the tool with its source (0.30 s: the longest ending among the approved talking-head exports, whose endings run 0.04 to 0.30 s after the last speech energy).

#### Scenario: Last word runs into the next

- **WHEN** the last kept word ends 0.10 s before another word in the source
- **THEN** the render's audio is silent from before that next word's onset, the picture holds for the tail, and the output's duration is the last word's end plus the tail

#### Scenario: Measured on the output

- **WHEN** a preview is rendered
- **THEN** the gap between the last speech energy and the end of the file is at least the tail
