---
name: motion-graphics
description: Craft rules and workflow for motion graphics, and for videos made from scratch with no footage (explainers, kinetic typography, animated titles, data stories, promos, intros/outros, chapter cards), in 9:16, 16:9, 1:1 or 4:5. Use whenever the user wants a video without a camera, an animated explainer or title sequence, "make this move", or wants graphics/transitions/typography to look more professional. Covers timing, easing, choreography, typography, colour, transitions, pacing and sound, plus the storyboard engine (tools/storyboard.py) and its Remotion scene primitives, including narrated explainers (local text-to-speech, a headline that builds with the voice, a posable stick figure and cue-driven UI widgets). For Remotion API questions use the remotion-* skills; for talking-head shorts use short-form-pro (whose overlays follow the craft rules here).
---

# Motion graphics

The remotion-* skills explain how Remotion works. This skill is about taste: what makes motion
read as professional rather than as "PowerPoint with animations", and how to build a video from
an idea alone. Everything here runs locally and costs nothing.

**Engine:** `tools/storyboard.py` (check → stills → render → mix → loudness), with the Remotion
`Story` composition and scene primitives in `tools/motion/src/scenes/`.
**Templates:** `templates/storyboard.json` (`tools/new_project.py --type generated` copies it in) and
`templates/storyboard_explainer.json` for a narrated explainer (add `--explainer`; see below).

**Brand first.** The storyboard's `"brand"` loads `brands/<slug>/brand.json` (colours, fonts).
Read that brand's `brand.md` before planning. Its taste overrides the defaults below. With
`"brand": "none"`, use the neutral look and ask the user about style.

**Brand fonts.** A `fontFiles` weight is `400`, `"400"` or a variable font's range `"100 800"`. Give a
variable font its range, so bold uses the font's own weight axis instead of a faked bold; `brand check`
reports each file's weight or range. A role the kit leaves unset (`serif`, `sans`, `mono`) uses the
kit's `sans`, else its first font file; the neutral faces only apply when the kit names no font. Before
a final render, resolve `brand check` `warnings` (set the weight or range the file provides). A font
that doesn't load fails the render with `Font did not load: <style> <weight> "<family>" (<file>)`.

## Workflow: a video from scratch

1. **Project.** Run `uv run tools/new_project.py <name> --brand <slug|none> --type generated --platforms <list> --language <code>`.
   The aspect comes from the first platform: reels/tiktok/shorts → 9:16, youtube → 16:9, linkedin → 4:5, x → 1:1.
2. **Brief.** Ask, or infer, four things: the **one sentence** the viewer should remember, the audience,
   the platform (which sets the aspect and length), and the call to action. Without that sentence, the video has no spine.
   Then write the **story spine** before choosing any graphic (see "Story first" below).
3. **Beat sheet.** Write one idea per scene, in a table:
   `# | dur | scene type | on screen | narration (if any) | transition | SFX`.
   Present it in plain English and **wait for approval**. This is cheap to change now and expensive later.
4. **storyboard.json.** Write it from the approved table. Then run
   `uv run tools/storyboard.py <edit> check`. It must show no ERRORs. Fix every WARN, or say why it's fine.
   Check flags reading time, narration that's too long, scenes over 7 s, SFX closer than 0.3 s,
   missing assets, and overlay components used outside 9:16.
5. **Stills.** Run `uv run tools/storyboard.py <edit> stills`. It writes `edit/stills/contact.png`
   (each scene once settled, plus the midpoint of every transition). Read the PNG. Fix layout,
   size and contrast here, before any full render.
6. **Preview.** Run `uv run tools/storyboard.py <edit> render --preview`. It writes `edit/preview.mp4`
   at 720p in about 20 s per 25 s of video. Verify (see the end of this file), then show the user.
7. **Final, only after approval.** Run `uv run tools/storyboard.py <edit> render --export <platform>`.
   The frame is full-res, the encode is `DELIVERY_X264`, and the result is copied to `exports/<project>_<platform>_<date>.mp4`.
8. Log the decisions in `edit/project.md`.

Another aspect from the same storyboard: copy `storyboard.json` to `storyboard_<x>.json`, change
`aspect`, and point the tool at that file. The primitives re-lay themselves out. Always check the
stills, because line breaks change.

## Narrated explainer

A voice tells a short story; each spoken phrase builds on screen as a headline in time with it;
UI-style cards and recurring objects show what the words say; a stick figure acts where a person
doing something is the clearest picture. Vector only: no photos, no human likeness. One scene type
does it all: `BeatScene`.

### Story first
The story is the product; the figure and the widgets only serve it. Write the spine before any
graphic, and present it above the beat sheet:

- **Spine:** setup (who, what they believe or want) → tension (what goes wrong, what it costs) →
  turn (the insight, the evidence) → payoff (what changes, shown happening) → CTA. Every beat
  moves one of these forward; a beat that only restates the last one is cut.
