## ADDED Requirements

### Requirement: Accent text reads on its fill

Wherever a component draws the brand accent as text, or as the border of a text stamp, on a fill (a card, a backdrop), the colour SHALL reach WCAG contrast ≥ 3:1 against that fill. When the brand accent doesn't, the theme SHALL use a darker colour of the same hue that does. If no colour of that hue reaches 3:1, it SHALL use `ink`. Accent used as a fill behind text (a highlighter) SHALL keep using the text colour that reads on the accent.

#### Scenario: Pale accent on white

- **WHEN** a brand's accent is `#E8FD5A`, its ink is `#16150F`, and the receipt overlay draws its total stamp on its white card
- **THEN** the stamp colour in the rendered props has contrast ≥ 3:1 against `#FFFFFF`, and the probe reports no contrast warning for that event

#### Scenario: Accent that already reads

- **WHEN** the accent is `#1F4FD8` on the same card
- **THEN** the accent is used unchanged

### Requirement: Every component readable with extreme accents

A test SHALL render a still of every overlay and scene in the registry with two fixture brands: a pale accent (`#E8FD5A` on a light background) and a dark accent (`#1A1A40` on a dark background). It SHALL run the legibility probe on each, and SHALL fail naming each component and brand whose text contrast is under 3:1.

#### Scenario: Matrix passes

- **WHEN** the test runs on the engine after this change
- **THEN** it exits 0 and reports one probe result per component and brand
