## ADDED Requirements

### Requirement: Dark-mode kits read on cards

Cards are light and take `ink` for their text. When a kit's `ink` is lighter than its `bg`, the engine SHALL swap them, so `ink` is the dark colour of the pair.

#### Scenario: Cream ink on a dark background

- **WHEN** a kit has `ink` #F2F0E9 and `bg` #16150F
- **THEN** a white card's text is #16150F, and a dark backdrop is asked for with `dark`
