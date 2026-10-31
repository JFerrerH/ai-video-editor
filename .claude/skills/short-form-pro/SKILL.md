---
name: short-form-pro
description: Turn a talking-head take into a professional, high-retention vertical short (Reels / TikTok / Shorts) with B-roll from the brand's own assets, Remotion motion graphics, karaoke captions, zoom/look/freeze beats and synced SFX. Use whenever the user wants a short-form or vertical edit to be more engaging, eye-catching, "professional", or "less simple", or wants complementary visuals for what the speaker says. Builds on the video-use skill (read it first; its hard rules still apply).
---

# Short-form pro

`video-use` gets you a clean cut. This skill takes that cut to a finished
short: something new on screen every 2–3 s, all of it tied to the words being
spoken. Everything here runs locally and costs nothing.

**Engine:** `tools/shortform.py` (Python), `tools/motion/` (Remotion overlay),
`tools/sfx_synth.py` (SFX), `tools/site_capture.py` (website stills).
**Describe the short as data:** `edit/short.json` (template `templates/short.json`, shape and anchors in
`tools/short_spec.py`), run with `uv run tools/shortform.py check|stills|render <edit>/short.json`. It is
validated and executes nothing, so the same spec runs headless (`run_job.py` op `shortform`). `edit/build.py`
(template `templates/shortform_build.py`) drives the same engine from Python: keep it as the escape hatch for
one-off code the spec can't express. Past projects' `build.py` files are good worked examples when they exist on
this machine; they are never committed.

**Motion craft** (timing, easing, choreography, transitions, type sizes) lives in the `motion-graphics`
skill and applies to every overlay here. A full-screen cutaway that needs to be a whole designed scene can
use its aspect-aware primitives (`TitleCard`, `KineticType`, `StatScene`, `BarChart`, `ListScene`, `ImageScene`)
as overlay events with `full: true`.

**Brand first.** Each project's `edit/project.md` names its brand. When it has one, read
`brands/<slug>/brand.md` before planning: the brand's taste **overrides the defaults below** (caption
colour, hook rules, looks, SFX vocabulary, CTA). Without a brand (`Brand: none`), use the neutral defaults
and ask the user about taste. Never carry one brand's rules or examples into another project.
Examples below are illustrative. They show the technique, not a style to copy.

## Retention playbook (what makes it feel professional)

1. **Hook in the first frame.** The video starts on speech (trim lead silence to
   ~50 ms) with a text hook card built on curiosity or emotion **about the speaker's own story**
   (e.g. *"I dreamed this app in 2020 / and today it's real"*). It should be true to the story, under 7
   words per line. Tone, colour and what's off-limits (e.g. no competitor comparisons) come from the brand kit. Keep the face on screen for the first ~3 s so viewers connect with a person.
2. **Pattern interrupt every 2–3 s.** Rotate through: jump cut with zoom change,
   punch-in on an emphasis word, a pop-in graphic over the speaker, a full
   cutaway, a look change. Never hold the same frame more than ~4 s.
