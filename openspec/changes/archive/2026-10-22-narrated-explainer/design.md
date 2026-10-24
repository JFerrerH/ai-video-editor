# Design

## Context

- `tools/storyboard.py` reads `edit/storyboard.json`, computes the timeline from fixed scene
  `duration`s, writes `story_props.json`, and renders the Remotion `Story` composition through the
  `npx remotion` CLI. `narration` is only used by a words-per-second warning. `audio.voice` is one
  file placed at `voice_start`, and `mix()` ducks music under it and normalises loudness.
- `Story.tsx` mirrors the Python frame maths; `SceneView` draws `Bg` then the scene component.
  Overlay events live in `Overlay.tsx` `REGISTRY`; scene primitives in `scenes/index.ts` `SCENES`.
  `useFrameLayout()` gives the aspect's safe box.
- The existing 9:16 overlays (`CodeEditor`, `RingStat`, `PhoneMockup`…) are fixed to 1080x1920,
  so they can't be reused as-is in other aspects.
- `tools/transcribe_local.py` (mlx-whisper large-v3-turbo, already cached on this machine) writes
  word-level JSON to `<edit>/transcripts/<stem>.json` and takes several files in one run.
- Requirements: `specs/voice-generation`, `specs/explainer-graphics`, `specs/storyboard-video`.

## Goals / Non-Goals

**Goals:**
- `check`, `stills` and `render` keep working on a default install. Only `voice` needs the `gen`
  group.
- One frame maths: Python resolves every duration and cue to numbers, so `Story.tsx` keeps its
  current timeline logic unchanged.
- Usable early. Voice, timing and headline are useful before the figure and widgets exist, so they
  land first.

**Non-Goals:**
- Inverse kinematics, walk cycles, or a general character animation system.
- A visual editor. Everything is authored in `storyboard.json`.

## Decisions

### 1. TTS: Kokoro-82M through `mlx-audio`

- 82M parameters, Apache-2.0, runs on MLX (already installed), and is far faster than real time on
  a base M-series chip. It covers the languages we work in (English, Spanish, and more).
- Alternatives:
  - Chatterbox (MIT) is more expressive but ~10x bigger, torch-based and mostly English. It's the
    fallback if Kokoro's delivery is too flat, and the pilot is where that gets judged.
  - Piper (MIT engine; each voice has its own licence) sounds more robotic.
  - F5-TTS and XTTS have non-commercial weight licences.
- `tools/gen/voice.py` exposes `synthesize_many(jobs, force)` (one model load per run) and a CLI.
  The `mlx-audio` import happens inside the function, so the module's top level (language/preset
  tables, sidecar helpers) imports with the standard library only, and `check` can use it.
- Language validation needs no model. Kokoro preset ids carry their language in the prefix (`af_`/`am_`
  US English, `bf_`/`bm_` UK English, `ef_`/`em_` Spanish, `ff_` French, `if_`/`im_` Italian,
  `pf_`/`pm_` Portuguese, `hf_`/`hm_` Hindi, `jf_`/`jm_` Japanese, `zf_`/`zm_` Mandarin). One table
  maps a storyboard `lang` (`en`, `en-gb`, `es`…) to Kokoro's language code and a default preset.
