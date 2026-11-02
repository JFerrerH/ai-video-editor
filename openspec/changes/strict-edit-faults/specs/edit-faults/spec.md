## ADDED Requirements

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

The engine SHALL keep a list of anti-patterns a viewer notices at once. Each SHALL have a check whose finding names the event or segment, the time and the fix, and a test fixture that reproduces it. In strict mode every one SHALL be an error, and `stills` SHALL return `renderable: false`. The list:
1. text over the face;
2. text unreadable against what is behind it;
3. captions on top of overlay text;
4. text too small;
5. a cut inside a word;
6. a false start or untranscribed speech kept;
7. the same source audio twice;
8. a graphic echoing the words being spoken;
9. accent text on a fill it doesn't read on;
10. `frame` given by hand.

`shortform check --never-list` SHALL print the list with each item's check name, so callers can show it.

#### Scenario: Floating stat across the face

- **WHEN** a non-full `StatScene` with `value: 500`, `prefix: "$"`, `suffix: " mil"`, a kicker and a label is placed by the caller over a take whose head box is 380–760 x 520–1000 px, against a light wall, and `stills --strict` runs
- **THEN** the result has errors naming that event for text over the face, for contrast under the minimum (kicker and suffix), and for captions on its text, and `renderable` is false

#### Scenario: List printed

- **WHEN** `shortform check --never-list` runs
- **THEN** it prints 10 numbered items, each with its check name, and exits 0

### Requirement: Text keeps clear of the face

For every overlay event with viewer text, `stills` SHALL measure each text element's box at the event's still time. It SHALL report text whose box intersects the segment's take head box (scaled to output and grown by 6% of the frame width on each side) as `events[N] (<type>) text covers the speaker's face at <t> s`, followed by the fix: `"full": true`, or let the engine place it. When the take has no head box (no person), nothing SHALL be reported. Text drawn on a layer behind the speaker's cut-out (live-stage `behind` events) SHALL not be reported, because the speaker covers it. The contrast probe SHALL measure only its visible pixels.

#### Scenario: Title above the head

- **WHEN** a floating title's text box ends 40 px above the grown head box
- **THEN** no face finding is reported

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

In strict mode, `frame` on any event SHALL be an error. A floating overlay without `frame` SHALL be placed in the band between the top safe margin and the top of the grown head box, centred horizontally. It SHALL be scaled down, never up, to fit that band. When it fits only below the minimum text size, `check` SHALL report an error naming the event, with the fix of `"full": true` or fewer words. Without strict mode, a given `frame` SHALL keep working as today.

#### Scenario: Placed above the head

- **WHEN** a floating `Receipt` without `frame` runs over a take whose grown head box starts at 560 px, and `stills --strict` runs
- **THEN** the event's measured content box ends at or above 560 px, its text is at least 28 px tall, and no face or caption finding is reported

#### Scenario: Doesn't fit

- **WHEN** a floating overlay's content would need a scale below the minimum text size to fit the band
- **THEN** `check --strict` reports an error naming the event and suggesting `"full": true` or fewer words
