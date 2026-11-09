# Tasks

## 1. Faster tests first

- [ ] 1.1 pytest-xdist in the dev group; `-n auto` in CLAUDE.md's test command and the test docstrings (measured 1 min 32 s against 4 min 07 s)
- [ ] 1.2 Matrix in parallel (D7) with its wall time printed; a full run under 5 minutes

## 2. Matrix inputs

- [ ] 2.1 Random inputs with `--seed` (D6), and refusals with a plan fix listed apart

## 3. Shared fixes

- [ ] 3.1 Surface-aware text colours (D1), with a test on a random palette, and the components moved to them
- [ ] 3.2 Size tokens (D2) and the lint test
- [ ] 3.3 Placement for any text (D3)
- [ ] 3.4 `data-overhang` (D4)
- [ ] 3.5 Caption bands and the chest rule on content boxes (D5), with tests for a card under captions and a drawer under the chin

## 4. Limits

- [ ] 4.1 `--fit-limits` (D8); compute and write every limit

## 5. Verification

- [ ] 5.1 The full matrix, fixed and random, exits 0 in under 5 minutes; record its wall time and peak memory
- [ ] 5.2 The added `plan_build` time on a 50 s plan from `layout-and-cut-invariants`
- [ ] 5.3 Under `footage/` (gitignored): the hosted plan that overflowed is refused with its fixes named; with them it renders, stills at each cut and the last second show nothing outside its card, no captions on a card or the face, no card on the chest, and a tail at the end; -14 LUFS
- [ ] 5.4 `short-form-pro` and `motion-graphics` SKILL.md and CLAUDE.md
