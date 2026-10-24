# Spec Delta

## Purpose

Keep each brand's animated character clips in a reusable, tagged library inside its private kit, so
new videos reuse existing shots first and only pay for what a script lacks.

## ADDED Requirements

### Requirement: Library lives in the brand kit

A brand's clip library SHALL live at `brands/<slug>/library/`, inside the brand kit, which is
gitignored. It contains `spec.json`, `index.json`, `clips/`, `keyframes/` and `README.md`. No library
content (clips, prompts, character descriptions) SHALL be written to a tracked path.

#### Scenario: Nothing tracked

- **WHEN** a library is generated for a brand
- **THEN** `git status --porcelain` shows no new or changed file under `brands/<slug>/`, `tools/` or `templates/` from the library content

### Requirement: Neutral template

`brands/_template/library/README.md` SHALL document the layout, the `index.json` fields and the reuse
workflow using only neutral examples. It SHALL name no real brand or character.

#### Scenario: New brand

- **WHEN** a new brand kit is created by copying `brands/_template/`
- **THEN** it contains `library/README.md` and no clips

### Requirement: Index entries

Every clip in `clips/` SHALL have one `index.json` entry: `id`, `file`, `cast` (list), `mood`, `use`
(what lines it fits), `action`, `camera`, `dur` (measured seconds) and `source` (`library` or the
project it came from).

#### Scenario: Measured duration

- **WHEN** a clip is added to the library
- **THEN** its entry's `dur` equals the file's ffprobe duration to 0.01 s

### Requirement: Generate library clips

The library tool SHALL generate keyframes and then clips for the entries in `spec.json`, through the
same paid-call rules as character projects (estimate, budget, spend log in the library folder). It
SHALL skip entries whose files already exist.

#### Scenario: Incremental add

- **WHEN** one new entry is added to a `spec.json` that already has 14 generated clips
- **THEN** a run makes exactly one keyframe request and, after that, one clip request

### Requirement: Import from a finished project

The library tool SHALL import chosen shots from a project into the library with tags given on the
command line. It copies the clip and its keyframe and adds an index entry whose `source` is the
project name. It SHALL refuse an id that already exists.

#### Scenario: Import

- **WHEN** a project's `shots/s05_reveal.mp4` is imported as `reveal_doorway` with mood `warm`
- **THEN** `clips/reveal_doorway.mp4` exists and `index.json` has its entry with the project as `source`

### Requirement: Lookup by tag

The library tool SHALL list clips filtered by cast member, mood or a word in `use`, printing id,
duration, cast and use.

#### Scenario: Filter by cast and mood

- **WHEN** clips are listed with `--cast hero --mood happy`
- **THEN** only entries whose `cast` contains `hero` and whose `mood` is `happy` are printed

### Requirement: Shots can point at library clips

A shot in a project's `shots.json` with `"library": "<id>"` SHALL use that brand library clip instead
of a generated one. The animate tool SHALL make no paid call for it, and the shot-cut tool SHALL read
the clip from the library.

#### Scenario: Mixed shot list

- **WHEN** a shot list has 8 shots of which 6 point at library clips
- **THEN** the animate tool estimates and generates only 2 clips, and `base.mov` uses all 8
