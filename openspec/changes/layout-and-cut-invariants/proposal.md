# Proposal

## Why

The checks so far measure named properties at one moment per graphic (text size, contrast, the face at the still time, false starts), and most were added after the failure that showed them. A hosted preview passed every check with a ratio-bars label running past its card, captions lifted onto the speaker's eyes to clear a drawer, a cut that ended 0.15 s after the last word with the next word 0.1 s away, and, one round earlier, a cut that let a word from outside the edit into the preview. None of these is specific to that video: they are general rules nobody wrote down. This change writes them as invariants every component, brand, framing and text must meet, and tests them on generated inputs instead of on the last failure.

## What Changes

- **Geometry invariant.** In measure mode, every visible text box and every drawn shape must sit inside its own card (the nearest ancestor with a background) and inside the frame's safe area. Measured for every component through the existing DOM measurement, at every entrance's finish and at the final state, not at one still time.
- **Captions keep clear of the head.** When captions move to make room for a graphic, the new position is checked against the speaker's head box at that moment. If neither position clears both the graphic and the head, it is a finding, not a placement over the face.
- **Cuts have air.** An edge whose outer side has less silence than the edge refinement's own air (`pre` before an in-point, `post` after an out-point) before the next sound is a finding in strict mode, named by sentence in plans, instead of a cut at the quietest point.
- **The video ends with a tail.** The last edge holds the picture for a measured tail and fades the audio, so a short never stops on the last syllable.
- **Text fields declare their limits.** Every rendered text field and list in a component schema has `maxLength` / `maxItems`; a plan over them is refused at validation, before any still.
- **Layout matrix.** A tool renders each component in measure mode with generated props at those limits, on three brand fixtures and two framings, and reports every invariant broken. A component either fits every allowed input or its schema stops allowing it. It runs as a release gate.

Out of scope: camera moves that reveal an empty backdrop, non-text contrast for meaningful shapes, caption chunk minimums, and redesigning individual components beyond what the matrix reports. Speed of stills and renders is a separate change.

Tools: `tools/motion/src/Overlay.tsx` (measure mode), `tools/shortform.py` (measurement schedule, caption moves, edges, tail), `tools/short_spec.py` (finding kinds), `tools/edit_plan.py` (limits and edge hints), `tools/overlay_schema.py`, component schemas, new `tools/layout_matrix.py`. Skill: `short-form-pro`. Workflows: `short-form-pro` and headless `plan_build` / `shortform`; `motion-graphics` storyboards are not affected. No new models or dependencies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `edit-faults`: geometry, captions clear of the head, air at cuts, and the end tail, all strict findings.
- `overlay-schema`: text and list limits in every schema, and the layout matrix.

## Impact

More measure-only renders per build (one per entrance instead of one per event): the cost is measured in the tasks before release. Components the matrix flags change size or wrapping, or get stricter limits. Saved plans that break a new limit are refused with the field and its limit.
