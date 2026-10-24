# Spec Delta

## Purpose

Narrate script lines with a paid cloud TTS service (ElevenLabs) when the local voice is not good
enough, producing clips that drop into the same pipeline as local narration.

## ADDED Requirements

### Requirement: Same clip contract as local voice

The cloud voice tool SHALL write one mono WAV (48 kHz) per line, plus a sidecar JSON with the cache key
(text sent, voice id, model, settings), the duration and the provider. Its output SHALL be accepted by
the shot-cut tool exactly like local voice clips.

#### Scenario: One clip per shot line

- **WHEN** it runs on a shot list with 11 lines
- **THEN** 11 WAVs and 11 sidecar JSONs exist in the chosen narration folder, each WAV mono at 48 kHz

### Requirement: Cached clips

A line whose cache key matches its sidecar SHALL NOT be sent again. Changing the text, voice, model or
settings SHALL re-synthesise only the lines affected.

#### Scenario: Rerun after editing one line

- **WHEN** one of 11 lines is edited and the tool runs again
- **THEN** exactly one request is sent

### Requirement: Respellings

The tool SHALL apply a project's respelling map (for example a number to its words, or a name to how
it sounds) to the text sent, while the sidecar keeps the script text.

#### Scenario: Year spelled out

- **WHEN** the map has `"2030": "dos mil treinta"` and a line contains "2030"
- **THEN** the text sent contains "dos mil treinta" and the sidecar's script text still contains "2030"

### Requirement: Library voices and plan limits

Given a voice id that is not in the account, the tool SHALL add it from the shared voice library first.
If the provider refuses because of the plan, it SHALL stop with a message that names the limit and the
premade voices the account can use. No partial set of clips SHALL be left behind.

#### Scenario: Free plan and a library voice

- **WHEN** a shared-library voice is requested on a free plan
- **THEN** the tool exits naming "paid plan required" and listing the account's usable voice names, and the narration folder is unchanged

### Requirement: Commercial-licence warning

When the account's plan has no commercial licence, the tool SHALL print a warning on every run that
the clips are not cleared for commercial publication.

#### Scenario: Free plan warning

- **WHEN** the tool runs with a free-plan key
- **THEN** the output contains a warning that the free plan has no commercial licence

### Requirement: Character budget

Before synthesising, the tool SHALL print the characters to be sent and the account's remaining
monthly characters. It SHALL stop if the run would exceed them.

#### Scenario: Not enough characters

- **WHEN** 900 characters are pending and the account has 500 left
- **THEN** the tool exits before any request, naming both numbers
