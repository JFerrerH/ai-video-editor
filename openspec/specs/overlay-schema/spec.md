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