- Silence trim: numpy RMS on 10 ms windows, keep 50 ms either side of the first and last window
  above -50 dBFS. Output: mono 24 kHz WAV (Kokoro's native rate); `mix()` already resamples to
  48 kHz.
- Text sent to TTS = narration with `*` and `|` removed, then the `voice.pronounce` map applied word
  by word (`{"SaaS": "sass"}`) for names it says wrong. The headline still shows the script's
  spelling (see 2).
- Sidecar JSON next to each clip = cache key (text sent, lang, preset, speed, model id) + duration +
  seconds taken. Same pattern as every other generated asset: no separate manifest.

### 2. Word timing: Whisper on each clip, aligned to the script

- `voice` (and `check`, for recorded clips) runs `transcribe_local.py` once on all clips that lack
  a fresh `<clip>.words.json`, with the storyboard language. Whisper is already cached and gives
  word times for recorded and synthesised clips alike.
- Alignment: tokenise the script (keeping punctuation and the `*` flag per word) and the spoken text
  (after `pronounce`, so each script word maps to one or more spoken tokens). Match normalised
  tokens with `difflib.SequenceMatcher`. A matched script word takes its first spoken token's
  start. Unmatched words are interpolated between their matched neighbours in proportion to
  character length. The first word is clamped to the clip's measured onset: Whisper stamps first
  words early (a known gotcha). Result: script words, in order, with strictly increasing times.
- Alternative: Kokoro's predicted phoneme durations would avoid Whisper. But `mlx-audio` doesn't
  expose them in a stable way, and the Whisper path also works for recorded clips.
- Phrases are cut in Python (after `.?!`, `|`, or 7 words) and written into each word as a
  `phrase` index, so the rule lives in one tested place and the headline just draws it.

### 3. Engine (`tools/storyboard.py`)

- A `resolve()` step runs before `check`/`stage`. It loads clip sidecars and word files, sets each
  auto duration to `transitionIn + clip + tail` (rounded to frames), records each scene's
  `voiceStart`, and resolves cues. `timeline()` uses the resolved durations, so the printed plan, the
  Remotion props and the render agree.
- Cue grammar: `^@([^#+-]+)(#\d+)?([+-]\d*\.?\d+)?$`. Cues are allowed in any prop value, in
  `figure.poses[].at` and in `sfx` times. Resolution walks the JSON. Errors are collected for
  `check`.
- New commands:
  - `voice [--force]`: synthesise clips, then time their words.
  - `sheet poses|widgets [--aspect A]`: render the verification contact sheets through two small
    Remotion compositions, `PoseSheet` and `WidgetSheet`.
- `render`: concatenate clips at their `voiceStart` into `edit/audio/narration_track.wav` (ffmpeg
  `adelay` + `amix`, the same pattern as the SFX), then feed it to `mix()` as the voice.
  `audio.voice` together with narrated clips is an error.
- `stage()` injects `words` (script text, time, emphasis, phrase) into each `BeatScene`'s props.
- The old `NARRATION_WPS` warning stays for storyboards without a `voice` block.

### 4. Remotion: `tools/motion/src/explainer/`

- **`GridBg`**: palette background, a 1 px grid (64 px pitch at 1080 short side) at ≤ 6% luminance
  contrast, a radial vignette, plus the scene's grain. Light and dark come from `paletteFor`.
- **`Headline`**: shows the words of the phrase active at the current frame. Each word rises and
  fades in over 3 frames from its time. Emphasis words sit in an accent pill (white text) with a
  spring pop. Wrapping uses `@remotion/layout-utils` `measureText` to the safe box's inner width,
  max 2 lines. Sizes scale with the short side.
- **`Figure`**: an SVG forward-kinematics rig. Hip root → spine → neck → head (circle + cap path),
  two arms (shoulder/elbow angles) and two legs (hip/knee angles). Round-capped 10 px strokes in
  palette ink; cap and shoes in the brand accent; a ground-shadow ellipse.
  - `poses.ts` holds each pose as a joint-angle table. Pose changes `spring()` every angle (settles
    in ≤ 0.4 s).
  - Idle motion: spine sway ±1.5° and a 2 px breath on a 2.4 s sine, phase-offset per scene.
  - Props attach to joints: megaphone to the right hand, box in front of the hands for `push`,
    desk + laptop on the ground for `type`.
  - `facing: left|right` mirrors the figure. `slot` and `scale` place it.
  - Alternatives: Lottie or Rive would need an authoring tool and licensed assets. AI-generated
    character frames aren't consistent from frame to frame and can't be posed. A code rig is
    consistent, brand-tinted and posable from JSON.
- **Widgets** (`explainer/widgets/`): a shared `Card` shell (radius, soft shadow, light/dark
  variant, spring rise-in at `at`, optional `out`). Each widget's own action times are cue-friendly
  props:
  - `Terminal{title, lines[{text, at, kind: cmd|out|ok}]}`: types commands at 22 chars/s.
  - `Checklist{items[{text, at?, state: todo|done|struck}]}`
  - `Stamp{text, at, color?}`: slams in rotated −8°.
  - `Counter{label, from, to, start, end, prefix, suffix, spark?}`
  - `Gauge{value, at}`, `Stopwatch{seconds, start, end}`
  - `FunnelBars{rows[{label, value}], at, drop?}`
  - `TileGrid{count, cols, colors?, at, stagger}`
  - `Badge{text, icon?, tone: ok|alert|neutral, at}`

  They borrow code from `CodeEditor` and `RingStat` but lay out from `useFrameLayout`.
- **`BeatScene`**: `GridBg` → widgets in slots → figure → `Headline` (top layer). The slots are
  `main`, `side` and `figure`, with geometry per aspect:
  - 9:16: stacked. Headline top, `main` in the middle, figure bottom-centre.
  - 16:9: headline top, `main` left two-thirds, figure right.
  - 1:1 and 4:5: like 9:16, scaled down.
- **`ProgressBar`**: registered as an overlay event. The engine adds it spanning the whole video
  when the storyboard sets `"progress": true`.

### 5. Dependencies

`[dependency-groups] gen = ["mlx-audio==<pinned>", "misaki[en]==<pinned>", "en-core-web-sm @ <wheel>"]`.
`espeak-ng` needs no system install: `misaki[en]` pulls in `espeakng-loader`, whose wheel ships
`libespeak-ng` and its data, and misaki loads that copy (found in task 1.2; this replaces the earlier
plan of a Homebrew `espeak-ng`). The tool checks that the bundled library is present when the language
needs it, and prints `uv sync --group gen` if it isn't. misaki's English pipeline needs the spaCy model `en_core_web_sm`; left alone it
installs it into the venv on first run, outside the lockfile, so it's pinned in the group instead.

## Risks / Trade-offs

- [Kokoro mispronounces names and jargon] → `voice.pronounce` map; the pilot lists every
  substitution it needed.
- [Spanish has fewer and flatter Kokoro voices than English] → the user listens to the pilot clips.
  Recorded `narration_audio` per scene always works. Chatterbox is the documented fallback for a
  later change.
- [Whisper misses words on very short clips] → interpolation keeps every script word, and the
  times-strictly-increasing check catches nonsense. `check` prints the aligned/interpolated count
  per scene.
- [The change is large] → task order: voice, timing and headline (usable on their own) → figure
  → widgets → BeatScene. Each group ends with its own sheet or still checks.
- [Poses look stiff or off-model] → the pose sheet is read before any pilot; angle tables are cheap
  to tune.
- [Delivery feels monotone across a 1–2 min piece] → per-scene `speed` override, a `tail` for
  breathing room, and music ducked underneath. The skill tells writers to vary sentence length.

## Migration Plan

Additive. Storyboards without a `voice` block behave exactly as before; `duration` stays required
for scenes without a narration clip (`check` errors if it's missing). Rollback = revert. Generated
clips under `footage/*/edit/audio/narration/` are ordinary WAVs.

## Open Questions

- Default voice preset per language. It's chosen by the user from the pilot's sample clips and
  written into the template; it doesn't change any spec. **Resolved 2026-10-22:** `af_heart` for
  English, `em_alex` for Spanish (`LANGS` in `tools/gen/voice.py`).
