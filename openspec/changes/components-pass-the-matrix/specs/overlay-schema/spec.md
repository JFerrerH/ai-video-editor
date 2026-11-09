## ADDED Requirements

### Requirement: Character kind comes from the schema

A text field SHALL declare `x-text: "number"` or `x-text: "symbol"` when it only takes digits or one symbol; otherwise it takes any text. The layout matrix SHALL choose the characters it tests from that declaration, never from the field's example.

#### Scenario: A label whose example is a range of numbers

- **WHEN** a field's example is "18–24" and the schema declares it as plain `x-text`
- **THEN** the matrix tests it with wide letters up to its `maxLength`

#### Scenario: A year

- **WHEN** a field is declared `x-text: "number"`
- **THEN** the matrix tests it with the widest digit

### Requirement: The matrix draws random inputs

Each matrix run SHALL also draw a seeded sample of random inputs: brand palettes from random hues and lightness, light and dark, and text lengths and item counts within the schema limits. It SHALL print the seed, and `--seed` SHALL reproduce a run.

#### Scenario: A fix tuned to the fixtures

- **WHEN** a component passes the three fixed kits only because its colours were picked for them
- **THEN** a run with random palettes reports its contrast finding with the seed

#### Scenario: Reproduced

- **WHEN** the matrix runs again with a printed seed
- **THEN** it draws the same inputs and reports the same findings

### Requirement: Matrix time budget

A full matrix run, fixed and random, SHALL finish in under 5 minutes on a 10-core Mac and print its wall time.

#### Scenario: Full run

- **WHEN** the matrix runs every component on every fixture and the random sample
- **THEN** it prints a wall time under 5 minutes

### Requirement: Refusals with a plan fix are not defects

A face finding that is the engine refusing a floating card with its fix (no room above the head at a readable size in that framing) SHALL be listed apart with the face finding that goes with it, and SHALL NOT fail the run, whatever the text. Text placed over the face without that refusal SHALL still fail it.

#### Scenario: A close-up with no room

- **WHEN** a ratio-bars card with labels at their limit fits above a close-up's head only under the minimum text size
- **THEN** the matrix lists it as refused with its fix and exits 0 if nothing else is found
