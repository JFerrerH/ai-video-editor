# project-setup Specification

## Purpose

Every request starts as a project, `footage/<name>/` with `edit/project.md`, that records its brand,
type, platforms and language. Later sessions pick up from that file, and no brand's taste leaks into
another project. Tool: `tools/new_project.py`.

## Requirements

### Requirement: Project scaffold

`new_project.py` SHALL create `footage/<name>/edit/project.md` from `templates/project.md`, with the
brand, type, platforms, language and date filled in. It SHALL reject names that aren't kebab-case
ASCII, refuse to overwrite an existing `project.md`, and refuse a brand that has no
`brands/<slug>/brand.json`.

#### Scenario: Existing project

- **WHEN** `new_project.py` runs for a name whose `edit/project.md` already exists
- **THEN** it exits without changing anything and says to continue that project

#### Scenario: Missing brand kit

- **WHEN** `--brand acme` is given and `brands/acme/brand.json` does not exist
- **THEN** it exits and says to copy `brands/_template/` first

### Requirement: Short-form starter

With `--shortform`, the system SHALL copy `templates/shortform_build.py` to `edit/build.py` and `templates/short.json` to `edit/short.json`, with the brand filled in to both when one is given.

#### Scenario: Branded short

- **WHEN** `--shortform --brand acme` is given
- **THEN** `edit/build.py` passes `brand="acme"` to the engine

#### Scenario: Spec starter

- **WHEN** `--shortform --brand acme` is given
- **THEN** `edit/short.json` exists, parses as JSON and has `"brand": "acme"`, and with `--brand none` it has `"brand": "none"`

### Requirement: Storyboard starter for from-scratch projects

For `--type generated` or `--type motion-graphics`, the system SHALL copy `templates/storyboard.json`
to `edit/storyboard.json` with `brand` set and `aspect` taken from the first platform (reels, tiktok,
shorts → 9:16; youtube, master → 16:9; linkedin → 4:5; x → 1:1; otherwise 9:16), and create
`edit/images/`. The copied template SHALL pass `storyboard.py check` with no ERRORs.

#### Scenario: YouTube explainer

- **WHEN** `--type generated --platforms youtube,reels` is given
- **THEN** `edit/storyboard.json` has `"aspect": "16:9"`

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
