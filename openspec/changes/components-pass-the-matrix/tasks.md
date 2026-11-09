# Tasks

## 1. Faster tests first

- [x] 1.1 pytest-xdist in the dev group; `-n auto` in CLAUDE.md's test command (1 min 32 s measured, against 4 min 07 s)
- [x] 1.2 Matrix jobs split by component and fixture (D5); print the wall time. 233 s for 288 inputs with 8 jobs (336 s before), peak RSS 1.2 GB. `stills.mjs` now shares one browser per scale (163 s to 121 s for one pair, same boxes), and the matrix measures at scale 1 as a build's stills do: at 0.5 it missed a drawer title 11 px past the bottom limit that a build reports

## 2. Inputs

- [x] 2.1 Character kinds (D1): schema values, the schema test, `widest()` reading the kind; with a test that a field whose example is "18–24" is tested with letters
- [x] 2.2 Random inputs with `--seed` (D3): two per component by default; the same seed gives the same findings; a full run is 295 s for 384 inputs, and the random sample found three components the fixed kits pass (two with no text showing, one contrast)
- [x] 2.3 Fix what letters and random inputs flag (D2), through shared code: `fitSize`/`FIT_WRAP`/`MIN_TEXT` (ratio bars, documents, topic cards, dot track, network chips), `accentOn` at 4.5:1 by default (a floating card can be scaled down), `textPair` for text on a coloured fill (headline pill, hook title, end card, buttons, chips), the scene palette taken on its real backdrop, the drawer card anchored above the safe text limit, a no-text probe relative to the text's own boxes (threshold measured on 137 visible texts), and own-place devices refused with the right fix

## 3. Layout rules

- [x] 3.1 Tests: captions that would overlap a drawer's card move clear of it; a floating card with no room above a close-up's head is refused, never placed below the chin
- [x] 3.2 Content boxes stored for every event, and caption bands checked against them (D4)

## 4. Docs

- [x] 4.1 `short-form-pro` SKILL.md and CLAUDE.md (and `motion-graphics`: kinds, fit, colours by surface)

## 5. Verification

- [x] 5.1 The full matrix, fixed and random, exits 0 in under 5 minutes; record wall time and peak memory: 0 findings with seeds 642169, 201273, 158762 (each had found something) and a fresh 234256; 255-273 s for 384 inputs with 8 jobs; peak RSS 1.3 GB
- [x] 5.2 The engine suite with `-n auto` under 2 minutes: 536 passed in 1 min 14 s
- [ ] 5.3 Under `footage/` (gitignored): the hosted plan with the 11-letter label is refused with its fixes named, or fits; with the fixes it renders, and stills at each cut and the last second show nothing outside its card, no captions on a card or the face, and a tail at the end; -14 LUFS
  - 2026-11-09, the hosted plan built on the Mac: the 11-letter ratio-bars label now fits its card; the ending holds on "...de la sala?" with no caption for the next line's onset (a new rule: a word the cut only grazes, its onset or its tail within the edge air, gets no caption), -14.1 LUFS, preview QA passes. Not met: the drawer moment is refused (its card fills the caption band in this medium shot, and above it is the face), and neither fix the refusal names works for it: a `side` move leaves the head across the same band, and `full` is not a drawer prop. A refusal must only name fixes that apply to that event; that and a one-line caption band for tight spans are open.

