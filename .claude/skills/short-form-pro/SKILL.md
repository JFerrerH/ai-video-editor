---
name: short-form-pro
description: Turn a talking-head take into a professional, high-retention vertical short (Reels / TikTok / Shorts) with B-roll from the brand's own assets, Remotion motion graphics, karaoke captions, zoom/look/freeze beats and synced SFX. Use whenever the user wants a short-form or vertical edit to be more engaging, eye-catching, "professional", or "less simple", or wants complementary visuals for what the speaker says. Builds on the video-use skill (read it first; its hard rules still apply).
---

# Short-form pro

`video-use` gets you a clean cut. This skill takes that cut to a finished
short: something new on screen every 2–3 s, all of it tied to the words being
spoken. Everything here runs locally and costs nothing.

**Engine:** `tools/shortform.py` (Python), `tools/motion/` (the Remotion stage that draws every frame),
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
   **float over the footage** with no backdrop, in the band above the head, with `enterFrom: "above"` so the
   entrance never crosses the face. **The engine places them**: leave out `frame`, and a floating overlay whose
   text would cover the head box (the face step's `head`) is scaled down and centred between the top safe margin
   and the head; when it would only fit with text under 28 px, `stills` says so (use `"full": true` or fewer
   words). A hand-set `frame: {scale, x, y}` still works locally; strict mode refuses it. **On a light backdrop captions turn plain ink**, key
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

## Edit by plan (preferred path)

Guessing seconds is where edits go wrong, and cutting, timing and placing are execution, not judgment. So write the
**plan**, the judgment (which lines stay, what each moment needs, which object carries the story), in sentence IDs and
words, and let the compiler do the rest. Writing `edit/short.json` by hand (Workflow below) stays possible for one-off
control; for edits nobody reviews by hand, plan.

```
uv run tools/edit_plan.py ids   footage/<p>          # F1, F2, … : take, start, length, text; false starts flagged
# write footage/<p>/edit/plan.json
uv run tools/edit_plan.py build footage/<p>          # → edit/short.json: check --strict, stills --strict (contrast, text over the face, tiny text), pacing
uv run tools/shortform.py stills footage/<p>/edit/short.json --strict   # then render --preview, then:
uv run tools/preview_qa.py footage/<p>               # listens to the preview: words, repeats, restarts, cuts
```
(The same three steps are the headless ops `plan_ids`, `plan_build`, `preview_qa`; `plan_precheck` answers in a second,
with no audio, what `plan_build` would refuse from the plan and transcript alone (echo, entrances that don't fit, a false
start kept, a cut with no pause, pacing), and `plan_build` runs its timing-independent part first (its times come from word times, so `timed_errors` are approximate); `uv run tools/edit_plan.py schema`
prints the plan's JSON Schema.) Run `conform`, `transcribe` and `face` first, as in Workflow 1 and 4.

Sentences also end at the transcript's `breaks`: a false start is its own flagged sentence even after a line with no
final punctuation, and so is a stretch of speech with no words (`untranscribed`). To drop either, leave its sentence out
of `keep`. If `plan build` is refused for kept speech with no words, the error names the sentences next to it: leave one
out. A transcript made before `breaks` existed can't split there (the error says so): run `transcribe` again on that take
(delete its `edit/transcripts/<take>.json` first), then `plan ids`, since the IDs change.

A plan has **no seconds**. Keys: `keep` (sentence IDs or ranges, in the order they play; a flagged false start is
refused, keep the repeat), `hook`, `beats`, `low`, `cta`, `captions` (`{"fixes": {"heard": "said"}}`, for a misheard
word), `assets`, `brand`.

- A **beat** is what one moment needs: `at` (a sentence), `word` (where it lands, default the sentence's first) and any
  of `device` (an overlay or stage component and its `props`), `camera` (`push`, `pull`, `side`, `corner`, `none`),
  `punch` (a punch-in on the word). `layer`/`object` are optional; `until` and `through` end the hold on a sentence or a
  word (a long run-on sentence needs `through`). A prop that is a time (an item entering, a stamp landing) is the word
  it lands on, `{"word": "costly"}`, not a number; leave an entrance list's times out and they come one after another.
  A stamp or a drop needs a run-up: start its beat a word or two before the word it lands on (a `Gauge` whose `slamAt` is
  its own first word fails in the render).
- **The compiler executes, it never decides.** It cuts the kept sentences by word, with dead air out and a long pause
  inside a run as a jump cut that changes the frame size; starts each beat on its word and holds it to the end of
  its sentence, the next beat or 6 s; gives each device its layer and camera (a `corner` `PhonePanel` goes on the `panel`
  layer with a `corner` move; a `BehindWord` pulls; a `Stuck` pushes); places floating text above the head (the engine
  does that: never write `frame`); picks sound effects, one per visible important change (hook pop, panel/side swipe,
  pull whoosh, drawer thud, gauge stamp, notice chime, first sticker pop, whoosh after the low look, click on a
  submit), minus `pluck` and anything the brand's notes reject. It adds **no** device, move or look you didn't ask for.
- **Restraint is enforced:** at most two punch-ins besides the hook's, one `low` look (a line of at most 3 s, never in
  the first 3 s), beats one at a time. The pacing report names the longest stretch with no graphic or camera move on
  screen: it warns past 5 s and refuses past 8 s, and never fills it. Add a beat where the line earns one, or cut
  tighter.
- **Devices are choices, none is required.** A short plan with only `keep` and a hook can be a valid, quiet edit. Pick a device
  because the line has a concrete thing to show, and let the same object come back (`object`) instead of a new card
  every time.

`build` leaves its stills in `edit/stills`: **read them before rendering**, a pass means the measured rules hold, not that the
edit is rich or good. Floating cards need room above the head; on a bright wall the default white text of a `BehindWord` or the
small kicker of a card fails, so give a `BehindWord` a dark `color` and no `camera: pull` (the stills place it above the head at that moment; `stills --strict` refuses text of which the speaker leaves under 85 % visible), and use full-screen scenes (`KineticType`
with `full`) or `Stickers` where a card won't fit. The build counts the time with no graphic or camera move on screen: a warning past 5 s, a refusal past 8 s (it never adds anything, so put a device on a word of the line that has something to show).

Errors name the plan field (`plan.beats[3].word`) or the beat (`beat 3 (F7 "la", Stuck)`) and the fix. Then check the
`stills` and the finished preview as in Verify; `preview_qa` fails on a word heard that the edit doesn't contain, a
clipped word, a line playing twice, a false start heard, or a cut louder than −12 dB against the speech.

Two worked plans (neutral content; the shapes are what matters):

*A founder story, about 65 s.* The idea card is one object that comes back with a different fill: the idea, "gave up",
"the friend's app", "ours".
```json
{"version": 1, "keep": ["F1-F2", "F4-F15"],
 "hook": {"title": ["Dreamed in 2020", "real today"], "emphasis": "real today"},
 "beats": [
  {"at": "F2", "word": "app", "device": "PhonePanel", "props": {"mode": "corner", "screens": [{"src": "site/home.png"}, {"src": "site/list.png"}]}},
  {"at": "F4", "word": "thesis", "device": "DocCard", "object": "idea", "props": {"kicker": "PLAN · 2020", "title": "A wardrobe in your phone"}},
  {"at": "F6", "word": "Big", "device": "Stickers", "props": {"items": [{"text": "Big Data", "at": {"word": "Big"}, "x": 150, "y": 230, "rot": -4}]}},
  {"at": "F7", "word": "drawer", "device": "StageDrawer", "through": "drawer", "props": {"card": {"kicker": "PLAN · 2020", "title": "A wardrobe in your phone"}, "dropAt": {"word": "put"}, "shutAt": {"word": "drawer"}}},
  {"at": "F7", "word": "but", "device": "Gauge", "through": "costly", "props": {"label": "QUOTE", "stamp": "OUT OF REACH", "slamAt": {"word": "costly"}}},
  {"at": "F8", "word": "half", "device": "DocCard", "object": "idea", "props": {"kicker": "PLAN · 2020", "title": "A wardrobe in your phone", "fillTo": 0.5, "fillAt": {"word": "half"}}},
  {"at": "F9", "word": "what", "camera": {"kind": "push", "amount": 0.08}},
  {"at": "F12", "word": "reality", "punch": true},
  {"at": "F15", "word": "visit", "device": "Waitlist", "props": {"title": "Early access", "placeholder": "you@mail.com", "email": "ana@mail.com", "button": "Join", "success": "You're in", "typeStart": {"word": "page"}, "typeEnd": {"word": "join"}, "submitAt": {"word": "list"}}}],
 "low": {"at": "F10", "words": "it's too late"},
 "assets": {"site/home.png": "assets/home.png", "site/list.png": "assets/list.png"}}
```
*A two-skills tutorial, about 85 s.* A tracker (`SkillSlots`) opens the list, marks each skill and recaps; stickers and a
search bar show what the speaker is saying; a word behind the head lands the quotable line.
```json
{"version": 1, "keep": ["F1", "F3-F11", "F13-F14"],
 "hook": {"title": ["2 skills", "before the AI"], "emphasis": "before the AI"},
 "beats": [
  {"at": "F1", "word": "nobody", "device": "BehindWord", "camera": {"kind": "push", "amount": 0.06}, "props": {"lead": "nobody talks about", "word": "two skills", "riseAt": {"word": "two"}}},
  {"at": "F3", "word": "skills", "device": "SkillSlots", "props": {"slots": [{"icon": "speech"}, {"icon": "bulb"}]}},
  {"at": "F4", "word": "communication", "punch": true},
  {"at": "F5", "word": "explain", "device": "Stickers", "through": "most", "props": {"items": [{"text": "explain", "at": {"word": "explain"}, "x": 120, "y": 230, "rot": -4}, {"text": "what you want", "at": {"word": "want"}, "x": 330, "y": 390, "rot": 3}]}},
  {"at": "F6", "word": "search", "device": "SearchBar", "through": "magic", "props": {"query": "what can AI do?", "typeEnd": {"word": "internet"}, "resultsAt": {"word": "video"}}},
  {"at": "F10", "word": "No", "device": "BehindWord", "through": "silly", "props": {"lead": "no such thing as a", "word": "silly question", "riseAt": {"word": "silly"}}},
  {"at": "F13", "word": "two", "device": "SkillSlots", "props": {"slots": [{"icon": "speech", "at": {"word": "two"}}, {"icon": "bulb", "at": {"word": "two"}}]}}],
 "cta": {"at": "F14", "word": "share", "handle": "Share it", "kicker": "Send it"}}
```

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
4b. Fill `edit/short.json` (`tools/new_project.py --shortform` writes it): `sources` (file + face, + `head` from the
   face step, else read from `edit/face.json`), `segments` (take, from/to or in/out, zoom, look, freeze_after),
   `brand`, `captions` (fixes, word_fixes, skip),
   `emphasis`, `events`, `sfx`, `public_files`. Time an event or SFX with an anchor instead of a number:
   `{"word": "launch", "take": "take1", "after": 12.0, "edge": "start", "offset": 0.1}` or
   `{"seg": 3, "edge": "end"}`. Anchors resolve **after** edge refinement, exactly as `p.word()` after
   `p.refine_edges()` does in a `build.py`. `edges: {"above_floor": 28}` for very low noise floors (gotchas).
   **Cut by words, not seconds:** `{"take": "take1", "from": {"word": "Resulta"}, "to": {"word": "maestría.", "after": 40}}`.
   The engine puts each edge in the pause before `from` / after `to` (silence measured against the take's own
   speech, so a breath counts as silence), or at the quietest point between two words that run together, never
   inside one, and drops every inner pause of 0.30 s or more (dead air) as a jump cut with the segment's zoom and
   look. `check`'s timeline shows the resolved seconds (pieces as `3.0`, `3.1`). Give `after` (source seconds)
   when the word occurs more than once. Seconds still work; use them for edges on music or a sound, not a word.
   A `base.mov` from `tools/shotcut.py` (character videos, `character-video` skill) is also a valid
   single source: one locked segment over it, as in `templates/character_build.py`.
5a. `uv run tools/shortform.py check <edit>/short.json` → timeline, edge report, echo/SFX warnings and
   errors; it writes no video. Fix every error (each says what to change); read every warning. `check` fails on:
   - **repeated audio:** two segments of one take covering the same source time, before or after edge
     refinement (`segments[4] (…) overlaps segments[3] (…) by 0.76 s: "…" would play twice`). Start the later one
     where the earlier ends, or set `"repeat": true` on it when the repeat is deliberate. Contiguous cuts of one take
     (next in ≤ 0.6 s after an out) whose refined edges would cross are `[joined]` at the quietest point between them;
     a pause you trimmed between them stays trimmed.
   - **an edge inside a word** that refinement couldn't move to silence (`segments[7].in 57.50 is inside "empezar"
     (57.28–57.64): use 57.28 or 57.64`). **A lock never excuses it**: `lock_in`/`lock_out` only keep an edge on sound
     *between* words (music, a breath). An edge in the silence of Whisper's early stamp isn't inside the word.
   - **an edge on sound:** more than 3 dB over the take's silence threshold (room tone + `above_floor`, or the speech
     level − 25 dB in a very quiet room) (`… starts in the middle of sound: +20.9 dB over the room tone`). Above the
     threshold, or on a locked edge, it is a warning. An in-point at source time 0 is clean (nothing precedes it).
   - **a false start kept:** the transcript marks restarts (`restarts`; also inline in the packed transcript as
     `(restart: false start …)`). A segment that plays the abandoned phrase and its restart fails with the cut
     that removes it (`start it at 41.50`, or end it at the abandoned phrase and start a new segment at the
     restart). `"keep_restart": true` on the segment makes it a warning, for a repeat that is meant.
   - **a dark scene on a light backdrop** (`"bg": "dark"` with `"full": true` and no `"dark": true`), or the reverse.
   Warnings to read: a segment that keeps `untranscribed` speech (speech with no words: listen before keeping it).
   - **event props** that don't match the component's schema (`tools/motion/src/**/<Type>.schema.json`; all of them:
     `uv run tools/overlay_schema.py --export`): unknown keys, missing required ones, wrong types (a number given as a
     string: `"value": "400.000"`), values outside an enum or range.
   - **prop times outside the event:** prop times are seconds from the EVENT's start (or a word/segment anchor,
     resolved for you). An output time there gets `… 18.2 s is outside the event (it starts at 17.50 s and lasts 3.0 s); prop times are seconds from the event's start: did you mean 0.7?`. Every
     entrance (a line, item or word appearing, explicit or default cue) must also finish before the event ends.
5. **Edge pass (non-negotiable; clipped words are the #1 complaint).** Read the edge report and the edge warnings
   from `check`. Every edge warning needs an envelope plot (±0.6 s, words overlaid, current vs refined edge:
   plot the RMS envelope with matplotlib, mark word starts/ends and both edges, save a PNG and Read it). If a word
   can't be cut cleanly because the next word follows with no gap, **keep the longer phrase**. Clean audio beats
   hitting 60 s. `from`/`to` edges are placed for you; use `lock_in`/`lock_out` only for edges on sound between
   words that you verified by eye (never to get past an in-word error).
   A drawn-out filler ("y…") you drop at an in-point can still get captioned from Whisper's stretched
   stamp: list it in `captions.skip`. Check the transcript's `untranscribed` ranges first: speech the
   transcriber couldn't put words to has no captions and no word anchors.
6. `uv run tools/shortform.py stills <edit>/short.json [--at t …]` → finished-look frames (cut, zoom, camera,
   every layer, the speaker's cut-out, captions: stage frames) in `edit/stills/`, ~3 s each, no render: the segment midpoints (or your
   `--at` times) plus one `ev<NN>_<Type>_<t>.png` per overlay event once its entrance has finished. Read every one
   and fix layout first. `stills` measures every event's text in the render (`edit/overlay_text.json`: field, box,
   px height) and warns when:
   - its text barely shows (`events[2] (KineticType) shows almost no text`: off screen, masked, not in yet);
   - its text doesn't read against what is really behind it (the event over the cut's own frame, with and without
     its glyphs: `events[0] (StatScene) text contrast 1.4:1 at 1.20 s is under 4.5:1 (kicker 1.4:1)`; 4.5:1 under
     48 px tall, 3:1 above). Give floating text a card, or a colour that reads on the wall;
   - text covers the speaker's face (the head box grown 6 % of the width; text behind the cut-out is exempt);
   - text renders under 28 px tall (a tiny tracked kicker shrunk with the card);
   - captions can't clear an overlay's text (they move below it, or above it, for that event on their own).
   A Remotion failure names the event: `events[N] (<Type>) failed at <t> s: <error>`.
   **Strict mode** (`--strict` on `check`/`stills`/`render`, `"strict": true` in a job) is for edits nobody
   reviews by hand: locks, `keep_restart` and hand-set `frame` are refused, and every never-list finding
   (`uv run tools/shortform.py check --never-list`), loud edge and layout invariant is an error; `stills --strict`
   then reports `renderable: false`. The invariants, which hold for every component, brand and framing:
   - `outside`: every text and drawn shape sits inside its card (the nearest ancestor with a background) and the
     frame (text between 100 and 1536 px vertically), measured at the finish of every entrance, not only at the
     still. Shorten the text or lower the list; the schema limits (`maxLength`, `maxItems`) refuse the worst cases
     before any still.
   - `face` for captions: when captions move off a graphic, the new band must also clear the head; if no band does
     it is a finding (fewer words, `"full": true`, or a `corner`/`side` move), never captions over the eyes.
   - `no_air`: a cut with less silence than the edge refinement's air (0.10 s before an in-point, 0.12 s after an
     out-point). In plans it names the sentence: keep the neighbouring sentence, or start/end at another one.
   - The video ends with a tail: the last clip holds its picture `END_TAIL` (0.30 s, `tools/shortform.py`) and
     the audio fades out in the silence there, so it never stops on a syllable.
   `uv run tools/layout_matrix.py` draws every component at its schema limits (wide capitals for any text, the
   widest digit for `x-text: "number"`, lists full) on three brand fixtures and two framings, plus two random
   inputs per component (a brand, a framing and props drawn from a printed seed; `--seed` reproduces a run), and
   exits 1 on any finding (under 5 min with cores minus two at once). Run it before releasing a component or a
   limit change. A refusal with a plan fix (a floating card with no room above a close-up's head, or a device that
   keeps its own place reaching the face) is listed as "refused": in a plan, answer it with `"full": true` or a
   `corner`/`side` move.
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
| `tools/short_spec.py` | Loads `edit/short.json` into the engine: validates every field (paths stay inside the project, grades are preset names, overlay `src` must be a `public_files` name, event props against their component's schema), refines edges, checks overlaps and edges, resolves anchors (prop times too). `check()` plans without rendering. Limits: 180 s, 120 segments, 200 events, 200 SFX. |
| `tools/overlay_schema.py` | Props schemas of every overlay component and scene (`<Name>.schema.json` beside it): validation, time fields, reveal cues, viewer text. `--export` prints them all (also the `schema` job op). |
| `tools/edit_plan.py` | `ids` numbers the transcript in sentences (F1…, false starts flagged); `build` compiles `edit/plan.json` (sentence IDs and words, no seconds) into `edit/short.json` and runs `check --strict`; `schema` prints the plan's JSON Schema. |
| `tools/preview_qa.py` | After a preview render: transcribes `edit/preview.mp4`, compares it with the words the edit keeps (unexpected speech, clipped word, repeat, restart) and measures the sound at each cut against the speech (−12 dB). Errors carry the output time, the segment and the fix. |
| `tools/shortform.py` | CLI `check\|stills\|render <spec>`. `Seg(take, in, out, zoom, look, freeze_after)`, `Project(..., brand="<slug>").build(preview)`. Zooms: `("static", s)`, `("push", a, b)`, `("punch", base, peak, src_t)`, `("outpunch", a, b, peak, src_t)`. `p.word()` / `p.at()` map source times → output timeline. Looks: `None`, `"bw"`, `"low"`. Karaoke ASS, attack-aligned SFX mix, two-pass loudnorm. `build()` cuts and mixes, then draws the frames on the Remotion `Stage` (no `overlay.mov`). |
| `tools/brand.py` | `load_brand(slug)` → Remotion theme, font `public_files`, caption props from `brands/<slug>/brand.json`; `None` → neutral. |
| `tools/motion/` | Remotion project. Composition `Stage` (what a short renders) reads `{durationInSeconds, brand, base, persons[], camera[], events[]}` and draws the cut `base` under the camera with the events on three layers; composition `Overlay` (`{durationInSeconds, brand, events[]}`) draws events alone on transparent, for measuring and blame. Studio: `cd tools/motion && npx remotion studio --props=<edit>/overlay_props.json --public-dir=<edit>/motion_public`. |
| `tools/sfx_synth.py` | Builds `assets/sfx/synth/*.wav` + `attack.json`: whoosh, whoosh_short, riser, impact, stamp, thud, pop, click, shutter, typing, chime, success, error, scratch, swell, pluck, bubble, swipe, tap, sparkle, sub, tick. Licence-free (synthesized). File RMS differs a lot (bubble/sub are hot): measure each effect against speech in the mix, not just the gain you typed. |
| `tools/person_matte.py` | Grey person matte (white = person) for a window of a clip: Apple Vision `.accurate` via `person_matte.swift` on macOS, MediaPipe selfie segmenter elsewhere (`uv sync --group matte`; `--backend` forces one). `matte_windows()` pads and merges the `behind` events' windows; `cutout()` writes the speaker as ProRes 4444 with alpha, deleted after the render. |
| `tools/site_capture.py` | Phone-sized viewport + full-page PNG of a URL (system Chrome via Playwright). It scrolls first so reveal animations render. |

### Overlay components (`tools/motion/src/components/`)

Every event is `{type, start, duration, props}` in output seconds. `props.full: true` draws the
brand `Backdrop` (a cutaway); `props.frame: {scale, x, y}` shrinks/moves any component (origin top
centre) to float it over the footage; `mono`/`dark` restyle it. Times inside props are seconds **relative to
the event start** (in `short.json` also a word or segment anchor); `check` rejects any that land outside the event.
The full prop list of each component is its schema (`uv run tools/overlay_schema.py --export`).

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

**Behind the speaker:** any event with `"layer": "behind"` (or the older `props.behind: true`) is drawn UNDER the
speaker's cut-out (`tools/person_matte.py`: Apple Vision on macOS, ~30 s per window; MediaPipe on Linux/Docker, same
build file, softer and less precise around loose hair against a busy background): text appears behind the head/hair. Set the text's `top` so its lower part overlaps the top of the head (find the head top on
a frame of that segment at its zoom) and keep it within `SAFE.side`. Captions and normal events stay on top.

