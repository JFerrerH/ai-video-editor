# Tasks

## 1. Faster tests first

- [x] 1.1 pytest-xdist in the dev group; `-n auto` in CLAUDE.md's test command (1 min 32 s measured, against 4 min 07 s)
- [x] 1.2 Matrix jobs split by component and fixture (D5); print the wall time. 233 s for 288 inputs with 8 jobs (336 s before), peak RSS 1.2 GB. `stills.mjs` now shares one browser per scale (163 s to 121 s for one pair, same boxes), and the matrix measures at scale 1 as a build's stills do: at 0.5 it missed a drawer title 11 px past the bottom limit that a build reports

## 2. Inputs

- [x] 2.1 Character kinds (D1): schema values, the schema test, `widest()` reading the kind; with a test that a field whose example is "18–24" is tested with letters
- [ ] 2.2 Random inputs with `--seed` (D3)
- [ ] 2.3 Fix what letters and random inputs flag (D2)

## 3. Layout rules

- [ ] 3.1 Tests: a card under the captions, and a drawer card under the chin
- [ ] 3.2 Caption bands and the chest rule on content boxes (D4)

## 4. Docs

- [ ] 4.1 `short-form-pro` SKILL.md and CLAUDE.md

## 5. Verification

- [ ] 5.1 The full matrix, fixed and random, exits 0 in under 5 minutes; record wall time and peak memory
- [ ] 5.2 The engine suite with `-n auto` under 2 minutes
- [ ] 5.3 Under `footage/` (gitignored): the hosted plan with the 11-letter label is refused with its fixes named, or fits; with the fixes it renders, and stills at each cut and the last second show nothing outside its card, no captions on a card or the face, no card on the chest, and a tail at the end; -14 LUFS