3. **Show what the speaker says.** Go through the transcript line by line: each concrete noun,
   number or claim becomes a visual. Order of preference:
   1. **The product itself:** real app screens / website (from the user's own site → `site_capture.py`).
   2. **People in the story:** founder or team photos (polaroids), with permission.
   3. **Data as graphics:** years → `DocumentCard`, money → `Receipt`, % → `RingStat`/`ProgressCard`, time → counters.
   4. **Metaphors:** "put it in a drawer" → `Drawer`; "we went all in building it" → `CodeEditor`.
   5. Stock footage, but only if a free licensed source with an API is available. Never scrape.
4. **Emotional arc in the picture.** Low point → `look="bw"` **only on the exact line that is
   the low point**, not on the build-up. Graphics around it stay in colour. Turn → hold the low beat on
   real footage (extend the out-point through the pause; a `freeze_after` frame can read as a glitch, so use it
   only if the brand asks), then a `Flash` and the colour snaps back on the comeback line, with one transition
   sound (whoosh by default; heavier hits only if the brand wants them).
4b. **Cutaway vs floating.** Only graphics that fill the screen get a full backdrop (`full: true`):
   phone/product montages, website scrolls, code editors. Cards, receipts, drawers, stats and photos
   **float over the footage** with no backdrop, shrunk into the band above the head with
   `frame: {scale, y}` (keep the scaled top ≥ 290 and the bottom above the head at the segment's tightest zoom) and `enterFrom: "above"`
   so the entrance never crosses the face. **On a light backdrop captions turn plain ink**, key
   phrases included (no accent colour on a background).
5. **Cutaways ≤ 3 s, product montages ≤ 7 s.** The voice continues underneath; swipe
   screens on the exact words (`p.word(...)`).
6. **Progressive captions** (default `caption_engine="remotion"`): each word appears on its own
   spoken timestamp, and the line is never shown ahead of the voice. Base style: the brand serif,
   sentence case, ~460 weight, white with a soft shade; size from `brand.json` `captions.size` (58 px default).
   **Key phrases** (`Project.emphasis`, ~1 per 4–5 s, on the same beats as the SFX/graphics):
   the same serif at ~600 weight, `captions.emphSize` (68 px), in `captions.emphColor` (white by default;
   a brand might use a soft yellow such as `#FCF0A3`). **A key phrase is always ALONE on screen.** The chunker clears the
   plain words before it, shows only the key phrase, then continues; lone function words left over
   ("en", "a la") fold into the previous plain line. Default to no boxes, panels or underlays behind
   captions (a brand kit can say otherwise). On light cutaway backdrops everything turns plain ink.
   Over footage, a soft radial shade keeps them legible.
   **Placement:** just under the chin (top ≈ 1300 px), inside the Instagram profile-grid crop
   (centre 3:4 = y 240–1680), above the bottom UI (y > ~1530) and clear of the right buttons. Check at
   the tightest zoom. Over a face is the other allowed spot. Graphics stay out of the caption band.
   **One word at a time:** `captions.mode: "word"` in `brand.json` (or `caption_props`) shows each plain word
   alone, replaced by the next, while key phrases stay together as one block; pair it with `emphCaps: true`
   + `emphWeight` (~760) for bold uppercase punch lines, and a bigger base `size` (~68 px). Over light clothes
   or walls raise `shade` (radial darkness, default 0.32) to ~0.5.
   The legacy uppercase karaoke ASS is still available as `caption_engine="ass"`.
6b. **Graphics complement, never echo.** An overlay must not print words the captions are saying
   at the same time (a ring labelled "half" while the speaker says "half"). It shows what the speaker
   *doesn't* say: the number without the words, the outcome, the who or what (the speaker's name on a
   thesis card), or nothing (unlabelled app screens).
   `p.echo_check()` flags every echo. It must be clean before rendering.
7. **CTA on screen.** Show the action as a UI (`Waitlist` typing → success), then a persistent
   `HandleCard` (@handle) to the end.
7b. **SFX vocabulary (default; a brand kit can override):** floating graphics land with a soft `click`
   (−15/−16 dB), and so do a few key phrases that have no other sound nearby (~3 per minute). **Vary the
   vocabulary** so it doesn't read as one click on loop: match the sound to the object (`bubble` chat,
   `pluck`/`tap` cards, `tick` counters/steps, `sparkle` an idea, `shutter` a screenshot, `pop` tiles,
   `error` a miss, a soft `sub` (≈ −22 dB) under one or two big punch lines). Cutaways
   and transitions get ONE simple `whoosh`; avoid stacking hits. No two effects within 0.3 s
   (`p.sfx_check()`). Prefer swapping an effect over adding one.
8. **Sound = picture.** Every SFX is tied to a visible event, sits 12–20 dB under speech,
   and is attack-aligned. Big hits go in silences, not over words.
9. **No music by default.** Tell the user to add a trending sound in-app at 5–10%
   (the platforms favour native audio). If music is licensed, duck it −12 to −15 dB under speech.

## Workflow

1. Run the `video-use` flow: inventory → transcribe (`--language` set!) → pack →
   propose the cut → **approval**. Aim for ~60 s, but never clip speech to get there.
