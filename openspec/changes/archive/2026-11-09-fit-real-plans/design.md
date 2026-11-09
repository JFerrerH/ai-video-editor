# Design

## Context

Measured 2026-11-09 on 96 plans and specs (every `edit` stored by hosted jobs, plus the local replay cases), by walking each event's props against the component schema: 76 text and list fields seen, 13 over the `v0.8.5` limit. The drawer refusal was confirmed in the build, not only the precheck: both a tester's plan and an approved launch plan (a drawer in a close shot) were refused with "no band below or above it clears the speaker's head".

## Decisions

**D1. Take the band that clears the graphic, warn about the head.** `_caption_moves` keeps its order (below, then above) and prefers a band that clears the head too. When only a head-crossing band clears the graphic it is used, with a non-strict `caption_head` finding. This is what captions did before the head rule, plus the warning; the rule turned out to refuse plans that were fine.

**D2. Floors are numbers, not content.** `tools/tests/real_use_floors.json` holds `{type, path, floor}` and nothing from any plan, so the repo stays public-safe. Limits go to exactly the observed maximum; the test asserts `limit >= floor`.

**D3. Fit, don't lower.** After raising a limit, the matrix draws that field at it with wide capitals and random inputs. An overflow is fixed in the component through `fitSize` / `FIT_WRAP` and a card that grows, or the component's layout changes for a wider field. A limit never goes back down to pass.

## Risks / Trade-offs

- **Wide capitals at 22 characters may not fit a small card.** Then the text shrinks to `MIN_TEXT` and wraps, and a very long field makes a taller card; the finding is reported if it can't fit the safe area.
- **`caption_head` is only a warning.** A viewer can see captions over a face in a medium shot with a drawer; that is what the approved plans did.

## Migration Plan

Engine release `v0.8.6`; the product pins it. No data migration.

## Open Questions

None.
