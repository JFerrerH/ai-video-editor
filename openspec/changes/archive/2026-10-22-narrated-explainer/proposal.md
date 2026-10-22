# Proposal

## Why

The from-scratch videos we want are narrated vector explainers: a voice tells a short story, and
each spoken phrase builds on screen as a headline in time with the voice. A simple recurring
character reacts in each beat, and UI-style cards (a terminal typing, a counter ticking, a checklist
getting stamped) show what the words say. There are no photos, no realistic scenes and no human
likeness.

Today's storyboard engine has fixed scene durations, a single voice file that knows nothing about
the scenes, and no character or card widgets, so this format can't be made. We need a local voice,
timing driven by that voice, and the graphic vocabulary. This replaces the earlier Phase 2 plan
(local image generation and depth parallax), which doesn't fit this look.

## What Changes

- **Local voice (`tools/gen/voice.py`)**: script text → WAV with Kokoro-82M through `mlx-audio`,
  fully offline. Language and voice preset are chosen per storyboard. A sidecar JSON records text,
  voice, speed, model and duration; unchanged lines are never re-synthesised.
- **Narration drives the timeline**: a scene's `narration` is synthesised into its own clip (or
  taken from a recorded clip). Its duration sets the scene's length unless the scene fixes one.
  The engine places the clips on the timeline as one narration track and gets each word's time
  (local Whisper, then aligned to the script so the displayed words are exactly the script's).
- **Word cues**: any time in a scene (a widget's `at`, a pose change, an SFX) can be written as
  `"@word"`, the moment that word is spoken in that scene. `check` errors on cues that aren't in
  the narration.
- **Headline**: the narration builds on screen at the top of the safe box, word by word as it's
  spoken. Upcoming words are hidden, the current phrase is ink, and `*marked*` words get an accent
  pill that pops. It clears per phrase.
- **Character**: our own neutral stick figure as a vector rig, with a pose library (stand, wave,
  cheer, point, shrug, slump, think, type, push, shout) and a few props (desk + laptop, megaphone,
  box). Poses blend with springs, an idle sway keeps it alive, and the accent colour comes from the
  brand.
- **Widgets**: aspect-aware cards that act on cues: `Terminal`, `Checklist` (check / strike),
  `Stamp`, `Counter` (with optional sparkline), `Gauge`, `Stopwatch`, `FunnelBars`, `TileGrid` and
  `Badge`.
- **`BeatScene`**: one scene type composes them: a grid background (light or dark), the headline,
  the figure, and widgets placed in named slots. A top `ProgressBar` event shows the video's
  progress.
- **Skill + routing**: the `motion-graphics` skill gets a "narrated explainer" section (beats of
  2–4 s, one idea per beat, the figure reacts, numbers move while they're said, a stamp for a
  negation, light/dark switch when the mood flips, hard cuts by default). CLAUDE.md routing and a
  `templates/storyboard_explainer.json` starter are added.
- New optional uv dependency group `gen` (`mlx-audio`). The default install is unchanged.

### Models and dependencies

| | Licence | Disk | RAM | Expected speed (32 GB M5) |
|---|---|---|---|---|
| Kokoro-82M weights (+ voice presets) | Apache-2.0 | ~0.35 GB, one download | < 1 GB | many times faster than real time; a 2-minute script in well under a minute (the pilot measures it) |
| `mlx-audio` | MIT (confirmed in task 1.2) | small; `mlx` is already installed | — | — |
| `espeak-ng` library, bundled in the `espeakng-loader` wheel that `misaki[en]` pulls in; phonemiser for non-English and English words it doesn't know | GPL-3.0; loaded by the tool on this machine and not redistributed by the repo; it does not change the licence of the audio we produce | ~20 MB | — | — |
| spaCy `en_core_web_sm` (English G2P), pinned in the `gen` group | MIT | ~13 MB | — | — |
| Whisper large-v3-turbo (word times) | MIT, **already cached** | 0 GB new | ~2 GB while it runs | ~3 s per 20 s of speech (measured on this Mac) |

Total new download: about 0.4 GB. Supported languages are English (US/UK), Spanish, French,
Italian, Portuguese (BR) and Hindi. Kokoro also speaks Japanese and Mandarin, but those need extra
`misaki` extras (`pyopenjtalk`, `unidic`, `jieba`) that the `gen` group doesn't install, so they're left
out for now. A storyboard in another language gets an error from `check`.

### Out of scope

- Image generation, depth maps and parallax (dropped; they don't fit this look).
- Voice cloning, or matching a real person's voice.
- Lip-sync, facial animation, or a figure that walks across the frame (poses change in place; the
  figure can slide between slots).
- Widgets for one brand's product UI. Widgets are generic; a brand's look comes from its colours and
  fonts.
- Splitting one long recorded voice file into scenes automatically. Recorded narration is supplied
  per scene.
- Short-form talking-head overlays (`tools/shortform.py`) are not changed.

## Capabilities

### New Capabilities

- `voice-generation`: local text-to-speech, giving reproducible, cached narration clips per line,
  with language/voice validation and licence-safe models.
- `explainer-graphics`: the vector vocabulary for narrated explainers: the headline that builds
  with the voice, the character rig and poses, the widget set, grid backgrounds and the progress
  bar.

### Modified Capabilities

- `storyboard-video`: scene primitives gain `BeatScene`; scene durations can come from narration;
  per-scene narration is assembled into the voice track; word cues (`@word`) resolve to times;
  `check` validates cues, languages and voices.

## Impact

- **Tools**: new `tools/gen/voice.py`; `tools/storyboard.py` (narration step, auto durations,
  narration track, word alignment, cue resolution, new checks); reuses `tools/transcribe_local.py`.
- **Remotion** (`tools/motion/src/`): new `explainer/` folder (Headline, Figure + poses + props,
  widgets, grid background), `scenes/BeatScene.tsx`, `ProgressBar` overlay, registry entries.
- **Skills**: `motion-graphics` (new section, primitive table, workflow). `short-form-pro` and
  `video-use` are not changed, though `short-form-pro` could reuse the widgets later.
- **Docs**: CLAUDE.md routing and Gotchas (`uv sync --group gen`), new
  template.
- **Dependencies**: `pyproject.toml` group `gen`; no new npm packages.
