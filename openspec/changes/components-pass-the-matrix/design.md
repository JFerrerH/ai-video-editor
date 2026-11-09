# Design

## Context

At main 0329ca5 the matrix exits 0 in 336 s (6 jobs, 288 inputs). A hosted plan built there is refused: a ratio-bars label of 11 letters runs 23 px past its card. `widest()` in `layout_matrix.py` gives a field whose example has no letters the widest digit instead of letters, so the label (example "18–24", `maxLength` 20) was only ever tested with digits. The plan's drawer also shows captions over the card's bottom edge and the card resting under the speaker's chin. The engine suite takes 4 min 07 s sequential and 1 min 32 s with `pytest -n auto` (527 passed).

## Goals / Non-Goals

Goals: matrix inputs that cover what the schema allows, not what the example shows; the two layout rules; a matrix under 5 minutes and a suite under 2.

Non-goals: new devices; camera rules.

## Decisions

**D1. Kinds in the schema.** `x-text` stays `true` for any text and gains `"number"` and `"symbol"`. A schema test fails on a field whose examples have no letters and no declared kind, so every such field gets a decision once. `widest()` reads the kind; it no longer looks at the example.

**D2. Fixing what the letters flag.** Components flagged under letters use the shrink-to-fit #24 added (TopicCards, DotTrack): text shrinks to the minimum size, then wraps by words, inside its card. A limit drops only when that still can't fit, and never under real use (skill examples, fixtures, plans).

**D3. Random inputs.** A seeded generator draws palettes in OKLCH (hue random, lightness 0.15–0.97, chroma 0–0.2), lengths and counts uniform within the limits. Two per component per run by default (`--random`): each is a random brand and framing with random props for every component, so a full run stays in the time budget (295 s for 384 inputs with 8 jobs). Every input depends only on the seed, the sample and the component, so a seed reproduces a run however the work is split. They join the same job pool as the fixed pairs.

**D4. Placement stays above the head.** The user rejected placing floating cards below the chin to make them fit (2026-11-03) but accepted a drawer low in the frame as a device of its own. `_place` already only moves a card into the band above the head or refuses it; a property test holds it there, and drawers are not touched. Captions keep clearing an event's text only: a rule over the card's whole box was tried and dropped, because it refused a drawer plan that was fine.

**D4b. A refusal with its fix is the rule working.** When the engine refuses a floating card because no readable size fits above that head ("fits above the speaker's head only at …"), the plan's answer is the fix it names (`full`, a `corner` or `side` move). The matrix lists that refusal and its face finding apart for any text, not only when the component's own example fails too; a component that covers the face without that refusal still fails. Measured: the ratio-bars card at its limits doesn't fit above a close-up's head even with 4-letter captions and 6-letter labels, while lowering limits under real use would not change that.

**D5. Speed.** The matrix splits its jobs by component as well as by fixture, so the random sample doesn't lengthen the slowest worker; workers = `cpu_count - 2`. pytest-xdist goes in the dev group and the docs' test command.

## Risks / Trade-offs

- **More components flagged at first.** Intended: they were passing on the wrong input.
- **Memory with more workers.** Measured in 5.1; capped if a run swaps.

## Migration Plan

Engine release after this change; the product pins it.

## Open Questions

None.
