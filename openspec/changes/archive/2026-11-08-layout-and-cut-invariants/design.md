# Design

## Context

Measured on a hosted preview (51 s, brand kit with a pale accent, medium shot) that passed every strict check:

- A ratio-bars card is 600 px wide with fixed 120 px columns and 44 px labels: any label over about five letters runs past the column, and with three bars the third label crosses the card's edge. Its contrast against the wall behind is fine, so the legibility probe, the only thing that saw it, passed.
- A drawer at the bottom pushed captions above it (`_caption_moves`), onto the speaker's eyes. `_caption_moves` compares the band with the graphic only.
- The last cut ended 0.15 s after the last word; the next source word started 0.10 s after it. `refine_edges` falls back to the quietest point when there is no silence within reach, which is right for a join but leaves an end with no air. One round earlier, the same fallback let a word from outside the edit into a preview, which `preview_qa` caught after a full render.

The measurement already exists: `measureText` in `Overlay.tsx` walks each event's DOM and returns text boxes and sizes, and `measure_events` draws each event alone and uses those boxes for placement and probes. Nothing compares a box with its card or the frame.

## Goals / Non-Goals

Goals: invariants that hold for any component, brand, framing and text; findings with fixes a plan can apply; generated inputs as the test, not the last failure.

Non-goals: new devices, camera-move rules, speed (stills and renders: separate change).

## Decisions

**D1. Containment from the DOM, in the existing measure mode.** `measureText` grows a second list: every element with a non-transparent background, border or image, with its box and its card (nearest ancestor that draws a background, excluding the event root). Text nodes get their card the same way. Python checks each box against its card and the safe area. One rule, every component, no per-component code. Alternative rejected: pixel diff of the card's alpha, which can't tell a label outside its card from a second card.

**D2. Measure at every cue finish.** `cue_finish` already lists entrance finishes per cue. `measure_events` adds measure-only jobs (no probe pair) at each distinct finish, in the same `stills.mjs` batch and bundle. The probe pair stays at the still time.

**D3. Caption bands checked against the head.** `_caption_moves` takes `head_box(e)` for the event's moment and accepts a band only if it clears both. Neither → a `face` finding. The head box is the one `measure_events` already uses for placement.

**D4. Air at cuts reuses `refine_edges`' numbers.** `pre` and `post` are what the refinement already treats as enough air. `no_air` is reported from the refinement's `detail` rows (an edge that fell back to the quietest point). In plans, `_cut_hint` maps the edge to its sentence.

**D5. The end tail is a freeze and a fade.** The last segment ends at the last word's out-point (no audio past the fallback point), the extract freezes that frame for `END_TAIL` s and the audio fades over the silence it has (at least 30 ms). `END_TAIL` is measured from the approved reference shorts' endings before it is set (task 3.1); until then the change does not ship.

**D6. Limits in the schema, enforced at validation.** `maxLength` / `maxItems` per field, checked by `overlay_schema` validation that `validate_plan` and spec validation already call. The matrix (D7) sets them: the largest value that passes on every fixture.

**D7. The matrix renders measure-only stills.** For each component: props from the schema's defaults with every text field at `maxLength` in wide capitals (M W O Q D H N U cycled), lists at `maxItems`, times at their defaults. All-"W" text (about 0.95 em a letter, twice ordinary text) was tried first and drove limits under what real plans use (a kinetic line to 12 characters where plans use 27); wide capitals keep a 1.5x margin over real text. Limits never go under real use (skill examples, fixtures, project plans); where a component couldn't fit that, the component was changed (shrink-to-fit titles and values, wrapping stickers, a notice inside the safe area). A card whose own example has no room above a close-up's head is reported as "no room", not as a limit to lower. Fixtures: `_template` (neutral), a dark kit and a pale-accent kit under `tools/tests/fixtures/`, and two synthetic head boxes. It reuses `measure_events`' findings, so the matrix and a real build can't disagree.

**D8. What the matrix found outside the components.** The first full run (1,376 findings) also exposed the checks:
- The legibility probe took the median of a glyph's changed pixels; on thin or small text most are anti-aliased edges,
  so it read 2.8-3.9:1 for colours that are 5:1 and would refuse readable cards in real builds. It now takes the far
  end of them (10th/90th percentile), the glyph's core, against the median of what is behind. Every never-list
  contrast fixture still fails.
- Boxes are cut to what `overflow: hidden` parents let show, text counts its own pill as its card, and an element
  marked `data-overhang` (a stamp across a card's edge) is held to the frame only.
- A dark-mode kit keeps its dark tints after `ink_on_light` swaps ink and background: they're blended toward the new
  light background. Short-form compositions make the kit's `muted` readable (4.5:1) on white and on its background,
  and small accent text aims at 5:1 against the backdrop's darkest glow.
- `stills.mjs` takes a free port of its own: two at once raced for Remotion's 3000.

## Risks / Trade-offs

- **Longer builds.** One measure render per entrance instead of per event. Measured in 4.2; if it adds more than 20 % to `plan_build`, the measure-only renders run at a smaller scale (boxes don't depend on it).
- **Limits refuse plans that rendered before.** Intended: those were the ones at risk. Errors name the limit.
- **A freeze at the end can land on a blink.** Accepted for now; the tail is short. A later change can pick the nearest open-eyes frame.

## Migration Plan

Engine release; the product pins it and bumps its guide. No data migration.

## Open Questions

- `END_TAIL`: measured in task 3.1.