- **A concrete case beats an abstract claim.** One person, one situation, real-looking numbers
  ("three debts: $600.000, $4 M, $18 M") that the viewer can follow from beat to beat.
- **Show the mechanism.** If the idea works in a certain way (money rolling from one debt to the
  next, a habit compounding), animate that process with objects and numbers that change, rather than
  a character reacting to it.
- **Recurring visual protagonist.** Pick the object that carries the story (a card, a list, a
  counter, a bar) and keep it across beats so its state changes are the plot.
- **The figure is optional, per beat.** Use it when a human action is the clearest image (reading
  the source, giving up, celebrating) and drop it (`figure` omitted) when the object or the number
  is the hero. As a guide, the figure appears in at most about half the beats. Never add it to fill
  space. In a beat with no figure and every widget in `main`, `main` takes the whole area under the
  headline (no empty band); or put a second widget in the `figure` slot.
- Beat sheet columns for an explainer: `# | story role | narration | hero (object/widget) | figure (or —) | cue`.
- **When the idea has a physical metaphor** (a snowball, a ladder, a leak, a road), tell it in a
  **world** instead of beats with cards: see "World scenes" below. Prefer a world whenever the story
  is about something changing over time (growing, breaking, piling up, moving forward).

**Setup, once:** `uv sync --group gen` (Kokoro-82M, Apache-2.0 weights, fully local: through `mlx-audio`
on Apple Silicon, through the reference `kokoro` package on PyTorch CPU on Linux/Docker; ~0.37 GB on a Mac:
330 MB weights + ~0.5 MB per voice used, the spaCy English model and the bundled `espeak-ng` phonemiser).
Word times use the local Whisper that's already cached (on Linux also `uv sync --group asr`). Same voices
on both; a clip made by one backend is re-synthesised by the other (the sidecar records `backend`).

**Workflow:** `new_project.py <name> --type generated --explainer --platforms <p> --language <code>` →
write the beat sheet (one row per beat: narration, pose, widget, cue word) and get it approved →
`storyboard.py <edit> voice` (synthesises each scene's clip, times its words) → `check` (durations
now come from the clips; the `vo@` column is where each voice starts, `words` how many aligned) →
`sheet poses` / `sheet widgets --aspect <a>` when you change the rig or a widget → `stills` → `render --preview`.
Edit a line and `check` errors with "run `voice`"; only changed lines are re-synthesised.

Measured on an M5 (warm): Kokoro 0.1–0.4 s per 2–5 s clip (the first clip of a run takes 1–3 s
while the pipeline loads); Whisper ~0.7 s per clip after a ~4 s model load; a 13 s preview renders in ~8 s.

### Writing
- **One idea per beat, beats of 2–4 s.** A beat that needs two sentences is two beats.
- **Mix sentence lengths.** Three long lines in a row sound like a reading; a two-word line lands.
- **`*emphasis*` at most once per phrase** (`check` warns on more): the word the viewer must keep.
- **`|` forces a phrase break** ("One page, one goal, | *one afternoon.*"). Phrases also break after
  `.?!`, and a run over 7 words splits evenly (8 → 4 + 4).
- **`voice.pronounce`** respells names the voice gets wrong (`{"SaaS": "sass"}`); the headline keeps
  the script's spelling. List every substitution in `project.md`.
- Numbers: write them the way they should be said ("twelve hundred"); the widget shows the digits.
- **Punctuation marks the pacing, briefly.** `voice` synthesises each sentence or clause on its own
  and joins them with short silences: 0.18 s after `.` `!`, 0.2 s after `?`, 0.25 s after `…`,
  0.12 s after `:` `;`. Keep them short: longer pauses (0.3–0.45 s) were measured and rejected as
  hesitant and hard to follow. `|` only breaks the headline (no pause); a comma is a breath inside a
  piece; a one-word piece ("Ojo:") is kept with the next one, as a comma.
- **Questions don't rise.** Kokoro ends a yes/no question with the same falling pitch as a
  statement (measured), so "¿Tienes claro…?" sounds like an assertion. Write it as a statement or
  a condition ("Si no tienes claro cuánto debes…, comenta…"); wh-questions ("¿Por qué funciona?")
  fall naturally and are fine.
- **Keep the voice at `speed` 1.0.** Slowing it (0.85) made a reel drag and words blur into each
  other; aim for ~3–3.5 words/s and shorten lines instead. `check` warns above 4 words/s.
- **Spanish is Latin American by default** (`lang: "es"` phonemises with espeak `es-419`: seseo,
  "doce" → /ˈdose/, "motivación" → /motiβaˈsjon/). Kokoro's own default is Spain (/ˈdoθe/), which
  sounds odd to most audiences; use `lang: "es-es"` only for Spain.
- **Years and long numbers stumble** ("dos mil… doce": a gap inside the number). Keep them on
  screen and out of the voice unless the number is the point.
