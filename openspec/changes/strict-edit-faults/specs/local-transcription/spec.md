## ADDED Requirements

### Requirement: Implausible words are re-transcribed

After transcription, a word SHALL be treated as implausible when it lasts longer than `max(1.0, 0.12 × letters + 0.4)` seconds and speech runs through at least 60% of it. Each implausible word's window (its start to its end, with the usual padding) SHALL be transcribed again on its own. When the retry returns words that are not a listed hallucination, they SHALL replace the implausible word, and their times SHALL be kept non-decreasing. The patch SHALL be recorded in `source.patched` with `"replaced": "<word>"`. When the retry fails, the window SHALL be listed in `untranscribed`.

#### Scenario: Folded false start

- **WHEN** a backend result has one word "remove" spanning 38.68–42.34 over continuous speech, and the retry of that window returns "the first would be to drop the fear of… the first would be"
- **THEN** the written JSON has those words in 38.68–42.34 instead of the single long word, and `source.patched` has an entry with `"replaced": "remove"`

#### Scenario: Long word that is real

- **WHEN** a word lasts 1.1 s and has 9 letters (limit 1.48 s)
- **THEN** it is kept and nothing is re-transcribed for it

### Requirement: Restarts are marked

The transcript JSON SHALL list likely false starts as `restarts: [{"abandoned": [from, to], "again": t, "words": "<abandoned text>"}]` (empty list when none). A restart SHALL be marked when both of these hold:
- a phrase ends abandoned: its last word carries an ellipsis, or is followed by a pause of at least 0.3 s without sentence-ending punctuation;
- within 6 s after it, the same first two or more words (case and punctuation ignored) start again.

The packed transcript SHALL show each marked restart inline.

#### Scenario: Restart detected

- **WHEN** a transcript reads "the first would be to drop the fear of… the first would be to remove the fear"
- **THEN** `restarts` has one entry whose `abandoned` covers "the first would be to drop the fear of…" and whose `again` is the start of the second "the"

#### Scenario: Deliberate repetition isn't a restart

- **WHEN** a transcript reads "I spend this much on food. I spend this much on rent."
- **THEN** `restarts` is empty, because the first phrase ends a sentence

## MODIFIED Requirements

### Requirement: Speech with no words is re-transcribed

After transcription, the system SHALL find speech from the audio's RMS envelope (the same speech/silence measure the short-form edge refinement uses). Each stretch of at least 0.6 s of speech that no word covers (a word covers at most its first 1.5 s) SHALL be transcribed again on its own (0.5 s padding, same language, no prompt), and its words merged in time order. Each patch SHALL be recorded in `source.patched` as `{"from", "to", "words"}`.

#### Scenario: Hole filled

- **WHEN** a transcription returns no words for 0–30 s of a take that has speech there (simulated in a test by removing those words from a backend result)
- **THEN** the written JSON has words in 0–30 s, word times are still non-decreasing, spacing entries are rebuilt, and `source.patched` has an entry covering that window with its word count

#### Scenario: Stray words don't hide a hole

- **WHEN** a backend result has three words in the first second and none until 32 s, while speech runs throughout
- **THEN** the stretch from about 1 s to 32 s is re-transcribed and recorded in `source.patched`

#### Scenario: Short hole

- **WHEN** 0.8 s of speech between two words has no word
- **THEN** that stretch is re-transcribed, and if nothing comes back it is listed in `untranscribed`
