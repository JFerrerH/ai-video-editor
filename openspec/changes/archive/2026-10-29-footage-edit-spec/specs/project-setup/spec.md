# Spec Delta

## MODIFIED Requirements

### Requirement: Short-form starter

With `--shortform`, the system SHALL copy `templates/shortform_build.py` to `edit/build.py` and `templates/short.json` to `edit/short.json`, with the brand filled in to both when one is given.

#### Scenario: Branded short

- **WHEN** `--shortform --brand acme` is given
- **THEN** `edit/build.py` passes `brand="acme"` to the engine

#### Scenario: Spec starter

- **WHEN** `--shortform --brand acme` is given
- **THEN** `edit/short.json` exists, parses as JSON and has `"brand": "acme"`, and with `--brand none` it has `"brand": "none"`
