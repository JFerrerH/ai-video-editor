# Proposal

## Why

A full narrated-explainer pilot built from `BeatScene`s was rejected as "animated bullet points":
every beat was a headline plus one UI card that pops in, and each hard cut reset the frame, so
nothing carried the story. A style test where the metaphor itself acted (a snowball rolls down a
slope, smashes labelled blocks, swallows the shards and grows while the camera follows) was
approved as the direction. The engine has no way to build that kind of continuous, object-driven
world across several narrated beats; the test was a one-off prototype scene (`SnowballScene`).

## What Changes

- **New scene type `WorldScene`:** a continuous 2.5D world seen through a moving camera. Each
  narrated beat is still its own storyboard scene (own narration clip, own `@word` cues, own
  headline phrases), but consecutive `WorldScene`s that name the same `world` render as **one**
  continuous scene: time, camera and object state carry across the beat boundaries.
- **World definition** at the storyboard level (`worlds: {<id>: {terrain, objects[]}}`):
  - `terrain`: `snow` (a slope at a given angle, sky, a far ridge and trees in parallax, snowfall),
    coloured from the brand palette.
  - Objects: `block` (labelled, breakable), `ball` (rolls, grows, carries a value pill), `figure`
    (the existing stick figure, placed in the world), `sign` (a post with text planted in the
    ground), `prop` (`paper`, `towel`, `dumbbell`, `calculator`), `callout` (text bubble pointing
    at an object).
- **Actions** per beat (`actions: [{at, target, do, ...}]`, times accept cues):
  `roll` (to a position or a block; arriving at a block breaks it), `break` (shatter, pieces
  pulled into a ball, lime burst, label pill), `grow`, `value` (count up, optional `chip` that
  flies into the pill), `push` (a block barely moves), `pile` (snow piles on top), `highlight`,
  `pose`, `walk`, `throw`, `fall`, `show`/`hide`, sky `timelapse` (sun/moon cycles with a
  counter pill), and `camera` (follow an object or hold a position, zoom, eased; automatic punch
  and shake on breaks).
- `check` validates worlds: unknown world, object, target or action, an action that does not
  fit its target's kind, and a transition between two beats of the same world run (ERROR).
- The headline keeps working: each beat's words are shifted onto the merged scene's clock.
- `SnowballScene` (the prototype) is removed; its behaviour lives on as `WorldScene` objects and
  actions.
- motion-graphics `SKILL.md`: a "World scenes" section (when to use a world instead of beats,
  object/action reference, the run rule) and the beat-sheet guidance points to it. `CLAUDE.md`
  routing mentions world scenes for metaphor-driven explainers.
- **Out of scope:** terrains other than `snow` (the format allows more later), physics
  simulation (motion is eased keyframes, deterministic per frame), 3D, multiple cameras or
  split screens, raster art, lip-sync, changes to `BeatScene`, widgets or short-form overlays.

## Capabilities

### New Capabilities

- `world-scenes`: continuous camera-driven worlds for explainers: world definitions, objects,
  actions, camera, run merging across narrated beats, and their checks.

### Modified Capabilities

- `storyboard-video`: the scene-primitive list gains `WorldScene`; the contact sheet keeps one
  settled frame per narrated beat inside a world run.

## Impact

- Code: `tools/motion/src/scenes/WorldScene.tsx` and `tools/motion/src/world/` (new; terrain,
  objects, camera, state folding), `scenes/index.ts`, removal of `scenes/SnowballScene.tsx`;
  `tools/storyboard.py` (world validation, cue resolution in actions, run merging when writing
  render props, headline words for world beats).
- Skills/docs: `.claude/skills/motion-graphics/SKILL.md`, `CLAUDE.md`. Affected workflow:
  motion-graphics (narrated explainers, promos). short-form-pro and video-use are unaffected.
- No new dependencies or models (Remotion + SVG only); render cost is in line with `NetworkScene`.
