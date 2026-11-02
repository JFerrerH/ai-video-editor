# Spec Delta

## ADDED Requirements

### Requirement: Preview overlay at preview size
A preview render SHALL draw the Remotion overlay, and every behind-the-speaker layer, at the preview size (720x1280) so no overlay layer is scaled before compositing. A final render SHALL draw them at 1080x1920.

#### Scenario: Preview overlay size
- **WHEN** `uv run tools/shortform.py render <spec> --preview` runs on a spec with overlay events
- **THEN** the overlay file it writes measures 720x1280 in `ffprobe`, and the preview MP4 measures 720x1280

#### Scenario: Behind-the-speaker layer size
- **WHEN** a preview renders a spec with an event whose `props.behind` is true
- **THEN** that event's layer file measures 720x1280 in `ffprobe`

#### Scenario: Final overlay unchanged
- **WHEN** `uv run tools/shortform.py render <spec>` runs without `--preview`
- **THEN** the overlay file it writes measures 1080x1920, and the final MP4 measures 1080x1920 at -14 LUFS (±0.5)

### Requirement: Overlay reuse stays within one size
A render that reuses an existing overlay or behind-the-speaker layer (`skip_overlay`) SHALL reuse only a file drawn at its own output size. With no file at that size, it SHALL render one.

#### Scenario: Final after a preview
- **WHEN** a preview has rendered, and then a final runs with `skip_overlay`
- **THEN** the final renders a new 1080x1920 overlay instead of using the 720x1280 one, and the preview's overlay file is left in place

#### Scenario: Preview after a final
- **WHEN** a final has rendered, and then a preview runs with `skip_overlay`
- **THEN** the preview renders a 720x1280 overlay instead of scaling down the 1080x1920 one

#### Scenario: Reuse at the same size
- **WHEN** a preview runs with `skip_overlay` after an earlier preview of the same spec
- **THEN** no Remotion render runs for the overlay, and the earlier 720x1280 overlay file is used