- **No foreign names or titles in the narration.** A respelled English title ("Journal of
  Marketing Research" for a Spanish voice) is read word by word with gaps; say it in the voice's
  language ("un estudio publicado en 2012") and put the exact name on screen and in the sources.
- **Line ends are punctuation too.** End each beat's line with the mark the sentence needs (`,` when
  it continues into the next beat), because the pause between beats is taken from it.
- **Measure the pauses** (you can't listen): every silence ≥ 60 ms in `audio/narration_track.wav`
  (decode with ffmpeg: it's 24-bit) next to the script's punctuation. Same mark, same pause; a long
  gap with no mark is the voice hesitating, so rephrase that spot.
- **Verify intelligibility**, since you can't listen: transcribe each clip with the local Whisper
  and compare to the script. Missing words mean garbled audio; missing full stops mean the pauses
  are lost.

### Picture
- **The story's object is the hero; the figure is a supporting actor.** When the figure is in a beat,
  it changes pose on the beat's key word (`{"pose": "cheer", "at": "@done"}`); a figure standing
  still beside a widget adds nothing, so drop it.
- **Act the script out.** Read each line for a verb or an object and stage it: "as the book
  shows" → `read` with the `book`; "you want to buy it" → walk to a `ProductCard` and `reach`; "wait a
  day" → `wait`; "fear" → `scared`; "head or heart" → a `Balance` that tips on each word. Aim for 2–3 pose
  changes in a 4 s beat, each on its word. A badge is the fallback when nothing in the line can be shown.
- **Sequence, don't stack.** When a beat needs several elements, give the earlier one an `out` on
  the cue where the next one enters (same slot), so there's still one hero at a time.
- **Recurring objects carry the story:** the same `ProductCard` can be shown, locked (`lockAt`) and
  made to vanish (`out`) across consecutive beats.
- **Numbers move while they're said:** a `Counter` from `"@first-word"` to `"@last-word"` of the number.
- **A stamp for a negation** ("we *skip it*", "not this"): `Stamp` on the cue, over the thing negated.
- **Light/dark switch when the mood flips** (problem → answer, before → after). One dark beat per
  4–6 is plenty.
- **Hard cuts by default** between beats; a transition only for a real change of chapter.
- **`"progress": true`** for anything over ~20 s.
- Cue an element on its word; the engine resolves `"@word"` to the moment it's spoken (`@word#2`
  for the 2nd time, `@word+0.2` / `@word-0.1` to nudge). A cue that matches no word is an ERROR.

### Reference
`BeatScene` props: `bg: light|dark`, `figure`, `widgets[]`, `headline` (default true), `headlineSize`.
Words come from the narration automatically. Slots: `main` (widgets' default), `side`, `figure`.
9:16, 1:1 and 4:5 stack them (headline, `main`, figure band; a `side` widget takes the left of the band);
16:9 puts `main` on the left two-thirds and the figure on the right.

Poses (`tools/motion/src/explainer/poses.ts`; check them with `sheet poses`):

| pose | reads as | default prop |
|---|---|---|
| `stand` | neutral, listening | |
| `wave` | hello, goodbye, "you" | |
| `cheer` | win, done, launch | |
| `point` | "this", "here", look at the widget | |
| `shrug` | "who knows", a question | |
| `slump` | the problem, a loss, tired | |
| `think` | wondering, planning | |
| `type` | working, building | `desk` (desk + laptop) |
| `push` | effort, shipping, moving something | `box` |
| `shout` | announcing, marketing | `megaphone` |
| `read` | a book, a source, studying | `book` |
| `wait` | patience, "wait a day" (hands behind the back) | |
| `reach` | wanting, grabbing, "buy it" | |
| `scared` | fear, a shock, a risk | |
| `walk` | going somewhere (played automatically while a move runs) | |

Props: `desk`, `megaphone`, `box`, plus hand-held `book`, `phone` and `bag` (a shopping bag), which
follow the front hand. Set any of them on a pose cue: `{"pose": "cheer", "at": "@bought", "prop": "bag"}`.

Figure: `{pose}` or `{poses: [{pose, at, prop?}]}`, `facing: right|left`, `slot`, `scale`, `x`
(0–1 start position in its slot, default 0.5) and `moves: [{x, at, dur}]` (walks there over `dur`,
default 0.8 s, facing the way it goes). Pose changes spring in within 0.4 s; it sways and breathes
while it holds. `prop: null` drops a default prop. With a `side` widget the figure's slot is half the
band, so moves are short; use them in beats without a side widget for a visible walk.

Widgets (`tools/motion/src/explainer/widgets/`; check them with `sheet widgets --aspect <a>`). All
take `at` (entrance), `out` (exit), `slot`; times accept cues:

| widget | for | key props |
|---|---|---|
| `Terminal` | a command, a build, "it just runs" | `title, lines[{text, at, kind: cmd\|out\|ok}]` (cmd types at 22 chars/s) |
| `Checklist` | steps, a plan, what's done / dropped | `title, items[{text, at, state: todo\|done\|struck}]` |
| `Stamp` | a negation, a verdict | `text, at, color, rotate` |
| `Counter` | a number said aloud | `label, from, to, start, end, prefix, suffix, decimals, spark` |
| `Gauge` | a share, a score | `value` (0–100), `label, fillAt` |
| `Stopwatch` | time passing, "in 2 minutes" | `seconds, start, end, label` |
| `FunnelBars` | a funnel, a ranking | `title, rows[{label, value}], drop` (shows % lost) |
| `TileGrid` | "12 of 100" | `count, cols, highlight, colors, label` |
| `Badge` | a status, a result | `text, tone: ok\|alert\|neutral, icon` |
| `ProductCard` | something to buy, a temptation | `name, price, icon, button, pressAt, pressedText, lockAt, lockText` (`out` shrinks it away) |
| `Calendar` | "tomorrow", a deadline, days passing | `title, pages[{label, at, sub}]` (flips to each page on its cue) |
| `Balance` | X vs Y, a trade-off, head vs heart | `left, right, leftIcon, rightIcon, tilts[{to: left\|right\|level, at}]` |
| `ThoughtBubble` | what the figure thinks or wants | `icon` and/or `text`; trails dots towards the figure (`tail` overrides) |

Widget text is never under 28 px; each card fits its slot in every aspect.

## World scenes

One continuous world seen through a moving camera: the metaphor's objects move, collide, break and
grow while the voice tells the story. This is the default for a narrated explainer whose idea has a
physical image; `BeatScene` + widgets is for lists of facts, not for a story.

**The run rule.** Each narrated line is still its own scene (`"type": "WorldScene"`, its own
`narration`, cues and headline phrase), with `"props": {"world": "<id>", "actions": [...]}`.
Consecutive `WorldScene`s naming the same world render as **one** continuous scene: time, camera and
every object's state carry over (a broken block stays broken). No `transition` inside a run (`check`
errors); a run ends at the next non-world scene, which may have a transition (e.g. a fade to the end card).

**The world** lives at the storyboard top level: `"worlds": {"<id>": {"terrain": {"kind": "snow",
"slope": 9}, "objects": [...]}}`. World units: `x` along the ground (0 = start, ~1000 units ≈ one
screen width at zoom 1), ground at y = 0. Objects with `"hidden": true` appear on `show` (with a spring).

| kind | is | fields |
|---|---|---|
| `block` | a labelled obstacle (a debt, a task, a wall) that can break | `x, w, h, label, tag?, tone: ice\|alert, burst?` (pill text when it breaks) |
| `ball` | the thing that rolls, gathers and grows | `x, r, grow` (×radius per block absorbed, default 1.45), `value, prefix, suffix, locale` (pill over it) |
| `figure` | the stick figure, standing upright on the slope | `x, pose, facing, scale` |
| `sign` | a post planted in the ground (the CTA) | `x, text, sub` |
| `prop` | `paper`, `towel`, `dumbbell`, `calculator` | `x, item, size` |
| `callout` | a speech bubble pointing at an object | `text, target, dx, dy` |

Actions: `{"at": <s or "@cue">, "target": <id | "sky" | "camera">, "do": <action>, ...}`.

| do | on | does |
|---|---|---|
| `roll` | ball | rolls to `to` (an x, or a block id) arriving at `arrive` (a cue: land the impact on the word) or after `dur`. Reaching a block **breaks** it: shards burst, fly into the ball, the ball grows, a lime ring + burst pill, camera punch + shake; then it rolls on through |
| `value` | ball | counts the pill up to `v` over 0.6 s; `chip` ("+$80.000") pops 0.5 s before and flies into the pill |
| `grow` | ball | grows by `by` |
| `break` | block | breaks without a ball (`into` a ball id to absorb) |
| `push` | block | barely moves (`dx`, `dur`) with a shudder: effort that gets nowhere |
| `pile` | block | snow piles on top (`amount`, `dur`): time passing on something stuck |
| `highlight` | block | pulsing red outline (until `until`) |
| `pose` | figure | `pose`, `prop` (same names as `BeatScene`) |
| `walk` | figure | walks to `x` (walk cycle, faces the way it goes) |
| `throw` | figure | throws prop `item` on an arc to `to` ("tirar la toalla") |
| `fall` | prop | falls from the sky to `to` (a source, a letter, an idea arriving) |
| `hold` | prop | held over the head of figure `on` (lifting a weight) |
| `show` / `hide` | any | appear (spring) / vanish |
| `timelapse` | sky | sun and moon cycle once per step, a pill shows each label (`steps`, `dur`) |
| `camera` | camera | `follow` an object id or hold `x`, `zoom` (default 1.3), eased over `dur` |

Camera craft: frame the hero of each line (`follow` the block being talked about, the figure when
it acts, the ball while it rolls); pan with `x` keyframes to reveal a layout ("three debts":
show each block as the camera reaches it); pull back (`zoom` 0.85) for overviews, push in (1.3–1.4)
for a moment. A followed ball is framed ahead of its motion and the camera pulls back as it grows.
Change the picture every 2–3 s: a camera move, a pose, an object appearing, an impact.

```json
"worlds": {"slope": {"terrain": {"kind": "snow"}, "objects": [
  {"id": "ball", "kind": "ball", "x": 380, "r": 55, "value": 200000, "prefix": "$", "locale": "es-CO"},
  {"id": "small", "kind": "block", "x": 900, "w": 240, "h": 210, "tag": "Card", "label": "$600"},
  {"id": "fig", "kind": "figure", "x": 250}]}},
"scenes": [{"name": "push", "type": "WorldScene", "bg": "dark", "narration": "Start with the smallest. | You *break* it.",
  "props": {"world": "slope", "actions": [
    {"at": "@Start", "target": "fig", "do": "pose", "pose": "push", "prop": null},
    {"at": "@Start", "target": "camera", "do": "camera", "follow": "ball"},
    {"at": "@smallest", "target": "ball", "do": "roll", "to": "small", "arrive": "@break"}]},
  "sfx": [["impact", "@break", -14], ["sparkle", "@break+0.35", -18]]}]
```

Engine: `tools/motion/src/world/model.ts` (state per frame, pure functions of time) and
`scenes/WorldScene.tsx` (layers). New terrains or object kinds go there, mirrored in `check`.

## Craft rules

### 1. Timing (at 30 fps)

| Motion | Frames | Seconds |
|---|---|---|
| UI micro-motion (tick, pop, toggle) | 6–10 | 0.2–0.33 |
| Element entrance | 10–18 | 0.33–0.6 |
| Exit (always shorter than the entrance) | 6–10 | 0.2–0.33 |
| Scene transition | 12–20 | 0.4–0.65 |
| Stagger between words | 2–3 | |
| Stagger between list items or bars | 4–8, or on the narration cue | |

- **Hold to read.** Something must stay still long enough to read: about 0.8 s plus 4 words per second of
  on-screen text, and longer if there's narration. `check` enforces this.
- **Scene length.** Short-form: 2–4 s, with a new visual every 2–3 s. Long-form: 4–8 s. Past ~7 s,
  add a beat inside the scene (a new item, a count-up, a camera move), or split it.
- **Land on the word.** With narration, cue an element about 0.1 s *before* its word, so the eye arrives as the ear does.

### 2. Easing

- **Entrances use ease-out** (`easeOut` in `anim.ts`, `bezier(0.16, 1, 0.3, 1)`): fast in, gentle settle.
- **Exits use ease-in**, and are shorter. **Moves between two states use ease-in-out** (`easeInOut`).
- **Springs** (`enter()` in `anim.ts`, damping 12–16) suit playful or physical things: pops, cards, icons.
  Low damping (<10) wobbles and looks cheap unless the brand is deliberately bouncy.
- **Linear only for** camera drifts and Ken Burns moves (near-constant speed reads as a camera),
  progress bars filling in real time, and loops.
- Never use CSS transitions. All motion comes from `useCurrentFrame()` with `interpolate`/`spring`.

### 3. Choreography and hierarchy

- **One hero per scene.** Decide what the eye must see first. It enters first, it's the biggest,
  and it gets the strongest motion.
- **Enter in reading order:** kicker → title → rule → supporting line → details. Secondary elements
  enter smaller, later and softer.
- **One emphatic motion at a time.** Two things springing at once split attention. Stagger them.
- **Never fully static.** A frame with zero motion for over a second reads as frozen. Background
  drift and film grain (`grain` 0.3–0.5) keep a scene alive under still text. A Ken Burns move keeps a still alive.
- **Dim what's done.** In lists, earlier items fade to about 45% when a new one lands (`ListScene` does this).

### 4. Typography

- **Two families at most:** the brand serif for display, the sans for support. Everything comes from `useBrand()`.
- **Minimum sizes** (short side 1080 px): display ≥ 96 px, supporting text ≥ 44 px in 9:16
  (≥ 40 px in 16:9), and kickers ≥ 30 px, uppercase with 0.2 em tracking.
- **≤ 7 words per line, ≤ 3 lines.** Break titles with `\n` at natural phrase boundaries.
- **One emphasis per scene** (`emphasis`: the accent colour, plus italic in serif). An emphasised
  phrase never breaks across lines; the engine keeps it together.
- Sentence case for titles. Uppercase only for small, tracked kickers.
- Numbers use `tabular-nums`, so a counting value doesn't jitter.

### 5. Colour and rhythm

- Scene tones are `light`, `dark` and `accent`. **Alternate tones to create rhythm**, and use a tone
  change to mark a new chapter. Use the accent background sparingly: once or twice a video, on the punch.
- Long text is never set in the accent colour. Text uses `fg`/`muted` from `usePalette(bg)`, which switches with the tone.
- Text over images needs a scrim (`ImageScene` adds one under its title) or `darken`.

### 6. Transitions

| Type | When |
|---|---|
| `cut` (no `transition`) | The default between closely related beats: fastest and most "edited" |
| `slide` | The next item in a sequence. Direction follows progress: `from-right` forward, `from-bottom` for vertical stacks |
| `wipe` | A reveal, or before → after |
| `zoom` | Going deeper: into a detail, a stat, a punch |
| `fade` | A change of mood or time, and the ending |
| `flip`, `iris`, `clockWipe` | Rarely: playful, or "time passes" |

Use **2–3 transition types per video at most**, and keep one direction. A different transition on
every cut is the clearest amateur tell. A transition lasts 0.4–0.65 s and overlaps both neighbouring scenes.

### 7. Data

- **One number per `StatScene`.** It's a headline, not a chart. The count-up finishes before the label rises.
- **`BarChart`:** one series, ≤ 6 bars, and `highlight` on the bar the story is about (accent; the
  others are recessive ink). Values are text, never in the bar colour. Never use a dual axis.
- **Don't echo.** If narration says "three times faster", show 1 h vs 3 h, not the sentence.

### 8. Images

- **A promo animates the product's mechanism.** Show what the product *does* with code-drawn motion
  (`NetworkScene`, `IsoOffice`, widgets), not screenshots with a pan. A capture is at most a short
  proof beat (≤ 2 s, once or twice per video), never the backbone. The stick figure is a rare
  accent in a promo, not a fixture in every beat.
- `ImageScene` always moves. Put `focus` on the subject. `amount` ranges from 0.06 (calm) through 0.12 (default) to 0.2 (dramatic).
- **Alternate move directions** across consecutive image scenes (in → left → out), never the same move twice in a row.
- Only use images the user has rights to: their own captures (`site_capture.py`), photos, or
  (later) locally generated images. Never use stock scraped from a website.

### 9. Sound

- Every SFX is tied to something visible: a landing, a tick, a transition. Use at most one per beat,
  and keep them ≥ 0.3 s apart. Vary the vocabulary (the `sfx_synth.py` list is in the short-form-pro skill).
- Music beds come only from licensed music (`assets/music/`, which records its licence). Without
  narration, the music carries the mix. With narration, `duck` sidechains it under the voice.
  The mix is normalised to `lufs` (−14).
- **Music-driven pieces:** get a beat grid with `librosa.beat.beat_track` and put scene starts on beats.
  Snap durations so each `start` lands on a beat. Transitions overlap, so compute starts with `Story.timeline()`.

### 10. Anti-patterns (if the video does this, fix it)

- **Animated bullet points:** every beat is the headline plus one card (list, gauge, counter,
  badge) that pops in, and each cut resets the frame. That is a slide deck, not a story. Find the
  visual metaphor, build the world it lives in, and let the same objects move, collide, grow and
  break across beats while the camera travels. Cards are at most an occasional insert for a number.
- Everything enters at once, or everything bounces.
- Text arrives and leaves before it can be read.
- A different transition on every cut, or slides in random directions.
- Linear easing on UI entrances.
- Five bright colours, or accent-coloured paragraphs.
- Full sentences on screen while narration says the same sentence.
- A static frame held for more than a second with nothing moving.
- Tiny supporting text (under 40 px) or content in the platform UI zones.

## Storyboard format

```json
{"aspect": "9:16", "fps": 30, "brand": "none", "grain": 0.35, "lufs": -14,
 "scenes": [{"name": "hook", "type": "KineticType", "duration": 2.9, "bg": "dark",
             "transition": {"type": "slide", "direction": "from-bottom", "duration": 0.45},
             "props": {...}, "narration": "spoken line (planning + checks)",
             "sfx": [["tap", 0.0, -16]]}],
 "voice": {"lang": "en", "preset": "af_heart", "speed": 1.0, "pronounce": {}},   // optional: narrate
 "progress": true,
 "events": [{"type": "Flash", "start": 12.0, "duration": 0.3, "props": {}}],
 "audio": {"voice": "audio/vo.wav", "voice_start": 0, "music": {"file": "assets/music/…", "db": -6, "duck": true},
           "sfx": [["whoosh", 4.2, -18]]}}
```

- A `transition` belongs to the scene it leads **into**. Scene `sfx` times are relative to that scene's
  start; `audio.sfx` times are absolute. All `at`/time props inside `props` are seconds from the scene start.
- Asset paths (images…) are relative to the edit dir, or to the repo root (`assets/…`). They're staged automatically.
- `events` sit on top of every scene on the global timeline: `Flash`, `Captions`, or any scene primitive
  (it draws no background there; for a lower third, use a transparent `TitleCard` or `KineticType`).
- `ImageScene` defaults to `bg: "none"`. Every other scene defaults to `light`.
- With a `voice` block, each scene's `narration` is spoken (or `narration_audio` is used as a recorded
  clip), and `duration` may be omitted or `"auto"`: transition-in + clip + tail. Between two
  narrated beats joined by a cut the tail follows the line's last mark, so a full stop sounds the same
  across beats as inside one (≈0.35 s; `:` ≈0.22, `,` ≈0.2); 0.3 s before a transition or silence. `speed`
  per scene overrides the voice's. Without it, `narration` is a planning note, as before.
  Use one voice source: `audio.voice` or narrated scenes, not both.

