# edit-faults Specification

## Purpose
Faults a viewer notices at once (text over the face or unreadable, captions on overlay text, a cut word, a false start kept, audio played twice, an echoing graphic, hand placement) are checked by the engine, not left to the caller: each is a finding with its fix, an error in strict mode for edits nobody reviews by hand, and the engine places floating overlays itself.

## Requirements

### Requirement: Strict mode

`shortform check`, `stills` and `render` SHALL accept a strict switch (`--strict` on the CLI, `"strict": true` in a headless job's args). In strict mode:
- `lock_in`, `lock_out` and `keep_restart` on any segment SHALL be errors naming the segment and the key;
- every fault listed in "Viewer-visible faults block in strict mode" SHALL be an error instead of a warning.

Without the switch, behaviour SHALL be unchanged by this requirement.

#### Scenario: Lock refused

- **WHEN** a spec has `"lock_out": true` on segment 3 and `check --strict` runs
- **THEN** it exits non-zero with an error naming `segments[3].lock_out` that says locks aren't accepted here and the edge must sit in a pause or between words

#### Scenario: Same spec without strict

- **WHEN** the same spec runs `check` without `--strict` and segment 3's out-point is between two words
- **THEN** no error mentions `lock_out`

#### Scenario: Job arg

- **WHEN** a headless job `{"op": "shortform", "args": {"cmd": "check", "strict": true}}` runs on that spec
- **THEN** the job result has `ok: false` and the same error in `errors`

### Requirement: Viewer-visible faults block in strict mode

In strict mode, these `check` and `stills` findings SHALL be errors, each with a message that names the fix:
- an edge in the middle of sound (over the loud-edge threshold);
- a segment that keeps untranscribed speech;
- a segment that keeps both halves of a marked restart;
- text whose measured contrast is under 3:1.

`stills` in strict mode SHALL return these errors with `renderable: false` and SHALL NOT be followed by a render in the same job.

#### Scenario: Low contrast blocks

- **WHEN** a short's receipt event draws text whose probe contrast is 1.4:1, and `stills --strict` runs
- **THEN** the result has an error naming `events[N] (Receipt)`, the contrast `1.4:1` and the minimum `3:1`, and `renderable` is false

#### Scenario: Locally only a warning

- **WHEN** the same short runs `stills` without strict
- **THEN** the message is in `warnings` and stills are written

### Requirement: The never-list

The engine SHALL keep ten anti-patterns a viewer notices at once: text over the face; unreadable text; captions on overlay text; tiny text; a cut inside a word; a false start or untranscribed speech kept; the same audio twice; a graphic echoing the words; accent text that doesn't read; hand placement. Each SHALL have a check naming the event or segment, the time and the fix, and a fixture that reproduces it. In strict mode each SHALL be an error, and `stills` SHALL return `renderable: false`.

#### Scenario: Floating stat across the face

- **WHEN** a non-full `StatScene` with `value: 500`, `prefix: "$"`, `suffix: " mil"`, a kicker and a label is placed by the caller over a take whose head box is 380–760 x 520–1000 px, against a light wall, and `stills --strict` runs
- **THEN** the result has errors naming that event for text over the face, for contrast under the minimum (kicker and suffix), and for captions on its text, and `renderable` is false

### Requirement: The never-list is printable

`shortform check --never-list` SHALL print the list with each item's check name, so callers can show it.

#### Scenario: List printed

- **WHEN** `shortform check --never-list` runs
- **THEN** it prints 10 numbered items, each with its check name, and exits 0

### Requirement: Text keeps clear of the face

For every overlay event with viewer text, `stills` SHALL measure each text element's box at the event's still time. It SHALL report text whose box intersects the segment's take head box (scaled to output and grown by 6% of the frame width on each side) as `events[N] (<type>) text covers the speaker's face at <t> s`, followed by the fix: `"full": true`, or let the engine place it. When the take has no head box (no person), nothing SHALL be reported.

#### Scenario: Title above the head

- **WHEN** a floating title's text box ends 40 px above the grown head box
- **THEN** no face finding is reported

### Requirement: Text behind the speaker

Text drawn on a layer behind the speaker's cut-out (live-stage `behind` events) SHALL NOT be reported as covering the face, because the speaker covers it. The contrast probe SHALL measure only its pixels the cut-out leaves visible.

#### Scenario: Behind event over the head

- **WHEN** a `behind` event's text box intersects the head box
- **THEN** no face finding is reported for it

### Requirement: Captions never sit on overlay text

During every overlay event with viewer text, not only full-layout ones, captions SHALL move out of the overlay's text boxes: below them if they fit above the bottom safe zone, else above them if they fit below the top safe zone. When neither fits, `stills` SHALL report `captions cover events[N] (<type>) text at <t> s`, with the fix of fewer words or `"full": true`.

#### Scenario: Stacked captions

- **WHEN** a floating stat's label box reaches 790 px and the captions would sit at 830–930 px with no room above or below
- **THEN** `stills` reports the finding for that event

### Requirement: Minimum text size

`stills` SHALL measure the rendered height of each text element (font size × the event's scale, in 1080-wide pixels). It SHALL report any under 28 px as `events[N] (<type>) <field> text is <h> px tall, under 28 px`.

#### Scenario: Tiny kicker

- **WHEN** a kicker renders at 19 px
- **THEN** the finding names the event, `kicker` and `19 px`

### Requirement: Engine places floating overlays

A floating overlay without `frame` whose text would cover the grown head box SHALL be placed between the top safe margin and the head, centred, scaled down (never up) to fit; one clear of the head SHALL stay put. When it fits only with text under the minimum size, `stills` SHALL report a face finding naming the event, with the fix of `"full": true` or fewer words.

#### Scenario: Placed above the head

- **WHEN** a floating `NameTitle` without `frame`, whose text would cross the head, runs over a take whose grown head box starts at 565 px, and `stills --strict` runs
- **THEN** the event's measured text ends at or above 565 px and starts at or below 290 px, its text is at least 28 px tall, and no face or caption finding is reported

#### Scenario: Doesn't fit

- **WHEN** a floating overlay's content would need a scale below the minimum text size to fit the band
- **THEN** `stills --strict` reports an error naming the event and suggesting `"full": true` or fewer words, and `renderable` is false

### Requirement: Hand placement refused in strict mode

In strict mode, `frame` on any event SHALL be an error. Without strict mode, a given `frame` SHALL keep working as today.

#### Scenario: Frame given by hand

- **WHEN** an event has `"frame": {"y": 200}` and `check --strict` runs
- **THEN** it exits non-zero with an error naming `events[N].props.frame` and saying the engine places floating overlays
