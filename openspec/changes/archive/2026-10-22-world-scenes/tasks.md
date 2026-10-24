# Tasks

## 1. World engine (Remotion)

- [x] 1.1 Create `tools/motion/src/world/` with the types (world, objects, actions) and the per-frame state fold (positions, radius, value, visibility, broken-at, pose cues, sky step). Verify: `npx tsc --noEmit` passes.
- [x] 1.2 Port the prototype's snow terrain, parallax ridge, trees and snowfall into a `snow` terrain coloured from the brand (ink sky, `bg` snow, accent bursts). Verify: a still of an empty world shows ground, ridge, trees and snow inside the frame.
- [x] 1.3 Objects: `block` (label, tag, tones, wobble, `push`, `pile`, `highlight`), `ball` (rolling marks without a face-like pattern, shadow, squash on impact), `sign`, `prop` (paper, towel, dumbbell, calculator), `callout`. Verify: one still per kind reads clearly at 9:16.
- [x] 1.4 Actions: `roll` (to x or block; arrival breaks the block), `break` + absorb + burst pill, `grow`, `value` + `chip`, `show`/`hide`, `fall`, `throw`, sky `timelapse`. Verify: the spec scenarios "Block gone after the hit", "Value lands on its cue" and "Months pass" hold on stills.
- [x] 1.5 Figure in the world: existing rig on the ground at its x (slope height), `pose` cues, `walk` via `moves`, held props. Verify: stills before/after a pose cue differ in the figure's box.
- [x] 1.6 Camera: target timeline (object or x, zoom, eased `dur`), lag, look-ahead, pull-back for a growing ball, punch + shake on breaks. Verify: in the pilot's stills the followed ball is fully inside the frame.
- [x] 1.7 `WorldScene` (terrain + world layer + screen pills + headline + grain) registered in `scenes/index.ts`; delete `SnowballScene.tsx`. Verify: `npx tsc --noEmit` passes and the style-test storyboard, rewritten as a world run, renders.

## 2. Storyboard engine

- [x] 2.1 `storyboard.py`: accept top-level `worlds`; validate kinds, ids, required fields, actions vs. kinds, targets, the `world` name, transitions inside a run (ERROR) and unused worlds (WARN). Verify: storyboards with each error from the spec produce the expected message; existing storyboards check exactly as before.
- [x] 2.2 Merge world runs when writing render props (sum durations, shift action `at` and headline words, carry `beats`). Verify: the spec scenario "Run merges into one render scene" (9.5 s; 1.0 s in beat 3 → 6.5 s) holds in `story_props.json`, and `check` prints the same starts and total as unmerged.
- [x] 2.3 Contact sheet: one settled still per beat of a run, labelled with the beat name. Verify: a 4-beat run gives 4 labelled frames.

## 3. Docs

- [x] 3.1 motion-graphics `SKILL.md`: "World scenes" section (when to choose a world over beats, the run rule, objects/actions tables, camera, a short example) and link it from "Story first"; remove the prototype's mention. Verify: the tables list every kind and action `check` accepts.
- [x] 3.2 `CLAUDE.md` routing: world scenes for metaphor-driven explainers. Verify: the row names `WorldScene`.

## 4. Verification pilot

- [x] 4.1 Rebuild the pilot reel under `footage/` (gitignored) as world runs (hook, setup, failed attempt with timelapse and towel, the study falling, the snowball breaking three blocks with values and chips, the caveat, the CTA sign) plus the end card. Run `check`, `stills`, `render --preview`; read the contact sheet and frames pulled from the MP4 at every break and beat; report duration, LUFS and true peak, and the render time.

## Workflow follow-up

- `/opsx:verify` then `/opsx:archive` once the user approves the pilot.
