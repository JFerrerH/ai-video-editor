# Spec Delta

## ADDED Requirements

### Requirement: Character starter

With `--characters`, `new_project.py` SHALL copy `templates/shots.json` to `edit/shots.json` and
`templates/character_build.py` to `edit/build.py`, fill in the brand, and create `edit/keyframes/`,
`edit/shots/` and `edit/audio/`. When the brand kit has a `library/` folder, the copied `shots.json`
SHALL note the library path. Combining it with `--shortform` SHALL be rejected, because both write
`edit/build.py`. It replaces the storyboard starter: no `edit/storyboard.json` is written.

#### Scenario: Branded character project

- **WHEN** `new_project.py acme-tips --brand acme --type generated --characters` runs and `brands/acme/library/` exists
- **THEN** `edit/shots.json`, `edit/build.py` (with `brand="acme"`), `edit/keyframes/`, `edit/shots/` and `edit/audio/` exist, `shots.json` names `brands/acme/library`, and no `edit/storyboard.json` exists

#### Scenario: Conflicting starters

- **WHEN** `--characters --shortform` are both given
- **THEN** it exits without creating the project and says the two flags can't be combined
