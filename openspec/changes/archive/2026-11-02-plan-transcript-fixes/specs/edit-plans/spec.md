## MODIFIED Requirements

### Requirement: Numbered sentences

`plan ids <project>` SHALL print the project's transcript as numbered sentences `F1…Fn`. Each SHALL show its take, start, duration and text, and SHALL be flagged when it is the abandoned half of a likely restart. Takes SHALL be numbered in the given `order` (any others after them), else in name order. IDs SHALL be the same for the same transcript and order.

#### Scenario: Restart flagged

- **WHEN** a take says "En esa tesis… en esa tesis hablaba de crear" with a 0.5 s pause after the first "tesis"
- **THEN** the abandoned sentence is printed with a restart flag and the next sentence starts at the second "En"

#### Scenario: Sentences that open alike

- **WHEN** a sentence is followed after a pause by a whole other sentence, and then by one with the same first two words
- **THEN** no sentence is flagged

#### Scenario: Take order

- **WHEN** `order` is `["zeta", "alfa"]`
- **THEN** F1 is the first sentence of `zeta`, in `plan_ids` and in `plan_build`

## ADDED Requirements

### Requirement: Caption fixes in a plan

A plan MAY have `captions: {"fixes": {"heard": "said"}}`, which the compiled spec SHALL carry. Anything else under `captions` SHALL be an error, because the other caption fields use seconds.

#### Scenario: Misheard brand

- **WHEN** a plan has `captions: {"fixes": {"Akme": "Acme"}}`
- **THEN** `edit/short.json` has those fixes under `captions`

#### Scenario: Seconds in a caption fix

- **WHEN** a plan has `captions: {"word_fixes": [{"at": 12.4, "text": "x"}]}`
- **THEN** `plan build` exits non-zero naming `plan.captions`
