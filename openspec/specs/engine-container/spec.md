# engine-container Specification

## Purpose

One Docker image that runs the engine's tools on Linux (CPU only) with every system dependency they need, so the same workflows work on a server, in CI or on any machine with Docker.

## Requirements

### Requirement: Image builds from the repo

The repository SHALL contain a Dockerfile that builds the image from a clean checkout with `docker build`, for `linux/amd64` and `linux/arm64`, without any file that is gitignored (brand kits, footage, keys).

#### Scenario: Clean build

- **WHEN** `docker build -t engine .` runs on a fresh clone
- **THEN** the build exits 0 and the build context excludes `footage/`, `brands/*` (except `_template`), `exports/` and any `.env`

### Requirement: Toolchain present

The image SHALL provide Python 3.12 with the workspace's dependencies (including the voice and matte groups), ffmpeg/ffprobe with the `subtitles`, `ass` and `drawtext` filters, Node with the Remotion project's dependencies and a headless browser Remotion can render with, a headless browser the `site` capture can drive, auto-editor, and the video-use helpers.

#### Scenario: Self-check

- **WHEN** the image's self-check command runs
- **THEN** it reports each item (python, ffmpeg filters, node, remotion browser, capture browser, auto-editor, video-use helpers, transcription backend, voice backend, matte backend) as ok and exits 0

#### Scenario: Capture browser actually starts

- **WHEN** the self-check runs in the image
- **THEN** the `capture browser` item is ok only after the browser has launched, opened a blank page and closed

### Requirement: Offline start

By default the image SHALL contain the transcription, voice and matte model weights, so a container can run every local tool with networking disabled. A build argument SHALL allow building without weights (downloaded on first use instead).

#### Scenario: No network

- **WHEN** a container of the default image runs with `--network none` and transcribes a clip, synthesises one voice line and renders one storyboard still
- **THEN** all three succeed

### Requirement: Work directories mounted, not baked

Projects, brand kits, licensed music and exports SHALL be read from and written to mounted directories at the repo's usual paths (`footage/`, `brands/`, `assets/music/`, `exports/`); nothing a user produces SHALL be stored only inside the container.

#### Scenario: Output survives the container

- **WHEN** a job writes a preview under a mounted `footage/<project>/edit/` and the container is removed
- **THEN** the preview file exists on the host

### Requirement: No secrets in the image

The image SHALL contain no API keys or `.env` files; keys for opt-in paid tools SHALL be supplied only at run time as environment variables or a mounted file.

#### Scenario: Image inspection

- **WHEN** the image's filesystem is searched for `.env` files and for the key variable names used by the paid tools
- **THEN** no file containing a key value is found
