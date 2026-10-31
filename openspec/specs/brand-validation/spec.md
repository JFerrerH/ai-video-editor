# brand-validation Specification

## Purpose
Prove that every brand file (font, raster image, SVG) is harmless and usable, and that `brand.json` has the right shape, before any render loads them. Files that fail are removed, not kept.

## Requirements

### Requirement: Check a brand directory

`brand` with `cmd: check` SHALL validate every file directly in `<dir>/incoming/` (`dir` defaults to `brand`, inside the project) and SHALL return one entry per file with its name, kind, status (`valid` or `invalid`), reason when invalid, and where it was stored when valid. Valid files SHALL move into `<dir>/fonts/` or `<dir>/logos/`; invalid files, including unsupported types, SHALL be deleted, leaving `incoming/` empty.

#### Scenario: Mixed upload

- **WHEN** `incoming/` holds a valid TTF, a valid PNG, a corrupt TTF and a `.txt` file
- **THEN** the result lists four entries (two `valid`, two `invalid` with reasons), `fonts/` holds the TTF, `logos/` holds the PNG, and `incoming/` is empty

#### Scenario: Same name again

- **WHEN** a valid `Brand-Bold.ttf` is checked and `fonts/Brand-Bold.ttf` already exists
- **THEN** the new file replaces it and the entry says `replaced: true`

### Requirement: Same check on the CLI

The same check SHALL run from the command line on any kit directory, such as `brands/<slug>/`, with the same rules and the same result.

#### Scenario: Local kit

- **WHEN** `tools/brand_check.py brands/<slug>` runs on a kit whose `incoming/` holds one valid OTF
- **THEN** the OTF is in `brands/<slug>/fonts/`, `incoming/` is empty, and the printed result matches what the `brand` op returns for the same files

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

### Requirement: Raster images

A raster image SHALL be PNG or JPEG of at most 20 MB and at most 8000 px on each side, and SHALL decode fully. A valid image SHALL be re-encoded as PNG in `logos/` (orientation applied, metadata dropped, transparency kept) and reported with its width and height. A file whose bytes do not match its extension SHALL be invalid.

#### Scenario: Image bomb

- **WHEN** a 40 KB PNG declares 30000x30000 pixels
- **THEN** it is `invalid` with a reason naming the size limit, and it is refused before being decoded

#### Scenario: Wrong extension

- **WHEN** a file named `logo.png` holds a JPEG
- **THEN** it is accepted as a JPEG and stored as `logos/logo.png` (re-encoded PNG)

#### Scenario: Not an image

- **WHEN** a file named `logo.png` holds HTML text
- **THEN** it is `invalid` with a reason saying it is not a PNG or JPEG

### Requirement: SVG

An SVG SHALL be at most 2 MB, SHALL parse as XML with no DTD or entity declarations, and SHALL be rejected if it contains a `script`, `foreignObject`, `iframe`, `embed` or `object` element, any `on*` attribute, any `href`/`xlink:href` other than a fragment (`#id`) or an embedded PNG/JPEG data URI, or any CSS `url()`/`@import` that is not a fragment. A clean SVG SHALL be stored only as a PNG rasterization (long side 2048 px, transparency kept) in `logos/`; the SVG source SHALL NOT be kept.

#### Scenario: SVG with script

- **WHEN** an uploaded logo SVG contains a `<script>` element
- **THEN** it is `invalid` with a reason naming the script, and nothing from it exists in `logos/`

#### Scenario: External reference

- **WHEN** an SVG has `<image href="https://example.com/x.png">`
- **THEN** it is `invalid` with a reason naming the external reference

#### Scenario: Entity expansion

- **WHEN** an SVG declares nested XML entities (a "billion laughs" file)
- **THEN** it is `invalid` and the check finishes in under 2 s

#### Scenario: Clean SVG

- **WHEN** a plain two-colour SVG logo with a 200x50 viewBox is checked
- **THEN** `logos/<name>.png` is 2048x512 with transparent corners, and no `.svg` file is in `logos/`

### Requirement: Kit shape

If `<dir>/brand.json` exists, the check SHALL validate it after the files: `name` (≤ 80 characters), `colors` (the seven known roles, each `#RRGGBB`), `fonts` (`serif`, `sans`, `mono`), `fontFiles` (each `file` a validated font in `fonts/`) and `captions` (only options the renderer accepts, within range). Unknown keys SHALL be errors.

#### Scenario: Template kit

- **WHEN** the check runs on a copy of `brands/_template/`
- **THEN** it reports no kit errors

### Requirement: Kit errors fail the check

Each kit error SHALL name its field. Kit errors SHALL make the job's `ok` false; invalid files alone SHALL NOT.

#### Scenario: Invalid colour

- **WHEN** `brand.json` has `"colors": {"accent": "red"}`
- **THEN** the result has `ok: false` and an error naming `colors.accent`

#### Scenario: Font file not validated

- **WHEN** `brand.json` lists `{"family": "Brand", "file": "Brand-Bold.ttf"}` and `fonts/Brand-Bold.ttf` does not exist
- **THEN** the result has `ok: false` and an error naming `fontFiles[0].file` and the file

#### Scenario: Valid kit renders

- **WHEN** a kit whose fonts and logo passed the check is used by a branded short in a pilot project
- **THEN** `shortform stills` succeeds and a still with a caption shows the brand font (checked by reading the PNG)

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