## Scene primitives (`tools/motion/src/scenes/`)

All of them work in 9:16, 16:9, 1:1 and 4:5. They lay out inside the aspect's safe box
(`SAFE_BY_ASPECT` in `layout.ts`) and take colours from the scene's `bg` tone.

| type | use for | key props |
|---|---|---|
| `TitleCard` | opening, chapter, end card | `kicker, title` (`\n` = line), `emphasis, sub, align` (16:9 defaults to left), `size` |
| `KineticType` | the words are the picture: hooks, punch lines, quotes | `lines[{text, at?, emphasis?, size?}]`, `style: rise\|pop\|fade\|blur\|slam\|type`, `font: serif\|sans`, `uppercase, align, stagger` |
| `StatScene` | one headline number | `value, from, prefix, suffix, decimals, locale, kicker, label, max` (adds a progress bar), `countStart, countEnd` |
| `BarChart` | compare ≤ 6 values | `kicker, title, bars[{label, value, highlight}], unit, prefix, decimals, max, start, stagger, grow` |
| `ListScene` | steps, reasons, features | `kicker, title, items[{text, icon?, at?}], marker: number\|check\|icon\|dot, dimPrevious` |
| `ImageScene` | any still: captures, photos, generated art | `src, move: in\|out\|left\|right\|up\|down\|none, amount, focus{x,y}, kicker, title, darken, mono` |
| `BeatScene` | a narrated explainer beat (see "Narrated explainer") | `bg, figure, widgets[], headline, headlineSize` |
| `NetworkScene` | integrations, routing, "everything through one hub" | `kicker, title, emphasis, nodes[{id, label, color?, icon?}], hub{label?, icon?, color?}, chaos, connect, chips[{node, text, at}], messages[{from, to, at, lock?}], log[{text, at}]` |
| `IsoOffice` | a team or agents visibly doing the work; handoffs; "watch it again" | `kicker, title, emphasis, cols, rows, desks[{id, u, v}], agents[{id, label, color?, at?, pos}], walks[{agent, to, at, dur?, carry?}], bubbles[{agent, text\|icon, at, until?}], replay{at, dur, to?}` |
| `WorldScene` | a story told by objects in one continuous world (see "World scenes") | `world` (id from top-level `worlds`), `actions[]`, `burst` |
| `EndCard` | closing card with the brand's logo and a call to action | `logo` (SVG/PNG path), `logoHeight, title, tagline, button, url` |

