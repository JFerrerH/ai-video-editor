## ADDED Requirements

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
