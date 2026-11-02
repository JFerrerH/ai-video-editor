## ADDED Requirements

### Requirement: The preview plays the words of the edit

`preview_qa <project>` SHALL transcribe `edit/preview.mp4` and compare it with the words the edit plays. Each source word SHALL be owned by the segment that covers most of it. Words of three letters or fewer SHALL not count as unexpected speech. It SHALL report:
- a clipped word at a cut;
- three or more consecutive heard words the edit doesn't contain;
- a 3-word run played more often than the take says it;
- a heard restart.
Each report SHALL give the output time, the segment and the fix.

#### Scenario: Stumble the transcript hid

- **WHEN** the preview contains "conversemos" at 38.7 s and no kept source word matches it
- **THEN** `preview_qa` exits non-zero naming 38.7 s, the segment, and that speech is heard there that the edit doesn't contain

### Requirement: Cuts are quiet relative to the speech

`preview_qa` SHALL measure the energy at each cut of the preview audio against the take's speech level, using the real clip durations. A cut louder than −12 dB relative to speech SHALL be an error. A cut at the media start of a take SHALL count as clean.

#### Scenario: Locked cut mid-word

- **WHEN** a cut in the preview is −7.2 dB relative to speech
- **THEN** `preview_qa` exits non-zero naming the cut's output time and its level

#### Scenario: Good edit

- **WHEN** the approved launch plan is compiled and rendered
- **THEN** `preview_qa` exits 0
