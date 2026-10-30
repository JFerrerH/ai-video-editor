# Spec Delta

## Purpose

Run one engine operation from a JSON job description and get a machine-readable JSON result, so workflows can be driven by another program (a queue worker, CI, a script) without a person typing commands.

## ADDED Requirements

### Requirement: Job in, result out

The runner SHALL read one job (JSON from a file path or stdin) with `op`, `project` and `args`, run it, and print exactly one JSON result on stdout with `ok`, `op`, `outputs` (paths relative to the project), `seconds` and, on failure, `error`. Progress logs SHALL go to stderr only.

#### Scenario: Successful job

- **WHEN** a job `{"op": "inventory", "project": "demo", "args": {}}` runs on a project with one source clip
- **THEN** the runner exits 0, stdout parses as JSON with `ok: true`, and `outputs` lists the written inventory file

#### Scenario: Failed job

- **WHEN** a job references a source file that does not exist
- **THEN** the runner exits non-zero and stdout parses as JSON with `ok: false` and a one-line `error`, with no traceback on stdout

### Requirement: Fixed operation list

The runner SHALL accept only operations from a fixed list: `inventory`, `transcribe`, `voice`, `storyboard` (`check`, `voice`, `sheet`, `stills`, `render`), `matte` and `shortform.build`. Each operation SHALL validate its arguments against a schema before running anything. An unknown operation or argument SHALL be rejected without side effects.

#### Scenario: Unknown operation

- **WHEN** a job has `"op": "shell"`
- **THEN** the runner exits non-zero with `ok: false`, and no file is created or changed

#### Scenario: Unknown argument

- **WHEN** a `transcribe` job includes an argument the operation does not define
- **THEN** the runner rejects it before transcribing and names the argument in `error`

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
