# Spec Delta

## Purpose

Describe a vertical short made from talking-head footage entirely as validated data (`edit/short.json`), so it can be checked and rendered without running project code, with the same result as the equivalent `build.py`.

## ADDED Requirements

### Requirement: Spec file format

A short-form project SHALL be describable by one JSON file, `edit/short.json`, holding the brand, sources with face centres, segments, caption settings, emphasis phrases, overlay events, SFX and public files. Every field `templates/shortform_build.py` exposes SHALL have a JSON form. Unknown fields SHALL be errors.

#### Scenario: Template spec checks clean

- **WHEN** `edit/short.json` is the unmodified starter written by `tools/new_project.py --shortform`, with its one source present and transcribed
- **THEN** `check` exits 0 and reports one segment and the planned duration

#### Scenario: Unknown field

- **WHEN** a segment in `edit/short.json` contains a field `"filter": "..."`
- **THEN** `check` exits non-zero and names the field and the segment index

### Requirement: Declarative time anchors

Wherever an event start, event end or SFX time is given, the spec SHALL accept either a number (output seconds) or an anchor: a word in a take (text, optional source time it must follow, start or end edge), or a segment's start or end. Each anchor takes an optional offset in seconds. Anchors SHALL resolve against the transcript and the edge-refined cut.

#### Scenario: Word anchor

- **WHEN** an event starts at `{"word": "launch", "take": "take1", "after": 12.0}` and "launch" is spoken at source 13.40 s inside segment 2
- **THEN** the resolved start equals the output time `build.py` would get from `p.word("take1", "launch", 12.0)`

#### Scenario: Anchor not in the cut

- **WHEN** a word anchor names a word that falls in footage the cut removes
- **THEN** `check` reports an error naming the event, the word and the take, and renders nothing

### Requirement: Check without side effects

`check` SHALL validate the spec and print the planned timeline (per segment: take, in/out after edge refinement, output start, zoom, look) and the edge, edge-energy, echo and SFX reports. It SHALL return errors and warnings as lists. It SHALL write no files outside `edit/`, and it SHALL write no video.

#### Scenario: Errors listed

- **WHEN** the spec references an SFX name that does not exist in the shared SFX library and an overlay type that is not in the overlay registry
- **THEN** `check` exits non-zero and both errors appear in its error list

#### Scenario: Warnings don't fail

- **WHEN** two SFX are 0.2 s apart
- **THEN** `check` exits 0 and the SFX spacing warning appears in its warning list

### Requirement: Inputs confined to the project

Every file a spec names (sources, public files, transcripts) SHALL resolve inside the project after following symlinks, or inside the shared assets. A brand SHALL be a kit slug that exists under `brands/`, or `none`. Overlay event props SHALL NOT name files directly; they reference public files by their staged name.

#### Scenario: Source outside the project

- **WHEN** a source path is `../other-project/take1.mov`
- **THEN** `check` rejects the spec and nothing is read from that path

#### Scenario: Unknown brand

- **WHEN** the spec names brand `does-not-exist`
- **THEN** `check` reports that the brand kit is missing, instead of falling back to another brand

### Requirement: Size limits

A spec SHALL be rejected if the planned output is longer than 180 s, or it has more than 120 segments, 200 overlay events or 200 SFX.

#### Scenario: Too long

- **WHEN** the segments add up to 240 s of output
- **THEN** `check` rejects the spec and states the limit

### Requirement: Render matches build.py

Rendering a spec SHALL produce a preview (720x1280) or final (1080x1920) MP4 at -14 LUFS (±0.5), through the same short-form engine `build.py` uses. A spec and a `build.py` that describe the same edit SHALL produce outputs with equal duration (±1 frame) and matching frames at every cut.

#### Scenario: Ported project

- **WHEN** an existing `build.py` short is rewritten as `edit/short.json` and both render the final
- **THEN** the durations match within one frame, stills at each segment's midpoint are visually identical (PSNR ≥ 40 dB), and both measure -14 LUFS ±0.5

### Requirement: Stills of the finished short

Short-form `stills` SHALL write PNG frames of the composited short (cut, overlays and captions) at given output times into `edit/stills/`, or at each segment's midpoint when no times are given. It SHALL do this without rendering the full video.

#### Scenario: Default stills

- **WHEN** `stills` runs on a spec with 6 segments and no times
- **THEN** 6 PNGs appear in `edit/stills/`, each 540x960 or larger, and no `final.mp4` is written

### Requirement: Any 9:16 source size

The short-form engine SHALL accept SDR 9:16 sources of any resolution (aspect within 1% of 9:16) by working in a 1080x1920 frame, with face centres given in source pixels. It SHALL reject horizontal sources, other aspect ratios and HDR sources with a message that names `conform`.

#### Scenario: 4K vertical source

- **WHEN** a source is 2160x3840 SDR and its face centre is (1090, 1800)
- **THEN** a static 1.0 zoom keeps the face at the same relative position as the same take at 1080x1920 with face (545, 900)

#### Scenario: Horizontal source

- **WHEN** a source is 1920x1080
- **THEN** `check` reports that the source must be conformed to 9:16 first, and names the `conform` operation
