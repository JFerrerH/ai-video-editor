---
name: motion-graphics
description: Craft rules and workflow for motion graphics, and for videos made from scratch with no footage (explainers, kinetic typography, animated titles, data stories, promos, intros/outros, chapter cards), in 9:16, 16:9, 1:1 or 4:5. Use whenever the user wants a video without a camera, an animated explainer or title sequence, "make this move", or wants graphics/transitions/typography to look more professional. Covers timing, easing, choreography, typography, colour, transitions, pacing and sound, plus the storyboard engine (tools/storyboard.py) and its Remotion scene primitives. For Remotion API questions use the remotion-* skills; for talking-head shorts use short-form-pro (whose overlays follow the craft rules here).
---

# Motion graphics

The remotion-* skills explain how Remotion works. This skill is about taste: what makes motion
read as professional rather than as "PowerPoint with animations", and how to build a video from
an idea alone. Everything here runs locally and costs nothing.

**Engine:** `tools/storyboard.py` (check → stills → render → mix → loudness), with the Remotion
`Story` composition and scene primitives in `tools/motion/src/scenes/`.
**Template:** `templates/storyboard.json`. `tools/new_project.py --type generated` copies it in.

**Brand first.** The storyboard's `"brand"` loads `brands/<slug>/brand.json` (colours, fonts).
Read that brand's `brand.md` before planning. Its taste overrides the defaults below. With
`"brand": "none"`, use the neutral look and ask the user about style.

## Workflow: a video from scratch

1. **Project.** Run `uv run tools/new_project.py <name> --brand <slug|none> --type generated --platforms <list> --language <code>`.
   The aspect comes from the first platform: reels/tiktok/shorts → 9:16, youtube → 16:9, linkedin → 4:5, x → 1:1.
2. **Brief.** Ask, or infer, four things: the **one sentence** the viewer should remember, the audience,
   the platform (which sets the aspect and length), and the call to action. Without that sentence, the video has no spine.
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

`KineticType` styles: `rise` is masked word-by-word, typeset and editorial (the default). `pop`
springs words in, playful and social. `blur` is soft and premium. `fade` is calm and documentary.
`slam` shows one big line at a time, replacing the last, for hooks. `type` is a typewriter with a
caret, for prompts and searches.

The 9:16 overlay components from short-form-pro (`RingStat`, `PhoneMockup`, `Receipt`…) also work as
scene types, **only in 9:16**. `check` rejects them in other aspects.

Icons: `LineIcon` kinds in `components/icons.tsx` (speech, bulb, mail, receipt, calendar, search,
person, check, spark, send, chart, cv, plane). Use line icons, not emoji.

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