`KineticType` styles: `rise` is masked word-by-word, typeset and editorial (the default). `pop`
springs words in, playful and social. `blur` is soft and premium. `fade` is calm and documentary.
`slam` shows one big line at a time, replacing the last, for hooks. `type` is a typewriter with a
caret, for prompts and searches.

The 9:16 overlay components from short-form-pro (`RingStat`, `PhoneMockup`, `Receipt`…) also work as
scene types, **only in 9:16**. `check` rejects them in other aspects.

Icons: `LineIcon` kinds in `components/icons.tsx` (book, cart, heart, brain, moon, speech, bulb, mail, receipt, calendar, search,
person, check, spark, send, chart, cv, plane). Use line icons, not emoji.

### Every component ships a props schema

Each scene and overlay component has `<Name>.schema.json` beside its `.tsx` (`Captions` excepted: the
engine builds it). Short-form `check` validates event props against it, resolves and range-checks its time
props, and checks every entrance finishes before the event ends; `stills` uses it for the legibility probe and
caption placement; the `schema` job op exports it for callers. When you add a component or change its props,
update the schema in the same change:

- Draft one from the TypeScript types: `cd tools/motion && node scripts/prop_keys.mjs --skeleton <Name> >
  src/<dir>/<Name>.schema.json`, then annotate it (format in `tools/overlay_schema.py`):
  `x-layout: "full"` (draws across the safe area: scenes) or `"float"`; `x-time: "event"` on every prop that is
  seconds from the event's start, `"duration"` for a length in seconds, `"frames"` for frames; `x-text: true` on
  every string the viewer reads; `x-cues` for entrances (the default cue times and entrance length, copied from
  the component's own defaults); ranges and `default`s where the component has them.
- `uv run python -m unittest tools.tests.test_overlay_schema` fails, naming the component and key, when a
  declared prop is missing from the schema or the schema has a key the component doesn't declare, and when a
  registry or scene component has no schema. Pin new default cues with a test there, as for `ListScene`.

### Promo scenes

Every time below is seconds from the scene start or an `@word` cue. `check` rejects ids that don't
exist (message/chip nodes; walk, bubble and carry agents; desks), unknown icons, and a `replay` that
ends after its scene.

- **`NetworkScene`.** Nodes drift in `chaos` (tangled dashed lines, packets that never arrive,
  blinking error marks) until that time, then at `connect` (default: `chaos`, or 0) they ease into a
  ring around the `hub`, staggered, and spokes draw in. Without `chaos` the ring is there from the
  start. Without a `hub`, nodes link to their neighbours and messages travel straight. A message is
  a packet (envelope, or a lock with `lock: true`) that travels 0.9 s: half to the hub, half out to
  `to`, lighting each spoke and pulsing on arrival. `chips` pin a mono pill (e.g. "ID") to a node.
  `log` lines print in a ticker under the ring (beside it in 16:9), newest highlighted, older dimmed.
  Up to 8 nodes read well; node colours cycle a neutral palette unless given.
- **`IsoOffice`.** A `cols × rows` floor (default 8×6) with two back walls. `desks` are tiles
  `{id, u, v}` (0-based); omit them for `desk1…deskN` along the back rows (N = max(4, agents)). A
  position (`pos`, a walk's `to`) is a desk id (the agent stands at its front, at work, and its
  monitor lights up) or a tile `[u, v]`. Walks are straight lines (eased, default 1 s); `carry: true`
  holds a document on that walk (a handoff). Bubbles show `text` or an `icon` over the head from
  `at` to `until`. For portrait frames, a smaller floor (6×5) makes everything bigger.
- **Replay clock.** `replay{at, dur, to}` shows a scrub bar while the floor's content clock runs back
  from `at` to `to` (default 0) over the first 60% of `dur`, then forward again to `at`. After the
  replay the content clock runs `dur` behind real time. **Write every cue in narration time as
  usual**: the engine pauses the content for the replay, it doesn't move your cues. Walks, bubbles
  and entrances all reverse because everything is a function of that clock.
- **`EndCard`.** Logo (from `brands/<slug>/logos/`) springs from 60% over a soft glow, then title,
  tagline, button (pill with a drawn arrow: `ink` on light/accent, `accent` on dark) and url rise in,
  6 frames apart. At 0.2 s only the logo shows; by 1.5 s everything has landed.

### Adding a primitive

Put it in `src/scenes/` and register it in `SCENES` (`scenes/index.ts`). Lay it out with
`useFrameLayout()` (safe box, aspect), colour it with `usePalette(bg)`, set type with `useBrand().fonts`,
and drive motion with `useCurrentFrame()`. Size it for every aspect (`aspect === "16:9" ? … : portrait ? … : …`).
Add a row to the table above, then check stills in 9:16 **and** 16:9.

## Verify before presenting

1. `check` shows no ERRORs. Explain any WARN you kept.
2. Read the contact sheet from `stills`, then frames pulled from the **rendered MP4** at every transition
   midpoint and at each scene once settled (`ffmpeg -ss T -i preview.mp4 -frames:v 1 f.png`). Look for:
   text clipped or in UI zones, scene edges showing during a transition, wrong line breaks, and contrast.
3. The rendered duration matches the planned total (`render` prints both).
4. Loudness: `render` prints integrated LUFS and true peak. Report them. You can't listen, so say so.

## Gotchas

- `stills` and `render` re-bundle each time (about 5 s). Stills reuse the bundle within a run.
- The intermediate ProRes for a final is large: about 1 GB per minute at 1080x1920.
- A transition must be shorter than both of its neighbouring scenes (`check` errors otherwise).
- Remotion is free for teams of up to 3; larger companies need a licence.
- `voice` needs `uv sync --group gen`; a plain `uv sync` removes the group again. `check`, `stills`
  and `render` work without it once the clips exist.
- Kokoro's `speed` isn't linear: 1.2 is only ~8–10% shorter, 1.5 ~30–40%. Prefer shorter lines to speed.
- Clips live in `edit/audio/narration/<scene>.wav`, shared by every storyboard in that edit dir. An
  aspect copy (`storyboard_16x9.json`) reuses them; a **language copy needs its own project**.
  Set `locale` on `Counter`/`FunnelBars` to match (`"es-ES"`: 12.000, and no separator under 10 000).
- Languages: en (US), en-gb, es, fr, it, pt-br, hi (`uv run tools/gen/voice.py --list`). Spanish (`es` = Latin America, `es-es` = Spain) has
  three voices (`em_alex`, the default, `ef_dora`, and `em_santa`, a novelty voice); for a better Spanish read, record and use `narration_audio`.
