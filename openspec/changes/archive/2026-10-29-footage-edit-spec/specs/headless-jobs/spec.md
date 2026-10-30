# Spec Delta

## MODIFIED Requirements

### Requirement: Fixed operation list

The runner SHALL accept only operations from a fixed list:
- `inventory`, `transcribe`, `voice`, `matte`
- `storyboard` (`check`, `voice`, `sheet`, `stills`, `render`)
- `conform`, `pack`, `frames`, `face`
- `shortform` (`check`, `stills`, `render`)
- `cut` (`check`, `render`)
- `shortform.build`

Each operation SHALL validate its arguments against a schema before running anything. An unknown operation or argument SHALL be rejected without side effects.

#### Scenario: Unknown operation

- **WHEN** a job has `"op": "shell"`
- **THEN** the runner exits non-zero with `ok: false`, and no file is created or changed

#### Scenario: Unknown argument

- **WHEN** a `transcribe` job includes an argument the operation does not define
- **THEN** the runner rejects it before transcribing and names the argument in `error`

#### Scenario: New footage ops listed

- **WHEN** `tools/run_job.py --help` runs
- **THEN** its op list names `conform`, `pack`, `frames`, `face`, `shortform` and `cut` with their arguments

## ADDED Requirements

### Requirement: Footage ops run only data

Except for `shortform.build`, no operation SHALL execute code or command text taken from a job, a spec or an EDL. `shortform.build` SHALL stay documented as trusted input only. Every other footage op SHALL be safe to run on a spec written by an untrusted user.

#### Scenario: Short from data

- **WHEN** a project has `edit/short.json` and an `edit/build.py` that would write a marker file, and a `shortform` job with `cmd: render` runs
- **THEN** the short renders from `short.json` and the marker file is not created

### Requirement: Validated cut

The `cut` op SHALL render a plain EDL (sources, ranges, grade, optional overlays and subtitles) at the sources' orientation, through the video-use renderer. Before rendering, it SHALL reject:
- source and overlay paths outside the project
- a grade that isn't a named preset, `auto` or `none`
- unknown fields
- ranges outside a source's duration
- an output longer than 3 hours

#### Scenario: Raw filter in grade

- **WHEN** an EDL's grade is `"eq=contrast=1.1,movie=/etc/passwd"`
- **THEN** `cut check` rejects it, naming the allowed grades, and ffmpeg is never started

#### Scenario: Absolute source path

- **WHEN** an EDL source is `/Users/someone/private.mov`
- **THEN** the job is rejected as outside the project

#### Scenario: Plain cut renders

- **WHEN** a valid EDL with three ranges from a 1920x1080 conformed take runs through `cut render` with preview off
- **THEN** the output is 1920x1080, its duration equals the sum of the ranges (±1 frame per range), and the result reports its integrated loudness

### Requirement: Footage op outputs

`conform`, `frames`, `pack`, `face`, `shortform` and `cut` SHALL report their written files in `outputs`. Ops that measure something SHALL also return it as fields in the result, so a caller needn't parse files:
- `face`: the suggested centre and confidence per take
- `shortform check` and `cut check`: errors, warnings and planned duration
- renders: loudness and true peak

#### Scenario: Check result fields

- **WHEN** a `shortform` job with `cmd: check` runs on a valid spec
- **THEN** the result JSON has `ok: true`, `errors: []`, a `warnings` list and a `duration` in seconds
