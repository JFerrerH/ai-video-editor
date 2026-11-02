## ADDED Requirements

### Requirement: Stage components

The schema export SHALL include `Stickers`, `BehindWord`, `DocCard`, `StageDrawer`, `PhonePanel`, `CodePanel`, `Gauge`, `Stuck` and `Notice`, each with its props, required fields and the layers it may use. It SHALL also include the shared event props `layer` and `object`. Times inside their props SHALL be relative to the event start and SHALL resolve inside the event, like the existing components.

#### Scenario: Export lists the new components

- **WHEN** `overlay_schema.py --export` runs
- **THEN** the output has a schema for each of the nine components, and `layer` with the values `front`, `behind` and `panel`

#### Scenario: Sticker after the event ends

- **WHEN** a `Stickers` item has `at` past the event's duration
- **THEN** `check` exits non-zero naming the item
