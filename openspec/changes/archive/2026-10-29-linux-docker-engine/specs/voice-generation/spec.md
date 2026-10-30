# Spec Delta

## ADDED Requirements

### Requirement: Portable backend

The system SHALL synthesise on Linux as well as on Apple Silicon, using the same Kokoro-82M voices, languages, dialects, pauses and trimming, choosing the backend at runtime. The sidecar SHALL record the backend, and a clip made by a different backend SHALL be re-synthesised rather than reused.

#### Scenario: Linux line

- **WHEN** "Every scene starts with one clear idea." is synthesised in `en` with the default voice on Linux
- **THEN** a mono WAV of 24 kHz or more is written, its duration is between 1.0 s and 4.0 s, and the sidecar names the portable backend

#### Scenario: Clip from the other backend

- **WHEN** a clip made on a Mac is requested again with identical inputs on Linux
- **THEN** it is re-synthesised (not reported as cached) and the sidecar names the Linux backend

#### Scenario: Install hint on Linux

- **WHEN** a line is requested on Linux without the generation dependencies
- **THEN** the command exits non-zero and prints `uv sync --group gen`
