# Tasks

## 1. Faster tests first

- [x] 1.1 pytest-xdist in the dev group; `-n auto` in CLAUDE.md's test command (1 min 32 s measured, against 4 min 07 s)
- [x] 1.2 Matrix jobs split by component and fixture (D5); print the wall time. 233 s for 288 inputs with 8 jobs (336 s before), peak RSS 1.2 GB. `stills.mjs` now shares one browser per scale (163 s to 121 s for one pair, same boxes), and the matrix measures at scale 1 as a build's stills do: at 0.5 it missed a drawer title 11 px past the bottom limit that a build reports

## 2. Inputs

- [x] 2.1 Character kinds (D1): schema values, the schema test, `widest()` reading the kind; with a test that a field whose example is "18–24" is tested with letters
- [x] 2.2 Random inputs with `--seed` (D3): two per component by default; the same seed gives the same findings; a full run is 295 s for 384 inputs, and the random sample found three components the fixed kits pass (two with no text showing, one contrast)
- [x] 2.3 Fix what letters and random inputs flag (D2), through shared code: `fitSize`/`FIT_WRAP`/`MIN_TEXT` (ratio bars, documents, topic cards, dot track, network chips), `accentOn` at 4.5:1 by default (a floating card can be scaled down), `textPair` for text on a coloured fill (headline pill, hook title, end card, buttons, chips), the scene palette taken on its real backdrop, the drawer card anchored above the safe text limit, a no-text probe relative to the text's own boxes (threshold measured on 137 visible texts), and own-place devices refused with the right fix

## 3. Layout rules

- [x] 3.1 Test: a floating card with no room above a close-up's head is refused, never placed below the chin (a property test over random cards and heads)
- [x] 3.2 Dropped: captions keep clearing an event's text, as before; checking the card's whole drawn box refused a drawer plan that was fine

## 4. Docs

- [x] 4.1 `short-form-pro` SKILL.md and CLAUDE.md (and `motion-graphics`: kinds, fit, colours by surface)

## 5. Verification

- [x] 5.1 The full matrix, fixed and random, exits 0 in under 5 minutes; record wall time and peak memory: 0 findings with seeds 642169, 201273, 158762 (each had found something) and a fresh 234256; 255-273 s for 384 inputs with 8 jobs; peak RSS 1.3 GB
- [x] 5.2 The engine suite with `-n auto` under 2 minutes: 536 passed in 1 min 14 s
- [x] 5.3 Under `footage/` (gitignored): the hosted plan with the 11-letter label is refused with its fixes named, or fits; with the fixes it renders, and stills at each cut and the last second show nothing outside its card, no captions on a card or the face, and a tail at the end; -14 LUFS
  - 2026-11-09, the full hosted plan, drawer included, built on the Mac: compiles, renders in 87 s, preview QA passes, -14.1 LUFS. The 11-letter ratio-bars label fits its card and the ending holds on "...de la sala?" with no caption for the next line's onset (a word the cut only grazes, within the edge air, gets no caption). The drawer needed no rule: the first attempt re-anchored its card by the bottom and moved it into the caption band for ordinary content, so it was restored to the original and Doc's text fitting covers what the matrix found; a caption rule for the card's drawn box was dropped for the same reason (the user's plan was fine as it was).
