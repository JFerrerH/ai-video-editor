## ADDED Requirements

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
