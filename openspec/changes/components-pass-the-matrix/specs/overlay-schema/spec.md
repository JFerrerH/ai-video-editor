## ADDED Requirements

### Requirement: Text colour by surface

Every component SHALL draw text in a colour the theme picks for the surface that text sits on, at 4.5:1 or more against that surface (3:1 for text of 48 px or more), for any brand palette.

#### Scenario: Muted text on a white card

- **WHEN** a brand's muted colour is 2.5:1 against white and a component draws a caption in it on a white card
- **THEN** the theme returns a darker colour for that caption, and the legibility probe measures it at 4.5:1 or more

### Requirement: Type sizes from tokens

Components SHALL take font sizes from theme tokens. The smallest token SHALL render at least 30 px at the component's own scale.

#### Scenario: No size under the minimum

- **WHEN** the matrix draws every component with its example text on every fixture
- **THEN** no `small_text` finding is reported

### Requirement: Declared overhangs

An element designed to extend past its card SHALL carry `data-overhang` in its markup. It SHALL NOT be reported for leaving its card, and SHALL still be held to the frame and the safe area.

#### Scenario: A stamp across the card's edge

- **WHEN** a stamp marked `data-overhang` crosses its card's top edge and stays inside the frame
- **THEN** no `outside` finding is reported for it

### Requirement: The matrix draws random inputs

Each matrix run SHALL also draw a seeded sample of random inputs: brand palettes from random hues and lightness, light and dark, and text lengths and item counts within the schema limits. It SHALL print the seed, and `--seed` SHALL reproduce a run.

#### Scenario: A fix tuned to the fixtures

- **WHEN** a component passes the three fixed kits only because its colours were picked for them
- **THEN** a run with random palettes reports its contrast finding with the seed

### Requirement: Refusals with a plan fix are not defects

A face finding that is the engine refusing a floating card with a plan fix SHALL be listed apart and SHALL NOT fail the run. Text placed over the face SHALL still fail it.

#### Scenario: A close-up with no room

- **WHEN** a floating card fits above the head only under the minimum text size in a close-up
- **THEN** the matrix lists it as a refusal and exits 0 if nothing else is found

### Requirement: Limits are computed

`--fit-limits` SHALL find, per text field and list, the largest `maxLength` or `maxItems` that passes on every fixture and the random sample, write it to the schema, and print the seed it used.

#### Scenario: Limit lowered by the rule

- **WHEN** a label overflows at 20 characters and fits at 12 on every input
- **THEN** `--fit-limits` writes `maxLength: 12` for it

### Requirement: The matrix runs in parallel

The matrix SHALL split its inputs across worker processes, each with its own work directory and Remotion bundle, and a full run SHALL finish in under 5 minutes on a 10-core Mac. It SHALL print its wall time.

#### Scenario: Full run

- **WHEN** the matrix runs every component on every fixture and the random sample
- **THEN** it prints a wall time under 5 minutes
