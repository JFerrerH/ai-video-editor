## MODIFIED Requirements

### Requirement: Captions keep clear of the head when they move

When captions move above or below a graphic to clear it, a band that clears both the graphic and the speaker's head box at that moment SHALL be preferred. If the only band that clears the graphic also crosses the head, the captions SHALL take it and a finding of kind `caption_head` (a warning, never an error in strict mode) SHALL name the event, the time and the head's span. If no band clears the graphic, the finding SHALL remain `captions_on_text`.

#### Scenario: Drawer at the bottom of a medium shot

- **WHEN** a drawer's card reaches the caption band and the only band above it crosses the speaker's eyes
- **THEN** the captions go to that band, `check --strict` reports a `caption_head` warning and no error for them, and the plan renders

#### Scenario: A band clears both

- **WHEN** a graphic reaches the caption band and a band below it clears the graphic and the head
- **THEN** the captions go there and no finding is reported