### The stage: camera, layers and objects

A short renders on the Remotion `Stage`: ffmpeg cuts and mixes, then one composition draws the footage, the
speaker's cut-out, every event and the captions, so a graphic can move the speaker. Order, bottom to top:
`panel` → footage → `behind` → speaker cut-out → `front` → captions. **None of this is required**: a spec
without `camera` or `layer` renders as before (everything `front`, no camera), and most lines want no device.

**Camera** (`camera: [{kind, start, end, amount?}]`, times in seconds or word anchors, no overlap):

| Move | What it does | Suits |
|---|---|---|
| `push` | slow push-in, `amount` ≤ 0.08 | stakes, a serious line, before a turn |
| `pull` | the shot shrinks to 80 % on the brand's ink, rounded corners | a `behind` word that needs room |
| `side` | zoom 1.3× with the speaker in the left third, the wall on the right free | a `front` object (`PhonePanel` `side`, `Notice`, `Gauge`) |
| `corner` | the speaker becomes a 30 % bubble at the bottom right over the brand gradient; captions turn ink and sit above it | real screens or pages that need the frame (`PhonePanel` `corner` on layer `panel`, `CodePanel`) |

**Split screen is not available.** It was built and shown and rejected: cutting the speaker in half to give a
component half the frame is too invasive. Use `corner` (the speaker stays whole) or `side` instead.

