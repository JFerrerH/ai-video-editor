# headless-jobs Specification

## Purpose

Run one engine operation from a JSON job description and get a machine-readable JSON result, so workflows can be driven by another program (a queue worker, CI, a script) without a person typing commands.

## Requirements

### Requirement: Job in, result out

The runner SHALL read one job (JSON from a file path or stdin) with `op`, `project` and `args`, run it, and print exactly one JSON result on stdout with `ok`, `op`, `outputs` (paths relative to the project), `seconds` and, on failure, `error`. Progress logs SHALL go to stderr only.

#### Scenario: Successful job

- **WHEN** a job `{"op": "inventory", "project": "demo", "args": {}}` runs on a project with one source clip
- **THEN** the runner exits 0, stdout parses as JSON with `ok: true`, and `outputs` lists the written inventory file

#### Scenario: Failed job

- **WHEN** a job references a source file that does not exist
- **THEN** the runner exits non-zero and stdout parses as JSON with `ok: false` and a one-line `error`, with no traceback on stdout

### Requirement: Fixed operation list

The runner SHALL accept only operations from a fixed list:
- `inventory`, `transcribe`, `voice`, `matte`
- `storyboard` (`check`, `voice`, `sheet`, `stills`, `render`)
- `conform`, `pack`, `frames`, `face`
- `shortform` (`check`, `stills`, `render`)
- `cut` (`check`, `render`)
- `site`
- `brand` (`check`)
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

#### Scenario: Brand ops listed

- **WHEN** `tools/run_job.py --help` runs
- **THEN** its op list names `site` and `brand` with their arguments

#### Scenario: Non-http URL

- **WHEN** a `site` job has `"url": "file:///etc/passwd"`
- **THEN** the runner exits 2 with an error naming the scheme, and nothing is fetched or written

### Requirement: Paths confined to the project

Every path in a job SHALL resolve, after following symlinks, inside `footage/<project>/` (inputs and outputs) or the read-only shared assets; any other path SHALL be rejected. The project name SHALL be kebab-case ASCII.

#### Scenario: Escaping path

- **WHEN** a job passes `../../brands/x/brand.json` or an absolute path outside the project as a source
- **THEN** the runner rejects the job and nothing is read from that path

### Requirement: Same results as the CLI

An operation run through the runner SHALL produce the same files as the equivalent CLI command on the same inputs.

#### Scenario: Storyboard stills

- **WHEN** `storyboard stills` runs once through the runner and once through `tools/storyboard.py` on the same project
- **THEN** both write the same set of still file names with the same pixel dimensions

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

`conform`, `frames`, `pack`, `face`, `shortform`, `cut`, `site` and `brand` SHALL report their written files in `outputs`. Ops that measure something SHALL also return it as fields in the result, so a caller needn't parse files:
- `face`: the suggested centre and confidence per take
- `shortform check` and `cut check`: errors, warnings and planned duration
- renders: loudness and true peak
- `site`: final URL, title, colours, fonts, image candidates and the blocked count
- `brand check`: one entry per checked file and the kit errors

#### Scenario: Check result fields

- **WHEN** a `shortform` job with `cmd: check` runs on a valid spec
- **THEN** the result JSON has `ok: true`, `errors: []`, a `warnings` list and a `duration` in seconds

#### Scenario: Brand check result fields

- **WHEN** a `brand` job with `cmd: check` runs on a directory with one valid font and no `brand.json`
- **THEN** the result JSON has `ok: true`, a `files` list with one `valid` entry naming its family, `errors: []`, and `outputs` includes the stored font

### Requirement: Failures keep their cause
When an op fails with a multi-line message (for example a tool step that exits non-zero with its stderr attached), the runner SHALL write the whole message to stderr and SHALL set `error` to its most specific line: the last line naming an error, else the first line. Paths under the engine root SHALL appear relative in `error`.

#### Scenario: Remotion still fails
- **WHEN** a `shortform` stills job fails because `remotion still` exits non-zero with a `TypeError` in its output
- **THEN** stdout's `error` is the `TypeError` line, not the `FAILED: npx remotion …` command, and stderr holds the full Remotion output

#### Scenario: No engine paths
- **WHEN** the failing line contains an absolute path under the engine root (for example `/engine/footage/demo/edit/overlay_props.json`)
- **THEN** `error` shows it relative to the engine root (`footage/demo/edit/overlay_props.json`)

#### Scenario: One-line failure unchanged
- **WHEN** an op fails with a single-line message
- **THEN** `error` is that line, as before
