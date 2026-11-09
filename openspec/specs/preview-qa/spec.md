# preview-qa Specification

## Purpose
A rendered preview is listened to, not only checked: its words and the sound at every cut are compared with what the edit says it plays, so a clipped word, a stumble the transcript hid or a cut through speech is reported with its time and fix.

## Requirements

### Requirement: The preview plays the words of the edit

`preview_qa <project>` SHALL transcribe `edit/preview.mp4` and compare it with the words the edit plays. Each source word SHALL be owned by the segment that covers most of it. Words of three letters or fewer SHALL not count as unexpected speech, and a replaced run with the same letters as the expected one (a word heard as two) SHALL not either. It SHALL report:
- a clipped word at a cut;
- heard words the edit doesn't contain: at least one of more than three letters, unless the run is the expected word heard differently (split in two, or another ending);
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

### Requirement: Nothing after the last kept word is unexpected speech

The check SHALL NOT report as unexpected speech a heard word that comes after every word the edit keeps, because the render ends the last clip's audio before the next source word's onset (the end tail), so nothing from outside the edit can sound there. Heard words inside the edit SHALL be checked as before.

#### Scenario: A word Whisper adds after the last word

- **WHEN** the transcription of a preview adds a word after the edit's last word, with the heard and expected words otherwise equal
- **THEN** no `unexpected_speech` fault is reported for it

#### Scenario: A stumble inside the edit

- **WHEN** a word the edit doesn't contain is heard between two kept words
- **THEN** `unexpected_speech` is reported for it, as before
