# voice-generation Specification

## Purpose

Turn script lines into narration audio on this machine with commercially licensed open-weight
models: one reproducible, cached clip per line, with the language and voice checked before anything
is synthesised.

## Requirements

### Requirement: Local text-to-speech

The system SHALL synthesise a mono WAV (24 kHz or higher) from text, a language code and a voice
preset using only locally run, commercially licensed weights. Leading and trailing silence SHALL be
trimmed to at most 50 ms. No network call SHALL be made except to download weights that are not yet
cached.

#### Scenario: One line

- **WHEN** the text "Every scene starts with one clear idea." is synthesised in `en` with the default voice
- **THEN** a WAV is written whose duration is between 1.0 s and 4.0 s, with ≤ 50 ms of silence (below -50 dBFS) at each end

#### Scenario: Speed

- **WHEN** the same line is synthesised with speed 1.5 instead of 1.0
- **THEN** the clip is at least 20% shorter (Kokoro's speed is not linear: 1.2 gives only ~8–10%)

### Requirement: Language and voice validation

The system SHALL reject a language the model does not support, and a voice preset that does not
belong to the requested language. It SHALL do so before loading the model, naming the supported
languages or that language's voices.

#### Scenario: Unsupported language

- **WHEN** a line is requested in `de`
- **THEN** the command exits non-zero, lists the supported language codes, and writes no file

#### Scenario: Voice from another language

- **WHEN** a Spanish line is requested with an English-only voice preset
- **THEN** the command exits non-zero and lists the Spanish voice presets

### Requirement: Reproducible record and cache

Every clip SHALL have a sidecar JSON recording text, language, voice, speed, model id, duration and
seconds taken. A request whose output exists with a matching sidecar (text, language, voice, speed,
model) SHALL be skipped. Any difference, or `--force`, SHALL re-synthesise.

#### Scenario: Unchanged re-run

- **WHEN** the same line is requested twice with identical inputs
- **THEN** the second run reports it as cached and the WAV's modification time does not change

#### Scenario: Edited text

- **WHEN** the text of an existing clip changes by one word
- **THEN** the clip is re-synthesised and the sidecar records the new text

### Requirement: Licence-safe models

The system SHALL use only weights whose licence permits commercial use and SHALL name the model id
and licence in its help output. Non-commercial weights SHALL NOT be selectable.

#### Scenario: Help names the model

- **WHEN** a user runs the voice tool with `--help`
- **THEN** the output names the model id and its licence (Apache-2.0) and lists the supported languages

### Requirement: Optional install

The voice dependencies SHALL install separately from the default workspace install. Without them, or
without the phonemiser a language needs, the tool SHALL exit with the exact install command instead
of a traceback.

#### Scenario: Group not installed

- **WHEN** a line is requested in an environment without the generation dependencies
- **THEN** the command exits non-zero and prints `uv sync --group gen`

#### Scenario: Phonemiser missing

- **WHEN** a Spanish line is requested and the bundled `espeak-ng` phonemiser library can't be found
- **THEN** the command exits non-zero and prints `uv sync --group gen`
