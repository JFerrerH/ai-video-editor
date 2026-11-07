## MODIFIED Requirements

### Requirement: Implausible words are detected

After transcription, a word SHALL be treated as implausible when it lasts longer than `max(1.0, 0.12 × letters + 0.4)` seconds and either speech runs through at least 60% of it, or at least 0.6 s of speech inside it is covered by no word (a word covers at most its first 1.5 s).

#### Scenario: Long word that is real

- **WHEN** a word lasts 1.1 s and has 9 letters (limit 1.48 s)
- **THEN** it is kept and nothing is re-transcribed for it

#### Scenario: Word stretched over a pause and a retake

- **WHEN** a 3-letter word lasts 4.3 s, its first 2.3 s are silence and speech runs through its last 2 s
- **THEN** it is implausible, though speech fills under 60% of it

#### Scenario: Long word over silence

- **WHEN** a word lasts 3 s and the audio under it is silent after its first 0.3 s
- **THEN** it is not implausible and nothing is re-transcribed for it

### Requirement: Implausible words are re-transcribed

Each implausible word's window (its start to its end, with the usual padding) SHALL be transcribed again on its own. Words that come back and are not a listed hallucination SHALL replace the implausible word, with times kept non-decreasing, and the patch SHALL be recorded in `source.patched` with `"replaced": "<word>"`. A recovered word whose start sits in silence SHALL start at the next speech. When the retry fails, the window SHALL be listed in `untranscribed`.

#### Scenario: Folded false start

- **WHEN** a backend result has one word "remove" spanning 38.68–42.34 over continuous speech, and the retry of that window returns "the first would be to drop the fear of… the first would be"
- **THEN** the written JSON has those words in 38.68–42.34 instead of the single long word, and `source.patched` has an entry with `"replaced": "remove"`

#### Scenario: Retry hears nothing

- **WHEN** the retry of an implausible word's window returns no words
- **THEN** that window is listed in `untranscribed`

#### Scenario: Recovered word stamped in the pause

- **WHEN** a retry returns its first word from 50.0 to 52.6, and the audio is silent until speech starts at 52.3
- **THEN** that word starts at 52.3 in the written JSON, so the pause before it stays a pause

### Requirement: Restarts are marked

A restart SHALL be marked when both of these hold:
- a phrase ends abandoned: its last word carries an ellipsis, or is followed by a pause of at least 0.3 s without sentence-ending punctuation;
- within 6 s after it, and with at most 2 words between, the same first two or more words (case and punctuation ignored) start again.

The abandoned phrase SHALL start at the nearest earlier place where those two words open a phrase, with no sentence end between. Pauses of under 0.8 s inside the phrase SHALL NOT end it. A phrase that crosses a pause SHALL be marked only when the repeat runs three words, or the speaker waited 1 s or more before it (two words could be a list). The 6 s limit counts from the phrase's end.

#### Scenario: Restart detected

- **WHEN** a transcript reads "the first would be to drop the fear of… the first would be to remove the fear"
- **THEN** `restarts` has one entry whose `abandoned` covers "the first would be to drop the fear of…" and whose `again` is the start of the second "the"

#### Scenario: Filler before the repeat

- **WHEN** a transcript reads "the first would be… uh no the first would be to remove the fear"
- **THEN** `restarts` has one entry

#### Scenario: Pause inside the abandoned phrase

- **WHEN** a transcript reads "anyway I wonder, have you ever been" with a 0.5 s pause after the comma, then a 2 s pause, then "anyway I wonder, have you ever been the youngest here?"
- **THEN** `restarts` has one entry whose `abandoned` starts at the first "anyway" and ends at the first "been", and whose `again` is the start of the second "anyway"

#### Scenario: Deliberate repetition isn't a restart

- **WHEN** a transcript reads "I spend this much on food. I spend this much on rent."
- **THEN** `restarts` is empty, because the first phrase ends a sentence

#### Scenario: Two sentences that open alike aren't a restart

- **WHEN** a transcript reads "And in that thesis I wrote about a closet, with a pause after the comma, to organise my clothes. And in spite of it I gave up."
- **THEN** `restarts` is empty, because the speaker went on between them

## ADDED Requirements

### Requirement: Sentence breaks are listed

The transcript JSON SHALL list `breaks: [t, …]`, sorted and without repeats (empty list when none): the first word's start of each restart's `abandoned` range, each restart's `again`, and, for each `untranscribed` range, the start of the first word after it and of the first word inside or after its start.

#### Scenario: Breaks around a false start

- **WHEN** a transcript marks a restart with `abandoned` [93.5, 96.5] and `again` 98.7
- **THEN** `breaks` holds 93.5 and 98.7

#### Scenario: Breaks around a hole

- **WHEN** `untranscribed` lists [52.1, 53.0], and the next word starts at 53.1
- **THEN** `breaks` holds 53.1

#### Scenario: Nothing to break

- **WHEN** a transcript has no restarts and nothing untranscribed
- **THEN** `breaks` is an empty list
