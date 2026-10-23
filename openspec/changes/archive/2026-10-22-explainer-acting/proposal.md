# Proposal

## Why

In a narrated-explainer pilot the user found the figure too passive and the scene too empty: one
pose change and one card per beat, while the script talks about reading a book, wanting to buy
something, waiting a day and weighing head against heart. The rig and widget set can't act those
words out, so every beat falls back to a badge.

## What Changes

- **Poses:** add `read` (holding something open at chest height), `wait` (arms crossed), `reach`
  (leaning in, front arm out to grab), `scared` (recoil, hands up) and `walk` (a stride cycle,
  used while the figure moves).
- **Held props:** add `book`, `phone` and `bag` (shopping bag), drawn in the figure's hand, with
  default-prop pairings (`read` → `book`).
- **Figure moves:** a figure can travel across its slot: `moves: [{x, at, dur}]` (x 0–1 in the
  slot), playing `walk` while it moves and settling into the current pose when it stops.
- **New widgets:**
  - `ProductCard`: a product with icon, name and price, plus a buy button that can be pressed
    (`pressAt`), greyed out (`lockAt`) or made to vanish (`out`, as a shrink-and-fade "poof").
  - `Calendar`: a day page that flips from one label to the next on cues ("Hoy" → "Mañana").
  - `Balance`: a scale with two labelled pans that tilts towards one side on cues (`tilts: [{to:
    left|right|level, at}]`).
  - `ThoughtBubble`: a bubble with an icon or short text that rises from the figure's head side,
    in the `side` slot or above the figure.
- **Icons:** add the line icons `book`, `cart`, `heart`, `brain` and `moon`.
- `check` validates the new poses, props, widgets and move times. The pose and widget sheets
  show the new items.
- **Out of scope:** facial expressions, two figures in one beat, lip-sync, figure moves between
  slots, raster art, and any change to `KineticType`/`TitleCard` or the short-form overlays.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `explainer-graphics`: more poses and props; figure moves within its slot; four new widgets; new icons.

## Impact

- Code: `tools/motion/src/explainer/` (`poses.ts`, `Figure.tsx`, `widgets/`, `sheets.tsx`),
  `tools/motion/src/components/icons.tsx`, `tools/storyboard.py` (validation of the new fields).
- Skill: the `motion-graphics` SKILL.md "Narrated explainer" reference tables (poses, props,
  widgets, moves). No CLAUDE.md routing change: the workflow stays the same.
- Workflows: only `motion-graphics` narrated explainers. `short-form-pro` and `video-use` are not
  affected. Existing storyboards render unchanged (every addition is opt-in).
- Dependencies: none new. Everything is vector/SVG in Remotion, free and local.