2. **Gather visuals the user owns:** `uv run tools/site_capture.py <url> -o <edit>/downloads/site`
   (viewport + full-page PNG). Also download the site's own images and fonts (look at `<img src>` and
   `@font-face`). New brand? Copy `brands/_template/` to `brands/<slug>/`, put fonts and logos in its
   `incoming/`, fill in `brand.md` + `brand.json`, then run `uv run tools/brand_check.py brands/<slug>`.
   Resolve its `warnings` (set each `fontFiles` weight or range to what the file provides) before a
   final render.
3. **Plan the visuals as a table:** time | spoken line | what is on screen | SFX. Present it, ask
   only what you can't decide (permission for people photos, B&W low point, missing
   API keys). **Wait for approval.**
4. **Sources:** any SDR 9:16 take works (4K is scaled into the 1080x1920 work frame; face centres stay in
   source px). HDR, horizontal or other-aspect takes must be conformed first:
   `uv run tools/conform.py <project dir> --frame 9:16` → `edit/conformed/<stem>.mov` (same timeline, so the
   original's transcript still fits). `uv run tools/face_centre.py <take>` suggests the face centre; check it on
   a still (`uv run tools/frames.py <take> --at 2 8 --sheet`).
4b. Fill `edit/short.json` (`tools/new_project.py --shortform` writes it): `sources` (file + face), `segments`
   (take, in, out, zoom, look, freeze_after, lock_in/lock_out), `brand`, `captions` (fixes, word_fixes, skip),
   `emphasis`, `events`, `sfx`, `public_files`. Time an event or SFX with an anchor instead of a number:
   `{"word": "launch", "take": "take1", "after": 12.0, "edge": "start", "offset": 0.1}` or
   `{"seg": 3, "edge": "end"}`. Anchors resolve **after** edge refinement, exactly as `p.word()` after
   `p.refine_edges()` does in a `build.py`. `edges: {"above_floor": 28}` for very low noise floors (gotchas).
   A `base.mov` from `tools/shotcut.py` (character videos, `character-video` skill) is also a valid
   single source: one locked segment over it, as in `templates/character_build.py`.
5a. `uv run tools/shortform.py check <edit>/short.json` → timeline, edge report, echo/SFX warnings and
   errors; it writes no video. Fix every error; read every warning.
5. **Edge pass (non-negotiable; clipped words are the #1 complaint).** Read the
   edge report from `check`. Every `WARN` and every edge-energy "check" needs an
   envelope plot (±0.6 s, words overlaid, current vs refined edge: plot the RMS envelope with
   matplotlib, mark word starts/ends and both edges, save a PNG and Read it). If a word can't be cut cleanly because the next word
   follows with no gap, **keep the longer phrase**. Clean audio beats hitting 60 s.
   Use `lock_in`/`lock_out` only for edges you verified by eye. Watch for widened edges that **overlap the next segment** on continuous
   boundaries (duplicated audio): check each segment's refined out ≤ the next one's in and lock both at the dip.
   A drawn-out filler ("y…") you drop at an in-point can still get captioned from Whisper's stretched
   stamp: list it in `captions.skip`.
6. `uv run tools/shortform.py stills <edit>/short.json [--at t …]` → finished-look frames (cut, zoom, overlays,
   captions, behind-the-speaker layers) in `edit/stills/`, ~3 s each, no render. Read them and fix layout first.
7. `uv run tools/shortform.py render <edit>/short.json --preview` (~1 min for 60 s). Then verify (below), iterate,
   and render the final without `--preview`. Copy to `exports/<project>_<platform>_<YYYYMMDD>.mp4`.
   The final uses `DELIVERY_X264` (Instagram/TikTok master): source frame rate (don't upsample 30→60),
   H.264 High CRF 16, 1 s GOP, BT.709 tagged in the VUI, AAC 320k/48 kHz, faststart. Check with
   `ffprobe` that `color_primaries/transfer` read `bt709`.
   With a `build.py` instead: `uv run <edit>/build.py --preview`, `p.echo_check()`, `p.sfx_check()`,
   `p.stills([t…])` do the same.

## Tools

| Tool | What it does |
|---|---|
| `tools/short_spec.py` | Loads `edit/short.json` into the engine: validates every field (paths stay inside the project, grades are preset names, overlay `src` must be a `public_files` name), refines edges, resolves anchors. `check()` plans without rendering. Limits: 180 s, 120 segments, 200 events, 200 SFX. |
| `tools/shortform.py` | CLI `check\|stills\|render <spec>`. `Seg(take, in, out, zoom, look, freeze_after)`, `Project(..., brand="<slug>").build(preview)`. Zooms: `("static", s)`, `("push", a, b)`, `("punch", base, peak, src_t)`, `("outpunch", a, b, peak, src_t)`. Looks: `None`, `"bw"`. `p.word()` / `p.at()` map source times → output timeline. Karaoke ASS, attack-aligned SFX mix, two-pass loudnorm, overlay composite, captions LAST. |
| `tools/brand.py` | `load_brand(slug)` → Remotion theme, font `public_files`, caption props from `brands/<slug>/brand.json`; `None` → neutral. |
| `tools/motion/` | Remotion project. Composition `Overlay` reads `{durationInSeconds, brand, events[]}` and renders one transparent ProRes 4444 layer. Studio: `cd tools/motion && npx remotion studio --props=<edit>/overlay_props.json --public-dir=<edit>/motion_public`. |
| `tools/sfx_synth.py` | Builds `assets/sfx/synth/*.wav` + `attack.json`: whoosh, whoosh_short, riser, impact, stamp, thud, pop, click, shutter, typing, chime, success, error, scratch, swell, pluck, bubble, swipe, tap, sparkle, sub, tick. Licence-free (synthesized). File RMS differs a lot (bubble/sub are hot): measure each effect against speech in the mix, not just the gain you typed. |
| `tools/person_matte.py` | Grey person matte (white = person) for a window of a clip: Apple Vision `.accurate` via `person_matte.swift` on macOS, MediaPipe selfie segmenter elsewhere (`uv sync --group matte`; `--backend` forces one). Used automatically for `behind` events. |
| `tools/site_capture.py` | Phone-sized viewport + full-page PNG of a URL (system Chrome via Playwright). It scrolls first so reveal animations render. |

### Overlay components (`tools/motion/src/components/`)

Every event is `{type, start, duration, props}` in output seconds. `props.full: true` draws the
brand `Backdrop` (a cutaway); `props.frame: {scale, x, y}` shrinks/moves any component (origin top
centre) to float it over the footage; `mono`/`dark` restyle it. Times inside props are seconds **relative to
the event start**.

| type | use for | key props |
|---|---|---|
| `HookTitle` | opening hook card | `lines[{text, emphasis}]` |
| `PhoneMockup` | real app screens / website | `variant: center\|side`, `side`, `screens[{src, at, label}]`, `scroll{src, srcWidth, from, to, start, end, url}` |
| `DocumentCard` | a year, thesis, contract | `year?, kicker, title, emphasis, author, cardAt, enterFrom` |
| `Receipt` | cost / quote, "too expensive" | `title, items[{text, at, amount?}], total, stamp?, stampAt?, enterFrom` |
| `ProgressCard` | % progress, or "not ready yet" | `label, to, fillStart, fillEnd, stall, note, mono, showValue` |
| `RingStat` | a single % ("half") | `value, label?, fillAt, pulseAt, mono` |
| `Drawer` | shelving / giving up | `docTitle, closeAt` (pair with `full, mono`) |
| `Polaroids` | people in the story | `photos[{src, label, at, rotate}], chip, chipAt` |
| `CodeEditor` | building / hustle montage | `file, lines, dayFrom, dayTo, countStart, countEnd` (pair with `full, dark`) |
| `IdCard` | who / role / where, floating above the head | `kicker, title, subtitle, rows[{icon: pin\|swap\|dot, text, at}]` |
| `BoardingPass` | travel, conferences, remote work | `from, to, fromCity, toCity, carrier, details[{k, v}], flyStart, flyEnd` |
| `AiWorkflow` | AI tools / workflows: robot hub wires up emoji nodes, optional content pile at `pileAt` (pair with `full`) | `hub, nodes[{emoji, at}], pileAt, pileCount` |
| `PostPile` | "too much content" / noise (pair with `full`) | `count, pileStart, pileEnd, seed` |
| `Milestones` | life/career steps as icons (no numbers) | `items[{icon: cap\|diploma\|briefcase\|star, at, label?}]` |
| `AgeBars` | ratios / multiples (×1 ×2 ×3) | `bars[{value, label, at, highlight}], caption` |
| `Waitlist` | sign-up CTA | `title, placeholder, email, button, success, submitAt` |
| `SkillSlots` | "N things" tracker: numbered slots that fill with line icons on cue; reuse it per item and for the recap | `slots[{icon, at?}], active?` |
| `TopicCards` | "AI for X, Y, Z": small topic cards (line icon + kicker + title), one per cue, face stays visible | `cards[{icon, kicker?, title, at}]` |
| `NameTitle` | big serif name or punch line with no card; pair with `behind: true` to tuck it behind the speaker's head (for a punch line, `caption_skip` its words so the caption doesn't double it) | `text` or `lines[{text, at}], color?, size, weight, top` |
| `RoomDots` | "the only one in the room": a row of people, one lights up | `count, highlight, highlightAt` |
| `ContentGrid` | vague brief → bad deliverable: typing bubble → empty profile grid → clashing tiles → wobble | `gridAt, fillAt, missAt` |
| `FrameworkCard` | a framework/checklist to screenshot: `layout: "list"` full-screen (pair with `full`), or `"grid"` = compact 2×2 floating above the head; a short hold (~3 s) makes viewers pause/rewatch to screenshot (engagement) | `kicker, steps[{title, lines}], layout, stepsAt, stepGap, flashAt, top` |
| `SearchBar` | "searching the internet for answers": typing pill + spinner + skeleton results | `query, typeEnd, resultsAt` |
| `ChatThread` | asking your AI: abstract question bubbles, answers = icon + check; cutaway (`full`) or `floating` above the head | `messages[{from: me\|ai, at, icon?, lines?}], floating, bottom` |
| `DotTrack` | `steps` (circles checked on cue) or `days` (habit grid, e.g. 14 days) | `variant, stops[] / count, value, unit, fillStart, fillEnd` |
| `HandleCard` | end card | `kicker?, handle` (handle can be a CTA, e.g. "Comment below 👇") |
| `Flash` | the turn / comeback | `color` |
| `Captions` | added automatically by `Project` as the LAST event | `words[{t, text, emph(group id), chunk}]`, `chunks[{start, end}]`, `lightRanges`, `top`, `size`, `emphSize`, `emphColor` (defaults from `brand.json` `captions`; override via `Project.caption_props`) |

**Behind the speaker:** any event with `props.behind: true` is rendered UNDER a person-matted copy of the
footage (`tools/person_matte.py`: Apple Vision on macOS, ~30 s per window; MediaPipe on Linux/Docker, same
build file, softer and less precise around loose hair against a busy background): text appears behind the head/hair. Set the text's `top` so its lower part overlaps the top of the head (find the head top on
a frame of that segment at its zoom) and keep it within `SAFE.side`. Captions and normal events stay on top.

To add a component: create it in `components/`, register it in `REGISTRY` in `Overlay.tsx`, drive all
motion with `useCurrentFrame()` + `interpolate`/`spring` (no CSS transitions), read colours and fonts
from `useBrand()`, respect `SAFE` zones, and add a row to this table.

## Layout rules (1080×1920)

- Top ~290 px (≈15%): Instagram blurs/overlays its header ("Reels" title, camera, back button) here. Measured on a real
  Reels preview: the blur reaches ~270–300 px of the source (Meta's guides say "top 14%"). Nothing readable above `SAFE.top` = 290.
- Sides: cards and pills keep ≥ `SAFE.side` = 130 px from both edges (max width 820). Edge-to-edge cards read as "too big" on a phone,
  where IG also crops ~30 px a side.
- Above-the-head band (y 290–680): pop-in cards (hook, progress, ring, polaroids, waitlist, handle).
- Side pop-ins go on the **left** (x 56–360). The right ~15% belongs to the platform buttons.
- Caption band y≈1170–1300 (`margin_v=640`). Cutaway content ends by ~1270.
- Bottom: username + caption start at y ≈ 1750; the right button rail covers x > ~930 from y ≈ 1235 down. Captions at
  ~1300–1400 stay clear of both and inside the profile-grid 3:4 crop (y 240–1680).
- Check a real phone preview (IG Edits → Preview) when in doubt; scale = 0.732 of source on a 1600-px-tall screenshot.

## Hard-won gotchas

- **Whisper language:** always pass `--language`. An English verbatim prompt on Spanish audio makes the
  turbo model *translate*. `transcribe_local.py` now picks the prompt per language.
- **Early word stamps:** Whisper often starts a segment's first word inside the preceding silence.
  Set in-points from RMS silence (−40 dB, 10 ms windows), not from word starts. `p.at()` snaps
  times up to 0.4 s before an in-point to that segment's start, and captions assign each word to the
  segment it overlaps most.
- **Very low noise floors** (iPhone voice isolation, floor ≈ −77 dB): the default `above_floor=9` counts breaths
  and room tone as speech → WARNs everywhere and edges widened into the next segment (duplicated audio).
  Use `refine_edges(above_floor=28)` (≈ −49 dB, still > 25 dB under speech) and verify cuts on the base.
- **Line icons over emoji** in graphics (`components/icons.tsx` → `LineIcon`): emoji everywhere reads cheap.
- **Whisper word ends are early and its starts are early too.** Padding from word times (50/80 ms)
  clipped word tails and onsets in practice. `refine_edges()` fixes this from the envelope (silence = noise floor + 9 dB, 100 ms
  pre-roll, 120 ms tail, widen-only, never into the next sound). A higher threshold misses soft
  onsets, and a "dip" heuristic mistakes in-word dips for word gaps. Both were tried and reverted.
- **Removing words mid-sentence** only works where there is ≥ 60 ms of silence on both sides. A 40 ms
  gap is not enough; restore the phrase instead.
- **Exact segment lengths:** each segment is forced to N frames and N×(48000/fps) samples; otherwise
  ±1-frame drift adds up across 17 segments and overlays/SFX slide off their words.
- **Freeze frames:** `-t` must be an *input* option, or tpad/apad get truncated.
- **Remotion `--scale`** must give integer dimensions. The overlay is always rendered at 1080p and
  ffmpeg scales it for previews.
- **Fonts fail silently:** `Overlay` asserts `document.fonts.check()` for every brand font and fails
  with `Font did not load: <style> <weight> "<family>" (<file>)`.
- **Brand font weights:** `400`, `"400"` or a variable font's range `"100 800"` (give the range, or bold
  is faked instead of drawn from the weight axis). A role the kit leaves unset uses the kit's `sans`,
  else its first font file.
- Filenames from iPhone exports can contain U+202F (narrow no-break space). Rename sources first.
- Remotion is free for teams of up to 3. Larger companies need a licence.

## Verify before presenting

1. `ffprobe` duration == planned `offsets()[-1]` (to the frame).
1b. **Every cut on the rendered output:** RMS of the last/first 40 ms around each cut, on the
   final mix AND the dialogue-only base (`base_preview.mov`). Dialogue must be ≥ 20 dB under the
   speech level at the cut. If only the final mix is loud there, it's an SFX you placed on purpose.
   Also print the kept script per segment (`output_words()`) and read it as a sentence.
2. Contact sheet of ~30 frames across the timeline plus frames around the freeze/flash and every cutaway.
3. `ebur128`: −14 LUFS, true peak ≤ −1 dBTP, 3 s RMS steady (±2 dB).
4. Per-SFX check: level at each contact vs dialogue-only. Effects must never be louder than speech.
5. You can't listen: say so and report the numbers.
