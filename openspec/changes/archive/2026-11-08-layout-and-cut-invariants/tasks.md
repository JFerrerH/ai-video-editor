# Tasks

## 1. Geometry

- [x] 1.1 Fixture: a ratio-bars event with a 12-letter third label, and a test that `check --strict` with stills reports `outside` (fails before the code)
- [x] 1.2 `measureText` returns shapes and each box's card; Python checks card and safe-area containment as kind `outside`, in STRICT_KINDS (D1)
- [x] 1.3 Measure at every cue finish (D2), with a test for a late item

## 2. Captions and the head

- [x] 2.1 Test: a drawer in a medium shot whose only caption band crosses the eyes gives a `face` error and no band over the head
- [x] 2.2 `_caption_moves` checks each band against `head_box` at that moment (D3)

## 3. Cuts

- [x] 3.1 Measure the endings of the approved reference shorts (time from the last speech energy to the end) and set `END_TAIL` with that source in a comment
- [x] 3.2 `no_air` from `refine_edges` details, strict error except the last out-point, reported before stills in `plan_build` with the sentence (D4), with tests for 0.10 s and 0.40 s
- [x] 3.3 End tail: freeze and fade (D5), with a test on a synthetic take whose last word runs into the next

## 4. Limits and the matrix

- [x] 4.1 Schema test: every rendered text field has `maxLength`, every list `maxItems`; validation refuses values over them
- [x] 4.2 `tools/layout_matrix.py` (D7) with the three brand fixtures and two head boxes; record its run time and the added `plan_build` time on a 50 s plan (matrix: 336 s for 288 inputs with 6 jobs; `plan_build` on a 64 s plan: 91 s on main, 99 s here, +9 %)
- [x] 4.3 Run the matrix; fix each flagged component (fit its content) or lower its limit, until it exits 0

## 5. Docs

- [x] 5.1 `short-form-pro` SKILL.md and CLAUDE.md: the new finding kinds, limits, the tail, the matrix as a release gate

## 6. Verification

- [x] 6.1 Full engine test suite and the matrix
- [ ] 6.2 Under `footage/` (gitignored): the hosted plan that showed the overflow is refused with `outside` and `face` errors; with the fixes, it renders, and stills at each cut and the last second show nothing outside its card, no captions on the face, and a tail at the end; -14 LUFS
  - 2026-11-08, on the Mac at main 0329ca5 with the hosted plan (sentence IDs mapped by text): refused before the preview with one `outside` error, the ratio-bars third label (an 11-letter word) 23 px past its card's right edge. The matrix had passed that component because it tests a field whose example has no letters with digits only, while the field takes any text. Not met: no caption `face` error in this layout, and the drawer still shows captions over its card's bottom edge and the card resting on the speaker's chest, which no rule covers. All three go to `components-pass-the-matrix`, with the render that closes this task.
