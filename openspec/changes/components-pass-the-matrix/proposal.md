# Proposal

## Why

The layout matrix (change `layout-and-cut-invariants`) draws every component through the same measurement a build runs. With each schema's own example text, 33 of 48 components fail on at least one of three brand kits and two framings: 277 findings, almost all text under 4.5:1 contrast, text under 28 px, text over the face with no refusal, or a shape leaving its card. They are the same refusals that cost a hosted session several plan rounds. A check on a hosted preview also showed captions over a drawer's card and a card resting on the speaker's chest, which no rule covers. Fixing them one component at a time would pass these fixtures and break on the next brand, so the fixes go in shared code and are tested on random inputs. A sequential matrix run takes 13–18 minutes, too long to run on every change.

## What Changes

- **Text colour by surface.** Components draw text through a theme helper that picks the colour for the surface the text sits on (a white card, a tint, the brand background), at 4.5:1 or more for any brand. No component computes contrast against a surface it doesn't draw on.
- **Type sizes as tokens.** Font sizes come from theme tokens whose smallest step renders at least 28 px with margin; components stop writing font sizes as numbers.
- **Placement for every graphic with text.** Any event whose text would cover the head is placed above it or refused with its fix, whatever its layer flag, unless its schema says it owns its place.
- **Declared overhangs.** An element designed to leave its card (a stamp across the edge, rotated photos) says so in its markup. It is still held to the frame and the safe area.
- **Captions clear cards, not only text.** Caption bands are checked against an event's drawn content box, not only its text.
- **No card on the chest.** A floating card may not sit over the speaker's body below the chin; the engine places it above the head, or refuses with the fix (`full`, or a `corner` or `side` move).
- **Random inputs with a seed, refusals apart, computed limits.** Each matrix run adds random brand palettes, text lengths and item counts, printing a seed that reproduces it. A refusal with a plan fix is listed apart and doesn't fail the run. `--fit-limits` computes every `maxLength` / `maxItems`.
- **Fast tests.** The matrix runs its fixtures and the random sample in parallel processes, under 5 minutes for a full run on a 10-core Mac. The engine suite runs with `pytest -n auto` (1 min 32 s measured, against 4 min 07 s sequential). A test run over 10 minutes is a defect.

Out of scope: new devices; camera moves that reveal an empty backdrop; non-text contrast.

Tools: `tools/motion/src/theme.ts` and the components under `tools/motion/src/`, `tools/shortform.py` (placement, caption bands, chest), `tools/layout_matrix.py`, `tools/overlay_schema.py`, `pyproject.toml` (pytest-xdist in the dev group). Skill: `short-form-pro`, `motion-graphics` (theme helpers). Workflows: `short-form-pro` and `motion-graphics` storyboards (same components). No new models.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `overlay-schema`: surface-aware text colours and size tokens, declared overhangs, the matrix's random inputs, refusals, computed limits and time budget.
- `edit-faults`: captions clear an event's drawn content, and no floating card on the speaker's chest.

## Impact

Most components change their colour and size code; their look changes where text was too pale or too small. Schema limits drop to what fits. The engine can be released once the matrix, fixed and random, exits 0.
