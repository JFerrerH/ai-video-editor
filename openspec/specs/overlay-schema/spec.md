# overlay-schema Specification

## Purpose

Give every overlay component and scene primitive a machine-readable props schema, so edits written as data are validated before rendering and a caller can learn the props without reading the component's source.

## Requirements

### Requirement: One schema per component

Every component an overlay event can name (the overlay registry and the scene primitives, except the engine-owned `Captions`) SHALL have a props schema stored beside its source. A schema SHALL declare each prop's type, whether it is required, and where relevant its allowed values, numeric range and string length limit.

#### Scenario: Coverage

- **WHEN** the test suite runs
- **THEN** a test lists every registry and scene component and fails, naming the component, if any has no schema file

#### Scenario: Schema matches the component

- **WHEN** a component's TypeScript props declare a key the schema doesn't, or the schema declares a key the component doesn't read
- **THEN** the coverage test fails and names the component and the key

### Requirement: Shared event props

Props the overlay layer itself reads for every event (`full`, `frame`, `behind`, `dark` and the backdrop's props) SHALL be declared once in a shared schema and accepted on every event, in addition to the component's own props.

#### Scenario: Backdrop on any component

- **WHEN** a `ListScene` event and a `HookTitle` event each have `"full": true`
- **THEN** both pass schema validation

### Requirement: Time fields are event-relative

A prop the schema marks as a time SHALL mean seconds from the event's start. A time prop SHALL accept a number or, in a short-form spec, the same anchors as an event start (a word anchor or a segment anchor), which resolve to event-relative seconds.

#### Scenario: Marked time fields

- **WHEN** the `KineticType`, `ListScene` and `StatScene` schemas are read
- **THEN** `lines[].at`, `stagger`, `items[].at`, `countStart` and `countEnd` are marked as times, with the unit stated

### Requirement: Reveal cues

A schema SHALL mark which props start an entrance (a line, item or word appearing) and how long that entrance takes, including the default cue times the component uses when a time is omitted, so a checker can compute when every entrance finishes without rendering.

#### Scenario: Default cues

- **WHEN** a `ListScene` event has 4 items and no `at` values
- **THEN** the cue times computed from its schema equal the component's own defaults (0.5 s, then every 0.6 s), and the last entrance's finish time is reported

### Requirement: Text and layout annotations

A schema SHALL mark which string props are shown to the viewer as text, and whether the component is a full-layout scene (draws across the safe area) or a floating element.

#### Scenario: Text props listed

- **WHEN** the `StatScene` schema is read
- **THEN** `kicker` and `label` are marked as viewer text and the component is marked full-layout

### Requirement: Schema export

The engine SHALL provide all schemas as one JSON document, keyed by component name, including the shared event props, from the command line and from the headless job runner, with no project needed.

#### Scenario: Export from the CLI

- **WHEN** the schema export command runs
- **THEN** stdout is one JSON object with a key per component in the registry and scene list, each holding its props, and the shared event props under their own key

### Requirement: Stage components

The schema export SHALL include `Stickers`, `BehindWord`, `DocCard`, `StageDrawer`, `PhonePanel`, `CodePanel`, `Gauge`, `Stuck` and `Notice`, each with its props, required fields and the layers it may use. It SHALL also include the shared event props `layer` and `object`. Times inside their props SHALL be relative to the event start and SHALL resolve inside the event, like the existing components.

#### Scenario: Export lists the new components

- **WHEN** `overlay_schema.py --export` runs
- **THEN** the output has a schema for each of the nine components, and `layer` with the values `front`, `behind` and `panel`

#### Scenario: Sticker after the event ends

- **WHEN** a `Stickers` item has `at` past the event's duration
- **THEN** `check` exits non-zero naming the item

### Requirement: Text fields declare their limits

Every component schema field whose text is rendered SHALL declare `maxLength`, and every list SHALL declare `maxItems`. `validate_plan` and spec validation SHALL refuse a value over its limit, naming the field, its length and the limit, without rendering.

#### Scenario: A label over its limit

- **WHEN** a plan gives a ratio-bars label longer than the schema's `maxLength`
- **THEN** `plan_build` is refused with an error naming that label, its length and the limit, in under a second

#### Scenario: A schema without limits

- **WHEN** a component schema has a rendered text field with no `maxLength`
- **THEN** the schema test fails naming the component and the field

### Requirement: Layout matrix

`tools/layout_matrix.py` SHALL render every component in measure mode with generated props: every text field at its `maxLength` in wide capitals (M W O Q D H N U cycled, about 1.5 times the width of ordinary text; digits for a field whose example has no letters), every list at `maxItems`, on three brand fixtures (neutral, dark, pale accent) and two head boxes (close-up, medium shot). It SHALL report each geometry, size, contrast and face finding with the component, the props and the fixture, and exit 1 when there is any. A `face` finding for a floating card whose own example, with its lists at `maxItems`, does not fit above that head either SHALL be listed as "no room" without failing: no limit can fix the framing, and a plan answers it as the finding says.

A limit SHALL NOT be lower than the longest text or list a skill example, test fixture or project plan already uses; a component that can't fit that SHALL be changed to fit it.

#### Scenario: A component that overflows at its own limit

- **WHEN** a component's label overflows its card at the schema's `maxLength`
- **THEN** the matrix reports it and exits 1, until the component fits or its limit is lowered

#### Scenario: Clean run

- **WHEN** every component fits every generated input
- **THEN** the matrix prints a count of components, inputs and fixtures checked and exits 0

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
