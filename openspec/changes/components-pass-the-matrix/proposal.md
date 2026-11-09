# Proposal

## Why

The layout matrix now exits 0 on every component (change `layout-and-cut-invariants`), yet a hosted plan built on the same commit is refused because a ratio-bars label, an ordinary 11-letter word, runs 23 px past its card. The matrix passed it because it picks the kind of characters from the schema's example: a field whose example has no letters ("18–24") is tested with digits only, though it takes any text. A component can pass by matching its example rather than the inputs its schema allows. The same plan also shows captions over a drawer's card, which no rule covers. And a full matrix run takes 336 s, the engine suite 4 minutes sequential: a change can't be checked often at that cost.

## What Changes

- **Character kind from the schema, never from the example.** A text field declares `x-text: "number"` (digits, amounts, years) or `"symbol"` when that is all it takes; every other text field is tested with wide letters. Fields that take words but were tested with digits are fixed by fitting the component, through the same shrink-to-fit used by #24, or by a lower limit.
- **Random inputs with a seed.** Each run adds random brand palettes (light and dark), text lengths and item counts within the limits, and prints a seed; `--seed` reproduces it. A component tuned to the fixed kits fails the next seed.
- **Placement never moves a card below the chin**: the engine places a floating card above the head or refuses it with the fix. A drawer low in the frame is a device the plan chose, not a placement, and stays allowed.
- **Fast tests.** The engine suite runs with `pytest -n auto`; the matrix, fixed and random, finishes under 5 minutes. A test run over 10 minutes is a defect.

Out of scope: new devices, camera moves that reveal an empty backdrop, non-text contrast.

Tools: `tools/layout_matrix.py`, component schemas and the components the new inputs flag, `tools/shortform.py` (caption bands), `pyproject.toml` (pytest-xdist in the dev group). Skill: `short-form-pro`. Workflows: `short-form-pro`, `motion-graphics` storyboards (same components). No new models.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `overlay-schema`: character kinds declared in the schema, random matrix inputs with a seed, a time budget for the matrix.
- `edit-faults`: placement never moves a card below the chin.

## Impact

Some schemas gain `x-text` kinds; components that can't take words at their limit shrink to fit or get a lower limit. The engine is released after this change, with `layout-and-cut-invariants`.
