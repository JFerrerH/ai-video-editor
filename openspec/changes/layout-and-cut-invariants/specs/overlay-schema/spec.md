## ADDED Requirements

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
