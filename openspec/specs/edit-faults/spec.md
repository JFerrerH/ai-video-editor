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

### Requirement: Text behind the speaker stays readable

`stills` SHALL draw each `behind` event with and without the speaker's cut-out and compare the pixels of its text. When the speaker leaves under 85 % of them visible, it SHALL report `events[N] (<type>) is mostly hidden by the speaker`, naming the share and the fix (raise it with `props.y`, shorten it, or use the front layer). In strict mode this SHALL be an error and `stills` SHALL return `renderable: false`.

#### Scenario: Word behind the head

- **WHEN** a `BehindWord` at `y` 640 sits where the speaker's head covers 38 % of its letters
- **THEN** `stills --strict` reports 62 % of its text shows, under 85 %, and `renderable` is false

### Requirement: Components keep their small text legible

Stage and overlay components SHALL draw their kickers and labels at 30 px or more, in a bold weight and a colour that reads on their own card, so that `stills --strict` passes on ordinary footage. The legibility probe SHALL measure at full resolution, because thin strokes measured at half size blur to a false low contrast. A card whose text leaves the screen (a card dropping into a drawer) SHALL be probed at the moment its text is on screen.

#### Scenario: Card label on a light card

- **WHEN** a `Stuck`, `Gauge` or `ProgressCard` label is probed at full resolution
- **THEN** its contrast is at least 4.5:1 and its height at least 28 px

### Requirement: Graphics clear the head as it is at that moment

The top of the speaker's head SHALL be measured at each second of a take, in the columns around the face. A floating graphic SHALL be judged against the highest the head gets while the graphic is on screen, with 40 px of air, and its whole card SHALL count, not only its text. It MAY go up to 100 px from the top. When a take can't be tracked, the take's head box SHALL apply.

Placement SHALL apply to every graphic on the front layer, except those whose schema has `x-place: own`. It SHALL take the camera into account: a move on screen for at least 80 % of a graphic goes by where it puts the head, and a shorter one counts both positions. Its values SHALL have one source, read by the picture and the check.

#### Scenario: A graphic with a fixed default position

- **WHEN** a `Gauge` or `Notice` at its default position reaches the head
- **THEN** it is moved above the head like any other card

#### Scenario: A side move raises the head

- **WHEN** a floating card plays during a `side` move that scales the speaker up
- **THEN** it clears the head as the move puts it

#### Scenario: Any source size

- **WHEN** the same framing comes as 1080x1920 and as 720x1280
- **THEN** the card lands in the same place

#### Scenario: A card over the hair

- **WHEN** a floating card's body reaches the head while its text doesn't
- **THEN** the card is moved above the head

#### Scenario: The speaker leans back later

- **WHEN** a take's head top is at 500 px while one card is on screen and at 416 px during another
- **THEN** each card is placed against its own moment

### Requirement: The render keeps where a graphic was placed

A placement SHALL be saved in `edit/overlay_placed.json`, keyed by the event, and applied again by a later pass in the same project. The render SHALL show each graphic where the stills showed it.

#### Scenario: Render in the same job as the stills

- **WHEN** a plan is compiled, its stills place a card, and the preview renders from the cached measurements
- **THEN** the rendered event has that placement
