# brand-theme Specification

## Purpose
Turns a brand kit, or no brand, into the theme Remotion renders with: which face each font role uses, how brand font
files are loaded, and how a font that can't be loaded is reported.

## Requirements

### Requirement: Every accepted weight form renders
A `fontFiles` entry's `weight` SHALL render whether the kit gives it as a number (`400`), a numeric string (`"400"`)
or a range string (`"100 800"`). The theme passed to Remotion SHALL carry every weight as a string.

#### Scenario: Numeric weight
- **WHEN** a kit that passed the check lists a variable font with `"weight": 400` and a branded short runs `shortform stills`
- **THEN** the stills are written, the job's `ok` is true, and the overlay props written for it hold `"weight": "400"`

#### Scenario: Theme from a numeric weight
- **WHEN** `load_brand` reads a kit with `"weight": 300` on one font file and no weight on another
- **THEN** the theme's `fontFiles` hold `"300"` for the first and no weight for the second

### Requirement: Brand font that doesn't load
If a brand font file can't be loaded during a render, the render SHALL fail with an error that names the family,
weight, style and file of that font entry.

#### Scenario: Unloadable font
- **WHEN** a kit's font file is replaced, after the check, by bytes the browser can't load, and `shortform stills` runs
- **THEN** the job fails and its `error` contains `Font did not load`, the family, the weight, the style and the file name

### Requirement: Missing font roles use the kit's own faces
When a kit leaves a font role (`serif`, `sans` or `mono`) unset, the theme SHALL use the kit's `sans` for it, or
else the family of its first `fontFiles` entry. A neutral face SHALL be used for a role only when the kit names no
font at all.

#### Scenario: Kit with sans and mono only
- **WHEN** a kit sets `sans` and `mono` but no `serif`
- **THEN** the theme's `serif` equals the kit's `sans`, and a still of an `EndCard` with a title shows the headline in the kit's sans (checked by reading the PNG)

#### Scenario: Kit with font files only
- **WHEN** a kit sets no `fonts` and lists one font file of family `Brand Sans`
- **THEN** the theme's `serif`, `sans` and `mono` are all `Brand Sans`

#### Scenario: Kit roles set
- **WHEN** a kit sets all three roles
- **THEN** the theme's fonts are exactly the kit's

### Requirement: Unbranded renders use installed faces
With no brand, each font role SHALL name a face that is installed where the render runs: the existing Mac faces
first, then Noto Serif, Noto Sans and Noto Sans Mono, which the Linux image ships. No role SHALL fall back to the
browser's default font.

#### Scenario: Unbranded still on Linux
- **WHEN** an `EndCard` with a title, tagline and url is rendered as a still with no brand in the Linux image
- **THEN** the still differs from the same still with every role forced to `Liberation Serif`, and is identical to the same still with the roles forced to `Noto Serif`, `Noto Sans` and `Noto Sans Mono`

#### Scenario: Unbranded on the Mac
- **WHEN** the same still is rendered on a Mac
- **THEN** it is identical to a still rendered before this change