**Layers** (event field `layer`, beside `props`): `front` (default), `behind` (under the speaker's cut-out, so the
speaker covers it) and `panel` (under the footage; only valid while a `corner` move covers the whole event).
Each component lists the layers it may use in its schema (`x-layers`).

**Components** (schemas in `tools/motion/src/stage/components/`, `uv run tools/overlay_schema.py --export`):
`Stickers` (key words pop in on their spoken beat), `BehindWord` (a big word rising behind the head, optionally
struck through; keep it in the band above the shoulders where the matte is clean), `DocCard` (a story object with
fill, tag and pulse), `StageDrawer` (a card falls into a drawer; not the older `Drawer`), `PhonePanel` (real
screens, modes `corner` and `side`), `CodePanel` (types itself; can sit behind the speaker), `Gauge` (needle slams
to red, with a stamp), `Stuck` (a bar that stalls), `Notice` (a phone notification quoting what the speaker
reports). They draw where the spec says: the engine doesn't re-place them above the head.

**Recurring objects:** events of one component sharing `object: "<id>"` are the same thing coming back; `check`
errors if their identifying props differ (`DocCard`: `kicker`, `title`, `italic`) and lists where each appears.
A thread of one object through a video is a device, not a rule.

**Echo and emphasis:** `Stickers` and `BehindWord` items of up to 3 words, and a `Notice` quoting reported speech,
are emphasis, not restatement (the echo rule exempts them). Caption emphasis is dropped for a phrase one of them is
showing, so the same words aren't doubled in a heavier face.

**The low moment** (`"look": "low"`, optional `"freeze": 0.3–0.5`): one segment of 1.0–3.0 s with a static zoom, in
black and white with added contrast; its voice is band-limited to about 220 Hz–2.4 kHz (the consonants stay
audible; two stacked 1.1 kHz low-passes were rejected as unintelligible), with a light short echo. At most one per
video. Check by re-transcribing the rendered span.

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
- **Remotion `--scale`** must give integer dimensions. The stage previews at exactly 720x1280 with
  `--scale=0.6666666666666666` (a rounded 0.6667 gives 1280.06 px and Remotion refuses it); finals render at
  scale 1.
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
