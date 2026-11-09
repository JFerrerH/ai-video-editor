## ADDED Requirements

### Requirement: Captions clear an event's drawn content

When captions move to clear a graphic, the band SHALL clear the event's drawn content box (its card and shapes), not only its text. A band that overlaps it SHALL NOT be used.

#### Scenario: Caption on a card's edge

- **WHEN** a drawer's card ends 20 px below where captions would start
- **THEN** the captions move clear of the card, or a `captions_on_text` finding names the event

### Requirement: Placement never moves a card below the chin

When the engine places a floating card to clear the head, it SHALL place it above the head or refuse it with the fix (`"full": true`, fewer words, or a `corner` or `side` move); it SHALL NOT place it over the speaker's body below the chin. A component that owns its place low in the frame (a drawer) is a device the plan chose and is not moved.

#### Scenario: No room above the head

- **WHEN** a floating card doesn't fit above a close-up's head at a readable size
- **THEN** the build refuses it with the fix, and no placement puts its content below the head box
