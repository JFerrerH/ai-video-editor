## ADDED Requirements

### Requirement: Nothing after the last kept word is unexpected speech

The check SHALL NOT report as unexpected speech a heard word that comes after every word the edit keeps, because the render ends the last clip's audio before the next source word's onset (the end tail), so nothing from outside the edit can sound there. Heard words inside the edit SHALL be checked as before.

#### Scenario: A word Whisper adds after the last word

- **WHEN** the transcription of a preview adds a word after the edit's last word, with the heard and expected words otherwise equal
- **THEN** no `unexpected_speech` fault is reported for it

#### Scenario: A stumble inside the edit

- **WHEN** a word the edit doesn't contain is heard between two kept words
- **THEN** `unexpected_speech` is reported for it, as before
