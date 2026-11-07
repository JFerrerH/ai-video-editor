## MODIFIED Requirements

### Requirement: Numbered sentences

`plan ids <project>` SHALL print the project's transcript as numbered sentences `F1…Fn`. Each SHALL show its take, start, duration and text, and SHALL be flagged when it is the abandoned half of a likely restart. A sentence SHALL also end before a word that starts at one of the transcript's `breaks`. A transcript with no `breaks` field SHALL be numbered as if the list were empty. Takes SHALL be numbered in the given `order` (any others after them), else in name order. IDs SHALL be the same for the same transcript and order.

#### Scenario: Restart flagged

- **WHEN** a take says "En esa tesis… en esa tesis hablaba de crear" with a 0.5 s pause after the first "tesis"
- **THEN** the abandoned sentence is printed with a restart flag and the next sentence starts at the second "En"

#### Scenario: Sentences that open alike

- **WHEN** a sentence is followed after a pause by a whole other sentence, and then by one with the same first two words
- **THEN** no sentence is flagged

#### Scenario: Take order

- **WHEN** `order` is `["zeta", "alfa"]`
- **THEN** F1 is the first sentence of `zeta`, in `plan_ids` and in `plan_build`

#### Scenario: False start after an unpunctuated line

- **WHEN** a take says "I kept it in a drawer for years" and, 0.7 s later with no punctuation, a phrase it abandons and says again, and `breaks` holds the phrase's start and the restart
- **THEN** the drawer line, the abandoned phrase and the restart are three sentences, only the abandoned one is flagged, and a plan can keep the other two

#### Scenario: Transcript from before breaks

- **WHEN** a transcript has no `breaks` field
- **THEN** its sentence IDs are the same as before this change

## ADDED Requirements

### Requirement: Kept speech with no words names a plan fix

When `plan_build` is refused because a kept run holds a range of `untranscribed` speech, the error SHALL name the sentences on either side of that range and say to leave one out of `keep`. It SHALL NOT ask for listening or for a cut a plan can't express. When the range sits inside one sentence (a transcript with no `breaks`), the error SHALL say to run the footage's preparation again.

#### Scenario: Hole between two sentences

- **WHEN** a plan keeps F7 and F8 and an `untranscribed` range sits between them
- **THEN** the build is refused with an error naming F7, F8 and the range, saying to leave F7 or F8 out of `keep`, and keeping only F7 passes that check

#### Scenario: Hole inside a sentence of an older transcript

- **WHEN** a plan keeps F7, the transcript has no `breaks`, and an `untranscribed` range sits inside F7
- **THEN** the error names F7 and the range and says to prepare the footage again
