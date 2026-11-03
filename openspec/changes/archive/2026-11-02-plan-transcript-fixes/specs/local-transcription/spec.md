## MODIFIED Requirements

### Requirement: Restarts are marked

A restart SHALL be marked when both of these hold:
- a phrase ends abandoned: its last word carries an ellipsis, or is followed by a pause of at least 0.3 s without sentence-ending punctuation;
- within 6 s after it, and with at most 2 words between, the same first two or more words (case and punctuation ignored) start again.

#### Scenario: Restart detected

- **WHEN** a transcript reads "the first would be to drop the fear of… the first would be to remove the fear"
- **THEN** `restarts` has one entry whose `abandoned` covers "the first would be to drop the fear of…" and whose `again` is the start of the second "the"

#### Scenario: Filler before the repeat

- **WHEN** a transcript reads "the first would be… uh no the first would be to remove the fear"
- **THEN** `restarts` has one entry

#### Scenario: Deliberate repetition isn't a restart

- **WHEN** a transcript reads "I spend this much on food. I spend this much on rent."
- **THEN** `restarts` is empty, because the first phrase ends a sentence

#### Scenario: Two sentences that open alike aren't a restart

- **WHEN** a transcript reads "And in that thesis I wrote about a closet, with a pause after the comma, to organise my clothes. And in spite of it I gave up."
- **THEN** `restarts` is empty, because the speaker went on between them

### Requirement: Untranscribed speech is reported

Speech runs that are still without words after the retry, and whose level is within 12 dB of the take's speech (90th percentile of each), SHALL be listed in the JSON as `untranscribed: [[from, to], …]` (empty list when none), and printed as a warning naming each range.

#### Scenario: Unintelligible run

- **WHEN** a take contains 3 s of noise above the speech threshold that Whisper returns no words for, twice
- **THEN** `untranscribed` lists that range and the command prints a warning naming it, and still exits 0

#### Scenario: A breath in a pause

- **WHEN** a stretch with no words sits 16 dB under the take's speech, and well above the room's floor
- **THEN** `untranscribed` doesn't list it
