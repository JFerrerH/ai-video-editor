## MODIFIED Requirements

### Requirement: Fonts

A font SHALL be TTF, OTF, WOFF or WOFF2 of at most 5 MB, SHALL parse completely (character map, names, metrics and glyph outlines) and SHALL map at least the printable ASCII letters. A valid font SHALL be stored as TTF or OTF (WOFF/WOFF2 unwrapped) and reported with its family, weight and style (`normal` or `italic`). The weight SHALL be a number (100–900) for a static font and a range string `"<min> <max>"` (each clamped to 100–900) for a variable font with a weight axis.

#### Scenario: Corrupt font

- **WHEN** `incoming/` holds a `.ttf` file whose bytes are truncated halfway
- **THEN** it is `invalid` with a reason naming a parse failure, and no file derived from it exists in `fonts/`

#### Scenario: WOFF2 unwrapped

- **WHEN** a valid WOFF2 of a bold italic face is checked
- **THEN** `fonts/` holds a `.ttf` or `.otf` that parses, and the entry reports weight 700 and style `italic`

#### Scenario: Oversized font

- **WHEN** a 6 MB `.otf` is checked
- **THEN** it is `invalid` with a reason naming the 5 MB limit

#### Scenario: Variable font

- **WHEN** a valid TTF with a weight axis from 100 to 800 is checked
- **THEN** the entry reports weight `"100 800"`

## ADDED Requirements

### Requirement: Font entries that don't match their files are warned about
The check SHALL compare each `fontFiles` entry's `weight` and `style` with what its file provides: a range only on a variable font whose axis covers it, a single weight inside a variable font's range or equal to a static font's weight, and `italic` only on an italic face. Each mismatch SHALL be a warning in the result's `warnings` list, naming the entry's field and what the file provides. Warnings SHALL NOT make `ok` false.

#### Scenario: Range on a static font
- **WHEN** `brand.json` lists a static weight-300 face with `"weight": "100 900"`
- **THEN** the result has `ok: true` and a warning naming `fontFiles[0].weight` and saying the file provides weight 300

#### Scenario: Weight outside a variable range
- **WHEN** an entry for a variable font with range 400–800 has `"weight": "100 800"`
- **THEN** the result has `ok: true` and a warning naming the entry's `weight` and the range `400 800`

#### Scenario: Matching entries
- **WHEN** a variable font entry has no `weight`, and a static weight-400 face's entry has `"weight": 400`
- **THEN** the result's `warnings` is empty

#### Scenario: Italic on an upright face
- **WHEN** an entry for an upright face has `"style": "italic"`
- **THEN** the result has `ok: true` and a warning naming the entry's `style` and saying the file is upright

#### Scenario: Font file that no longer loads
- **WHEN** an entry's file in `fonts/` doesn't parse as a font (for example replaced after it was validated)
- **THEN** the result has `ok: true` and a warning naming the entry's `file` and the parse failure

#### Scenario: Kit without mismatches
- **WHEN** the check runs on a copy of `brands/_template/`
- **THEN** the result has `warnings: []`
