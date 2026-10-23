# world-scenes Specification

## Purpose
Continuous, camera-driven worlds for narrated explainers: metaphor objects that move, collide,
break and grow across several narrated beats, so the story is told by objects rather than by cards.

## Requirements

### Requirement: World definition

A storyboard SHALL accept `worlds: {<id>: {terrain, objects}}`. `terrain` SHALL accept `{kind:
"snow", slope}` (degrees, downhill to the right; default 9). Each object SHALL have a unique `id`, a
`kind` (`block`, `ball`, `figure`, `sign`, `prop`, `callout`), an `x` along the ground (world units,
0 = the start) and kind-specific fields: `block` `{w, h, label, tag?, tone?: ice|alert}`, `ball` `{r,
value?, prefix?, suffix?, locale?}`, `figure` `{pose?, facing?, scale?}`, `sign` `{text, sub?}`, `prop`
`{item: paper|towel|dumbbell|calculator, label?}`, `callout` `{text, target}`. An object MAY set
`hidden: true` to start invisible.

#### Scenario: Unknown object kind

- **WHEN** a world has an object with `kind: "tree"`
- **THEN** `check` reports an ERROR naming the world, the object and the valid kinds

#### Scenario: Duplicate id

- **WHEN** two objects in one world share the id `b1`
- **THEN** `check` reports an ERROR naming the world and `b1`

### Requirement: World runs

A `WorldScene` SHALL name a `world`. Consecutive `WorldScene`s naming the same world SHALL form a
run that renders as one continuous scene: its duration is the sum of the beats, and object state and
camera carry from one beat to the next. Each beat SHALL keep its own narration clip, word timing,
cues (seconds from that beat's start) and headline phrases. A transition on any beat of a run except
the first SHALL be a `check` ERROR. A world that no scene uses SHALL be a WARN.

#### Scenario: Run merges into one render scene

- **WHEN** three consecutive `WorldScene`s of world `slope` last 3.0 s, 2.5 s and 4.0 s
- **THEN** the props written for the render hold one scene of 9.5 s for that run, and an action cued at 1.0 s in the third beat is at 6.5 s in it

#### Scenario: Headline across a run

- **WHEN** a run's second beat narrates "La rompes" and "rompes" is spoken 0.8 s into that beat, which starts 3.0 s into the run
- **THEN** the merged scene's words include "rompes" at 3.8 s

#### Scenario: Transition inside a run

- **WHEN** the second beat of a world run has a `transition`
- **THEN** `check` reports an ERROR naming the beat

#### Scenario: Timeline unchanged

- **WHEN** a storyboard's beats are turned into one world run without changing narration
- **THEN** `check` prints the same scene starts and the same total duration as before

### Requirement: World actions

A `WorldScene` SHALL accept `actions: [{at, target, do, ...}]`, `at` in seconds or a word cue. The
actions and the kinds they apply to SHALL be:
- ball: `roll {to: x | block id, dur? | arrive?}` (`arrive` is the arrival time, cues allowed; arriving at a block breaks it), `grow {by}`, `value {v, chip?}`
- block: `break {into?: ball id}`, `push {dx, dur}`, `pile {amount, dur}`, `highlight`
- figure: `pose {pose, prop?}`, `walk {x, dur?}`, `throw {item, to}`
- prop: `fall {to?: x, dur?}`, `hold {on: figure id}` (carried over the figure's head)
- any object: `show`, `hide`
- the world itself (`target: "sky"`): `timelapse {steps: [labels], dur}`
- the camera (`target: "camera"`): `camera {follow: id | x, zoom?, dur?}`

An unknown action, an unknown target, an action on a kind it does not apply to, or a cue that matches
no word SHALL be a `check` ERROR.

#### Scenario: Action on the wrong kind

- **WHEN** an action `{"target": "fig", "do": "roll"}` targets a figure
- **THEN** `check` reports an ERROR naming the beat, the action and the kinds `roll` applies to

#### Scenario: Unknown target

- **WHEN** an action targets `b9` and the world has no object `b9`
- **THEN** `check` reports an ERROR naming the beat and `b9`

### Requirement: Break and absorb

When a ball reaches a block (or a `break` names a ball in `into`), the block SHALL disappear at that
moment, its pieces SHALL fly out and then into the ball within 0.6 s, the ball SHALL grow afterwards
(by its `grow` factor, default 1.45), and a pill with the scene's `burst` text (default "¡Listo!")
SHALL rise over the block's place. The camera SHALL punch in and shake briefly on the impact.

#### Scenario: Block gone after the hit

- **WHEN** a ball rolls to block `b1` arriving at 2.0 s, and stills are taken at 1.9 s and 2.8 s
- **THEN** the block's label is visible in the first still and not in the second, and the ball is larger in the second

### Requirement: Ball value

A ball with `value` SHALL show a pill above it with the value formatted for its `locale` (with
`prefix`/`suffix`), upright whatever the slope. A `value` action SHALL count the pill up to `v` over
0.6 s from its `at`; with `chip`, a pill with that text SHALL appear beside the ball 0.5 s earlier and
fly into the value pill.

#### Scenario: Value lands on its cue

- **WHEN** a ball's value goes from 200000 to 280000 at `"@suma"` (2.0 s) with locale `es-CO` and prefix `$`
- **THEN** a still at 2.7 s shows "$280.000" over the ball

### Requirement: Camera

The camera SHALL follow its current target (an object or a fixed x) with a short lag, ease to a new
target or zoom over the action's `dur` (default 0.8 s), keep the followed object inside the safe box,
and pull back as a followed ball grows so it stays inside the frame. Parallax layers (far ridge,
snowfall) SHALL move slower than the ground.

#### Scenario: Ball stays in frame

- **WHEN** the camera follows a ball that grows to three times its radius
- **THEN** in every still of the run the ball's full circle is inside the frame

### Requirement: Sky timelapse

A `timelapse` SHALL cycle a sun and a moon across the sky once per step over `dur`, and show a pill at
the top of the world area with the current step's label.

#### Scenario: Months pass

- **WHEN** a timelapse has steps "Mes 1", "Mes 2", "Mes 3" over 3.0 s from 1.0 s
- **THEN** a still at 3.5 s shows the pill "Mes 3"

### Requirement: Figure in the world

A world `figure` SHALL use the existing stick-figure rig and poses, stand on the ground at its `x`,
follow the slope's height, and accept the same pose names and props as in `BeatScene`. `throw`
SHALL send the named item along an arc to `to` and leave it on the ground.

#### Scenario: Figure pose on a cue

- **WHEN** a figure has `pose: "push"` at `"@empujas"` and `"cheer"` at `"@rompes"`
- **THEN** stills just after each word differ in the figure's box

### Requirement: Deterministic frames

Every frame of a world SHALL be a function of time alone (no state kept between frames), so stills
taken at any time match the rendered video at that time.

#### Scenario: Still equals video frame

- **WHEN** a still is taken at 4.0 s and the same time is pulled from the rendered preview
- **THEN** both show the same objects in the same places (allowing for the preview's scaling)
