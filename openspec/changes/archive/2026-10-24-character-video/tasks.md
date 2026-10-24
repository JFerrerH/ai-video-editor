# Tasks

## 1. Paid-call foundation

- [x] 1.1 Add the uv dependency group `cloud` with `fal-client` (pinned) in `pyproject.toml`; note in the group comment that tools run with `uv run --group cloud`
- [x] 1.2 `tools/gen/fal.py`: key loading (`FAL_API_KEY` / `FAL_KEY` from env or `vendor/video-use/.env`, never printed), model registry (MiniMax H3 Max Turbo default, Kling 2.5 Turbo Pro, Kling 3.0 Pro/Standard, Nano Banana edit) with parameter names, durations and listed prices
- [x] 1.3 In `fal.py`: `plan()` estimate printout, `--budget` guard (default $2, abort before any request), upload/subscribe/download helpers, append-only `gen_spend.jsonl` and a total printer
- [x] 1.4 Unit tests in `tools/tests/` for duration rounding (any vs fixed lists), estimate maths, budget refusal and missing-key refusal (no network)

## 2. Shot list, keyframes and animation

- [x] 2.1 `templates/shots.json` with a neutral world and cast ("hero", "guide"), one `frame` shot, one `base` group shot and one `library` shot; schema validation shared by the tools (unknown cast, missing still, empty `camera`)
- [x] 2.2 `tools/gen/keyframes.py`: prompt builder (craft rules in code, world/cast from data), `base` edits, `--n` candidates, skip existing, labelled contact sheet in `edit/verify/`
- [x] 2.3 `tools/gen/animate.py`: prompt = motion + camera + fixed tail, `--model`, `--dur 5|10|fit` (fit reads `timeline.json`, +0.2 s handle, rounds up for fixed-duration models, refuses over-max), `--suffix`, parallel, skip existing and `library` shots, frame strip per clip
- [x] 2.4 Tests for prompt building and shot-list validation (no network)

## 3. Narration and base take

- [x] 3.1 `tools/gen/voice_cloud.py`: ElevenLabs via `urllib`, WAV 48 kHz mono + sidecar (cache key incl. voice/model/settings, provider, duration), respellings, cache skip, library-voice add, 402 plan error with usable voices, commercial-licence warning, character budget from `/v1/user/subscription`
- [x] 3.2 `tools/shotcut.py`: `--plan` (timeline only) and full render to `base.mov` + `timeline.json` (lead 0.15 s, tail 0.25 s, min 2.0 s, hard cuts, optional music ducked, 1.5 s music fade, optional end card with 0.4 s crossfade), clips from `shots/` or the brand library, clear error for a too-short clip
- [x] 3.3 `templates/character_build.py`: data-only build on `shortform.Project` with one locked segment over `base.mov`; emphasis and word fixes relative to shot starts from `timeline.json`

## 4. Clip library

- [x] 4.1 `tools/gen/library.py`: `keyframes` / `clips` from `brands/<slug>/library/spec.json` (reusing 2.2/2.3 code paths, spend log in the library), `import` from a project with tags, `list --cast --mood --use`, `index.json` with measured durations
- [x] 4.2 `brands/_template/library/README.md` with the layout, index fields and reuse workflow (neutral examples only)

## 5. Project setup, skill and routing

- [x] 5.1 `tools/new_project.py --characters`: copy `shots.json` + `character_build.py`, fill brand, create `keyframes/`, `shots/`, `audio/`, note the brand library path, reject `--characters --shortform`; update `openspec/specs/project-setup` via this change's delta
- [x] 5.2 New skill `.claude/skills/character-video/SKILL.md`: when to use it, pipeline order (narration → plan → keyframes → animate fit → shotcut → build), library-first rule, one-shot model A/B before a batch, group shots via `base`, no "empty band" prompts, camera move in every shot, verification (frame strips, loudness), cost reporting, licence warning
- [x] 5.3 `CLAUDE.md`: routing row for character videos, the paid-API exception and its guardrails, keys in `vendor/video-use/.env`; `openspec/config.yaml` context line updated to match; one-line pointer in `short-form-pro` SKILL.md that a `shotcut.py` base take is a valid single source

## 6. Verification

- [x] 6.1 Run the unit tests and `openspec validate character-video --strict`
- [x] 6.2 Grep tracked files changed by this change for any brand, handle, person or character name from local brand kits, and for character descriptions copied from them; fix any hit
- [x] 6.3 Pilot under `footage/` (gitignored): `new_project.py --characters` for an existing brand with a library; 4-shot script (3 library clips + 1 new shot); local narration; `shotcut --plan` → animate the 1 new shot with `--dur fit` under a $0.50 budget → `shotcut` → build preview and final
- [x] 6.4 Inspect the pilot: contact sheet and frame strips read as PNGs, a frame at every cut, `timeline.json` vs narration durations, `gen_spend.jsonl` total, final at 1080x1920 with loudness -14 LUFS ± 1 and true peak ≤ -1 dBTP; record numbers in the pilot's `project.md`

## Workflow follow-up

- `/opsx:verify character-video`, then `/opsx:archive character-video` after SKILL.md and CLAUDE.md reflect the shipped behaviour.
