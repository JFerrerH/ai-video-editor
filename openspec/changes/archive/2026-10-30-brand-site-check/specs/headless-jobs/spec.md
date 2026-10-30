# Spec Delta

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
