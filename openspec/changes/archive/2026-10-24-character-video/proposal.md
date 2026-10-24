# Proposal

## Why

A brand can supply its own characters (mascot stills) and want videos where they act in one shared
set, with a camera move in every shot. Cut-out puppet animation was rejected for this, so the
characters need real motion from an image-to-video model. A pilot project proved the pipeline
(keyframes from reference stills → image-to-video → cut to narration → short-form engine). But it
lives as one-off scripts inside a gitignored project folder, and it cost about $10 for one reel. Most
of that went on tests, takes generated at a fixed 5/10 s and trimmed, and retakes. The same reel
redone with exact-length shots on a cheaper model cost under $1. A per-brand library of reusable
clips brings later reels to about $0.10–0.30. This change turns the pilot into brand-neutral
workspace tools, so the next brand (or the next reel) starts from a tested pipeline with cost
controls built in.

## What Changes

- New `tools/gen/fal.py`: one client for paid generators on fal.ai. It reads the key from
  `vendor/video-use/.env`, holds a model registry (endpoint, parameter names, allowed durations,
  price per second), estimates the cost of a request before sending it, enforces a per-run budget,
  and appends every paid call to the project's spend log.
- New `tools/gen/keyframes.py`: first frames for a shot list. It sends the cast's reference stills
  plus a shared "world" description to an image-edit model (default Nano Banana edit). It can build
  a group shot by adding characters to an approved keyframe (`base`), produces N candidates per shot
  and a labelled contact sheet.
- New `tools/gen/animate.py`: image-to-video per shot (motion + camera prompt). The default model is
  MiniMax H3 Max Turbo; Kling 2.5 Turbo Pro and 3.0 Pro/Standard are options. Clips are generated at
  exactly the length the narration needs (`--dur fit`) when the model accepts any duration, and at
  the smallest allowed length that covers it otherwise. Existing clips are skipped, runs in
  parallel, and each clip gets a frame strip for checking.
- New `tools/gen/voice_cloud.py`: ElevenLabs narration with the same output contract as
  `tools/gen/voice.py` (WAV + sidecar JSON with cache key and duration). It adds library voices to
  the account on demand, applies respellings, and gives a clear error for plan limits (free plan:
  no library voices through the API, no commercial licence).
- New `tools/shotcut.py`: builds the base take from a shot list. Each shot is cut to its narration
  line plus lead and tail air, with hard cuts, music ducked under the voice, and a fade to an
  optional end-card image. It writes `base.mov` and `timeline.json`. Captions, cards, SFX and loudness
  stay in `tools/shortform.py`, which takes the base take as its single source.
- New per-brand clip library convention, `brands/<slug>/library/` (gitignored with the rest of the
  kit): `spec.json`, `index.json` (cast, mood, use, duration, source), `clips/`, `keyframes/`,
  `README.md`. New `tools/gen/library.py` generates entries, imports finished project shots, and
  lists clips by tag. `brands/_template/library/README.md` documents the convention with neutral
  examples.
- New templates `templates/shots.json` and `templates/character_build.py` (data-only, like
  `shortform_build.py`), and `new_project.py --characters` to copy them.
- New skill `.claude/skills/character-video/SKILL.md` covering the workflow and cost discipline:
  reuse the library first, test one shot before a batch, generate exact durations, measure narration
  before animating. Plus a routing row in `CLAUDE.md`.
- **Policy change:** `openspec/config.yaml` and `CLAUDE.md` currently say "no paid APIs". This change
  adds an explicit, opt-in exception for character animation and cloud narration. Paid calls only
  run when the user has put a key in `vendor/video-use/.env`, always show an estimate first, stay
  under a budget, and are logged. Local tools stay the default everywhere else.

Out of scope:
- Migrating the pilot project's scripts. They stay in their gitignored project folder.
- Any brand's characters, prompts, library or voice choice. Those live only in `brands/<slug>/`.
- Local video-generation models (a ~25 GB download was declined).
- Voice cloning, lip-sync, ElevenLabs word-level alignment (Whisper still times the captions).
- Changes to Remotion components.

## Capabilities

### New Capabilities
- `character-video`: keyframes from cast reference stills in one shared set, image-to-video per
  shot with camera moves, exact-duration generation fitted to narration, cost estimate, budget and
  spend log for paid generators, and the base-take cut (shots + narration + music + end card) handed
  to the short-form engine.
- `clip-library`: the per-brand library of reusable animated clips (layout, index fields,
  generation, import from projects, lookup by tag) and the rule that a script maps to library clips
  before anything new is generated.
- `cloud-voice`: narration through a paid TTS service (ElevenLabs) with the same clip and sidecar
  contract as local voice, library-voice handling and plan-limit errors.

### Modified Capabilities
- `project-setup`: `new_project.py --characters` copies the shot-list and build templates.

## Impact

- **New code:** `tools/gen/fal.py`, `tools/gen/keyframes.py`, `tools/gen/animate.py`,
  `tools/gen/voice_cloud.py`, `tools/gen/library.py`, `tools/shotcut.py`,
  `templates/shots.json`, `templates/character_build.py`,
  `brands/_template/library/README.md`, `.claude/skills/character-video/SKILL.md`.
- **Changed:** `tools/new_project.py` (`--characters`), `CLAUDE.md` (routing row and the paid-API
  exception), `openspec/config.yaml` (context line about paid APIs). The short-form-pro skill gets a
  pointer: a base take from `shotcut.py` is a valid single source. video-use and motion-graphics are
  unaffected.
- **Dependencies:** `fal-client` (Apache-2.0, pure Python, ~1 MB) in a new optional uv group
  `cloud`. ElevenLabs is called over HTTPS with the standard library. No local model weights.
- **Cost and speed (measured in the pilot, 1080x1920 / 768p output):**
  - MiniMax H3 Max Turbo: $0.015/s listed, 5–35 s per clip.
  - Kling 2.5 Turbo Pro: $0.07/s, 1–2 min per clip.
  - Nano Banana edit: ~$0.04 per image.
  - A 50 s reel from scratch is ~$1.30; with a library, ~$0.10–0.30.
  - No local RAM or disk cost beyond the clips (~5–6 MB per 5 s clip).
- **Keys:** `FAL_API_KEY` (or `FAL_KEY`) and `ELEVENLABS_API_KEY` in `vendor/video-use/.env`, which is
  never committed.
- **Licences:** generated media follows each provider's commercial terms. A free ElevenLabs plan has
  no commercial licence, and the tool warns about this.
