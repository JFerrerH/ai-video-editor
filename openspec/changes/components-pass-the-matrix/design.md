# Design

## Context

At main 0329ca5 the matrix exits 0 in 336 s (6 jobs, 288 inputs). A hosted plan built there is refused: a ratio-bars label of 11 letters runs 23 px past its card. `widest()` in `layout_matrix.py` gives a field whose example has no letters the widest digit instead of letters, so the label (example "18–24", `maxLength` 20) was only ever tested with digits. The plan's drawer also shows captions over the card's bottom edge and the card resting under the speaker's chin. The engine suite takes 4 min 07 s sequential and 1 min 32 s with `pytest -n auto` (527 passed).

## Goals / Non-Goals

Goals: matrix inputs that cover what the schema allows, not what the example shows; the two layout rules; a matrix under 5 minutes and a suite under 2.

Non-goals: new devices; camera rules.

## Decisions

**D1. Kinds in the schema.** `x-text` stays `true` for any text and gains `"number"` and `"symbol"`. A schema test fails on a field whose examples have no letters and no declared kind, so every such field gets a decision once. `widest()` reads the kind; it no longer looks at the example.

**D2. Fixing what the letters flag.** Components flagged under letters use the shrink-to-fit #24 added (TopicCards, DotTrack): text shrinks to the minimum size, then wraps by words, inside its card. A limit drops only when that still can't fit, and never under real use (skill examples, fixtures, plans).

**D3. Random inputs.** A seeded generator draws palettes in OKLCH (hue random, lightness 0.15–0.97, chroma 0–0.2), lengths and counts uniform within the limits; eight per component per run. They join the same job pool as the fixed pairs.

**D4. Content boxes for captions and the chest.** Both use the content box `measure_events` already computes (the card's solid pixels). The chest region runs from the head box's bottom to the frame's bottom, 2.5 head widths wide around the head.

**D5. Speed.** The matrix splits its jobs by component as well as by fixture, so the random sample doesn't lengthen the slowest worker; workers = `cpu_count - 2`. pytest-xdist goes in the dev group and the docs' test command.

## Risks / Trade-offs

- **More components flagged at first.** Intended: they were passing on the wrong input.
- **Memory with more workers.** Measured in 5.1; capped if a run swaps.

## Migration Plan

Engine release after this change; the product pins it.

## Open Questions

None.
