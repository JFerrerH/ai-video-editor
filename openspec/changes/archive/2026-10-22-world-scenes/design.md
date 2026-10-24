# Design

## Context

- `tools/storyboard.py` resolves each scene's `@word` cues to seconds from that scene's start,
  places narration clips and SFX on the global timeline from the **unmerged** scene list, and
  writes `story_props.json` for the Remotion `Story` composition. `stills` and the contact sheet
  also work from the unmerged timeline.
- `BeatScene` receives `words` (headline) only because `storyboard.py` injects them for that type.
- The approved prototype `SnowballScene` (one scene, one narration clip) already has: snow
  terrain, parallax ridge, snowfall, a ball with eased roll segments, shatter + absorb, value pill
  and chips, camera follow with lag, punch and shake, and the figure placed in world space through
  a CSS transform. Everything is computed from the frame number.

## Goals / Non-Goals

**Goals:** one reusable world engine that a storyboard drives with objects and cued actions; beats
stay the unit of narration, checks and stills; the look of the prototype is the baseline.

**Non-Goals:** a general physics or tweening library; terrains beyond `snow`; editing worlds
visually; exposing per-object easing curves in the storyboard.

## Decisions

1. **Merge runs only when writing render props.** `storyboard.py` keeps validating, timing and
   mixing per beat. In the step that writes `story_props.json`, a run of consecutive `WorldScene`s
   with the same `world` becomes one scene: `duration` = sum of beat durations, `actions` and
   `words` shifted by each beat's offset in the run, and `beats: [{name, start}]` for debugging.
   No transitions inside a run, so the global timeline is identical merged or not; narration, SFX
   and stills need no change. *Alternative:* one long narrated scene per world. Rejected: one clip
   to re-synthesise per edit, cues ambiguous across many sentences, and the >7 s WARN loses meaning.
2. **Time fields are named.** Inside `actions`, `at`, `arrive` and `until` are times (shifted on
   merge, cue-resolved); `dur` is a length. `arrive` lets a roll land its impact on a spoken word. Ball `roll` with a block `to` computes the arrival time as `at + dur` (default
   derived from distance at a cruising speed). The engine's cue walker already resolves any cue
   string, so actions need no special casing there; the merge shifts `at` only.
3. **State folding per frame.** `tools/motion/src/world/` computes each object's state at time `t`
   by folding the sorted actions up to `t` (position, radius, value, visibility, broken-at, pose
   cues). Rolls are piecewise eased segments as in the prototype; growth and value changes are
   springs started at their action time. No memo across frames, so any frame renders alone
   (spec: deterministic frames).
4. **Camera as a target timeline.** `camera` actions form a list of targets (object id or x, zoom).
   The camera position is the target's position lag-filtered (average of the last ~0.4 s, as in the
   prototype), blended from the previous target over `dur` with ease-in-out. Zoom also scales by
   `(r0 / r) ** 0.25` while following a ball, which keeps a growing ball in frame. Breaks add a
   punch (≤ 6%) and a decaying shake (≤ 16 px). Before the first `camera` action, the camera follows
   the first ball, or frames x = 0.
5. **Rendering layers.** Screen-space sky + far ridge (parallax 0.12) → world layer (one CSS
   transform: anchor, zoom, slope rotation, camera offset) holding trees, ground, groove, blocks,
   shards, ball, figure, signs, props → screen-space snowfall (depth parallax) → screen-space pills
   (value, burst, chips, timelapse) projected from world coordinates so they stay upright →
   headline → grain. Colours: sky from `ink`, snow from the brand `bg`, bursts and pills from
   `accent`; `alert` blocks from a fixed warm red tint.
6. **Figure reuse.** The world figure renders the existing `Figure` component inside the world
   layer with a box whose bottom sits on the ground at its x. `walk` maps to `Figure.moves` with the
   box spanning the walk range. `throw` draws the item on a parabola from the hand to `to`.
7. **Validation in Python.** A table of kinds → allowed actions and required fields lives in
   `storyboard.py` next to the existing concept-scene validation; errors name world, beat, object
   and action. The kind list and action list are mirrored in TypeScript types.
8. **Remove the prototype.** `SnowballScene` is deleted once `WorldScene` reproduces the style
   test; the test storyboard is rewritten as a world run and used as the regression pilot.

## Risks / Trade-offs

- [Folding many actions per frame gets slow] → actions per world are tens, not thousands; fold is
  O(actions) per frame. Measure the pilot's render time against a `BeatScene` video of equal length.
- [Camera lag makes cues feel late] → lag ≤ 0.4 s and the camera looks ahead of a rolling ball.
- [World text overlaps the headline] → the world anchor sits at ~70% height and labels are drawn
  inside the world area; stills check it.
- [Users write one huge world run with no visual change] → the skill keeps "a new visual change
  every 2–3 s" and the 7 s per-beat WARN still applies per beat.

## Migration Plan

New scene type; existing storyboards are unaffected. The prototype `SnowballScene` is only used by
an unshipped test storyboard under `footage/` (gitignored), which is rewritten during the pilot.
