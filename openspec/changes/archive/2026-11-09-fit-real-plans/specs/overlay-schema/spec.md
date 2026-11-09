## ADDED Requirements

### Requirement: Limits are never under real use

No text field's `maxLength` and no list's `maxItems` SHALL be lower than the most real plans and specs used for it. The repository SHALL keep those maxima as a table of numbers per component field, and a test SHALL fail naming the field when a limit is under its floor. A limit raised to its floor SHALL pass the layout matrix at the new value; a component that overflows there SHALL be fixed through the shared text fitting, not by lowering the limit.

#### Scenario: A limit under its floor

- **WHEN** a schema lowers a card kicker's `maxLength` under the 22 characters real plans used
- **THEN** the schema test fails naming the component, the field, the limit and the floor

#### Scenario: A component at the floor

- **WHEN** the layout matrix draws every component with each field at its limit, including the raised ones
- **THEN** it reports no finding
