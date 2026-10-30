# Spec Delta

## MODIFIED Requirements

### Requirement: Toolchain present

The image SHALL provide Python 3.12 with the workspace's dependencies (including the voice and matte groups), ffmpeg/ffprobe with the `subtitles`, `ass` and `drawtext` filters, Node with the Remotion project's dependencies and a headless browser Remotion can render with, a headless browser the `site` capture can drive, auto-editor, and the video-use helpers.

#### Scenario: Self-check

- **WHEN** the image's self-check command runs
- **THEN** it reports each item (python, ffmpeg filters, node, remotion browser, capture browser, auto-editor, video-use helpers, transcription backend, voice backend, matte backend) as ok and exits 0

#### Scenario: Capture browser actually starts

- **WHEN** the self-check runs in the image
- **THEN** the `capture browser` item is ok only after the browser has launched, opened a blank page and closed
