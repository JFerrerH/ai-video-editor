## ADDED Requirements

### Requirement: The low look

A segment MAY have `look: "low"`. Its picture SHALL be black and white with added contrast, and it MAY have `freeze` (0.3–0.5 s) of its last frame. The segment's voice SHALL be band-limited, keeping roughly 220 Hz to 2.4 kHz (so the consonants stay audible), with a light short echo and level make-up. A `low` segment SHALL be 1.0–3.0 s long and have a static zoom. A spec SHALL have at most one `low` segment.

#### Scenario: One short low line

- **WHEN** one 2.1 s segment has `look: "low"` and `freeze: 0.4`
- **THEN** that span of the preview is greyscale, holds its last frame for 0.4 s, and its words are recognised by re-transcription

#### Scenario: Two low segments

- **WHEN** two segments have `look: "low"`
- **THEN** `check` exits non-zero saying the low look is used at most once
