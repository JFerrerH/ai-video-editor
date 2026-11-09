# Design

## Context

Matrix with each schema's example text (2026-11-08, 288 inputs, 13 min sequential): 277 findings in 33 components. By kind: contrast in ~25 components (secondary text at 2.3–4.4:1; components compute `readable()` against the brand background while drawing on a hard-coded white card or a tint), text under 28 px in 7 (literal sizes of 22–28 px, some rendering at 27.9), text over the face with no refusal in ~12 (placement only runs for `floating` events), shapes leaving their card in 6 (some by design: a stamp, rotated photos, a world that pans). A hosted plan built locally also showed captions over a drawer's card and the card on the speaker's chest.

## Goals / Non-Goals

Goals: every component passes the matrix, fixed and random, through shared code; a full matrix run under 5 minutes; the engine suite under 2 minutes.

Non-goals: redesigning devices; camera rules.

## Decisions

**D1. A surface in the theme.** `theme.ts` gains `surface(name)` returning the surface colour and its text roles (`ink`, `muted`, `accent`), each brought to the required contrast against that surface by the existing `readable()`. Components name their surface (`card`, `tint`, `bg`) instead of computing colours.

**D2. Size tokens.** `type.xs … xl` in the theme, the smallest 30 px at scale 1. Components use tokens; a lint test fails on a numeric `fontSize` under the smallest token in `tools/motion/src`.

**D3. Placement for any text.** `measure_events`' `floating()` covers every event with text on the front or panel layer that isn't `x-place: own`, `full` or hand-framed. An `own` component that covers the face is a defect the matrix reports.

**D4. Overhangs in markup.** `data-overhang` on an element: the card check skips it; the frame and safe-area checks don't.

**D5. Content boxes for captions and the chest.** `_caption_moves` and the chest rule use the content box `measure_events` already computes (`alpha_box` of the card, solid pixels). The chest region is from the head box's bottom to the frame's bottom, across 2.5 head widths centred on the head.

**D6. Random inputs.** A seeded generator draws palettes in OKLCH (random hue, lightness 0.15–0.97, chroma 0–0.2, so light and dark kits both appear), lengths and counts uniform within limits. Twelve random inputs per component per run by default.

**D7. Parallel by construction.** The matrix builds its job list (component × fixture or random input) and runs it in `os.cpu_count() - 2` processes. Each worker has its own temp project and runs `stills.mjs` once for its whole slice (one bundle per worker). The engine suite runs with pytest-xdist.

**D8. Computed limits.** `--fit-limits` bisects each field's length (and each list's count) on all fixtures and the random sample, in parallel, and writes the largest passing value.

## Risks / Trade-offs

- **Looks change.** Pale secondary text gets darker; small labels grow. That is the fix.
- **Memory with parallel Remotion.** Each worker holds a browser; capped at `cpu_count - 2` and at what fits in memory (measured in task 5.1).

## Migration Plan

Engine release once the matrix exits 0, together with `layout-and-cut-invariants`.

## Open Questions

None.
