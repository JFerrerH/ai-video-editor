## ADDED Requirements

### Requirement: Captions clear an event's drawn content

When captions move to clear a graphic, the band SHALL clear the event's drawn content box (its card and shapes), not only its text. A band that overlaps it SHALL NOT be used.

#### Scenario: Caption on a card's edge

- **WHEN** a drawer's card ends 20 px below where captions would start
- **THEN** the captions move clear of the card, or a `captions_on_text` finding names the event

### Requirement: No card on the speaker's chest

A floating graphic's drawn content SHALL NOT sit over the speaker's body below the chin (from the head box's bottom down, across the shoulders). The engine SHALL place it above the head, or report a `face` finding with the fix (`"full": true`, or a `corner` or `side` move).

#### Scenario: Drawer card under the chin

- **WHEN** a drawer drops its card to rest just under the speaker's chin in a medium shot
- **THEN** the build places the card above the head, or refuses it with a `face` error and its fix
