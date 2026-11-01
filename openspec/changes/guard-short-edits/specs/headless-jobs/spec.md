# Spec Delta

## ADDED Requirements

### Requirement: Schema op

The runner SHALL provide a `schema` operation that returns the overlay props schemas (every component plus the shared event props) in the result's `schema` field. It SHALL need no project, read no footage and write no files. The same document SHALL ship in the container image at a fixed path.

#### Scenario: Schema job

- **WHEN** a job `{"op": "schema", "args": {}}` runs
- **THEN** the runner exits 0, `ok` is true, `outputs` is empty, and `schema` has a key for `KineticType`, `ListScene` and `StatScene`

#### Scenario: Schema in the image

- **WHEN** the container's self-check runs
- **THEN** it reports the schema file present at its fixed path with one entry per registered component

## MODIFIED Requirements

### Requirement: Fixed operation list

The runner SHALL accept only operations from a fixed list:
- `inventory`, `transcribe`, `voice`, `matte`
- `storyboard` (`check`, `voice`, `sheet`, `stills`, `render`)
- `conform`, `pack`, `frames`, `face`
- `shortform` (`check`, `stills`, `render`)
- `cut` (`check`, `render`)
- `site`
- `brand` (`check`)
- `schema`
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

#### Scenario: Schema op listed

- **WHEN** `tools/run_job.py --help` runs
- **THEN** its op list names `schema`

#### Scenario: Non-http URL

- **WHEN** a `site` job has `"url": "file:///etc/passwd"`
- **THEN** the runner exits 2 with an error naming the scheme, and nothing is fetched or written

### Requirement: Footage op outputs

`conform`, `frames`, `pack`, `face`, `shortform`, `cut`, `site` and `brand` SHALL report their written files in `outputs`. Ops that measure something SHALL also return it as fields in the result, so a caller needn't parse files:
- `face`: the suggested centre and confidence per take
- `shortform check` and `cut check`: errors, warnings and planned duration
- `shortform stills`: warnings (legibility and caption placement) and one entry per still with its time and, for event stills, the event index and type
- `transcribe`: `language_detected` (when detected), `patched` and `untranscribed` per take
- renders: loudness and true peak
- `site`: final URL, title, colours, fonts, image candidates and the blocked count
- `brand check`: one entry per checked file and the kit errors

#### Scenario: Check result fields

- **WHEN** a `shortform` job with `cmd: check` runs on a valid spec
- **THEN** the result JSON has `ok: true`, `errors: []`, a `warnings` list and a `duration` in seconds

#### Scenario: Brand check result fields

- **WHEN** a `brand` job with `cmd: check` runs on a directory with one valid font and no `brand.json`
- **THEN** the result JSON has `ok: true`, a `files` list with one `valid` entry naming its family, `errors: []`, and `outputs` includes the stored font

#### Scenario: Stills result fields

- **WHEN** a `shortform` job with `cmd: stills` runs on a spec with 2 segments and 1 event
- **THEN** the result has 3 `stills` entries, one with `event: 0` and its type, and a `warnings` list

#### Scenario: Transcribe result fields

- **WHEN** a `transcribe` job runs on a take with one unintelligible speech run
- **THEN** the result has `ok: true` and `untranscribed` lists that range for the take
