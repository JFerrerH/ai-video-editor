# Proposal

## Why

Replaying 96 plans and specs from hosted sessions against `v0.8.5` showed two regressions from the layout work. First, plans with a drawer that passed on `v0.8.4` are now refused ("captions cover the drawer's text and no band clears the speaker's head"), though the drawer plan was fine as generated. Second, 13 schema limits sit below what real plans used: a card kicker of 22 characters against a limit of 12 (76 plans), a sticker list of 6 against 3 (31 plans), a receipt title of 17 against 11, an id card with 3 rows against 2. Those plans would now be refused for content the components used to draw.

## What Changes

- **Captions near the head are advice, not a refusal.** When captions move to clear a graphic and the only band that clears it also crosses the head, they take that band and a `caption_head` warning says so. A band that clears both is still preferred. Only when no band clears the graphic at all does the strict `captions_on_text` finding remain.
- **Limits at or above real use.** Each of the 13 fields is raised to the most real plans used, from a table of numbers kept in the repo (`tools/tests/real_use_floors.json`, no text), and a test fails if a limit falls under its floor. The layout matrix, which draws every component at its limits, checks the new values, and a component that overflows at one is fixed through the shared text fitting, never by lowering the limit.

Out of scope: the preview QA hearing a word the edit doesn't contain (investigated on its own), and any new rule about captions.

Tools: `tools/shortform.py` (caption bands), component schemas and the components the matrix flags, `tools/tests/`. Skill: `short-form-pro`. Workflows: `short-form-pro`. No new models or dependencies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `edit-faults`: captions that must cross the head to clear a graphic do so with a warning.
- `overlay-schema`: limits are never under what real plans used.

## Impact

Plans that used to be refused for the drawer and the captions pass again with a warning. Components draw longer text than the schema allowed in `v0.8.5`; where one overflowed at the new limit, its text now shrinks and wraps inside its card.
