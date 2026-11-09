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

`tools/layout_matrix.py` SHALL render every component in measure mode on generated props: each text field at its `maxLength` in wide capitals, each list at `maxItems`, on three brand fixtures (neutral, dark, pale accent) and two head boxes (close-up, medium shot). It SHALL report each geometry, size, contrast and face finding with the component, the props and the fixture, and exit 1 when there is any.

#### Scenario: A component that overflows at its own limit

- **WHEN** a component's label overflows its card at the schema's `maxLength`
- **THEN** the matrix reports it and exits 1, until the component fits or its limit is lowered

#### Scenario: Clean run

- **WHEN** every component fits every generated input
- **THEN** the matrix prints a count of components, inputs and fixtures checked and exits 0
