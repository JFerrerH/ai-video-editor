# Design

## Context

- The pilot (a gitignored project) proved the pipeline with five one-off scripts. Image edit for
  keyframes, image-to-video per shot, cloud TTS and a base-take assembler all ran on fal.ai /
  ElevenLabs; captions, cards, SFX and loudness came from `tools/shortform.py`, fed a single
  "take" covering the whole base video.
- `tools/gen/voice.py` already defines the narration clip contract: WAV + `<clip>.json` sidecar
  holding a cache key and duration. `storyboard.py` and the pilot's assembler both consume it.
- The workspace has been free/local only. This change is the first opt-in paid path; see the
  proposal's policy note.
- Lessons from the pilot that the tools must encode, not just document:
  - Generating 5/10 s takes before measuring the narration wasted ~20% of spend.
  - Four reference images in one request drifted a character off-model; adding characters to an
    approved frame did not.
  - Asking the image model for empty text bands padded frames with blurred bars.
  - Model A/B on one shot first prevented a full batch on the wrong model.

## Goals / Non-Goals

**Goals:**
- Brand-neutral tools: every brand fact (characters, world text, prompts, voices, library) comes from
  `brands/<slug>/` or the project's `edit/`, never from tracked code or examples.
- Paid calls are explicit, estimated, capped and logged, and fail closed (no key, no budget → no
  call).
- Reuse the short-form engine for everything after the base take.

**Non-Goals:**
- A generic multi-provider abstraction beyond fal.ai and ElevenLabs.
- Automatic shot-to-library matching. The agent maps lines to clips using `index.json`; the tool only
  filters.
- Quality scoring of generated clips. Verification stays frame strips read by the agent.

## Decisions

1. **One fal client module with a model registry** (`tools/gen/fal.py`). Each entry has endpoint,
   image parameter names, `durations` (`"any"` with min/max, or a list), resolution, price per
   second, and price per image for image models.
   - Keyframe and animate code share upload, subscribe, download, the estimate, the budget and the
     spend log.
   - *Alternative:* per-tool hard-coded endpoints, as in the pilot. Rejected: prices and parameter
     names differ per model (`image_url` vs `start_image_url`, float vs string durations) and would
     drift.
   - Default video model = MiniMax H3 Max Turbo (cheapest that held characters in the pilot A/B).
   - Registry prices are "listed" prices; the log says "estimated", never "charged".

2. **Budget and estimate in the shared client, not per tool.** `plan(requests) → (n, usd)` runs
   before any submit, and `--budget` defaults to $2 per run.
   - The spend log is `edit/gen_spend.jsonl` (or `library/gen_spend.jsonl`), append-only, one line
     per request.
   - *Alternative:* a global cap across runs. Deferred: runs are small and per-run caps stop the
     costly mistake (a wrong batch).

3. **`--dur fit` reads `timeline.json`, which comes from narration.** The order is:
   - narration (`voice.py` or `voice_cloud.py`), then
   - `shotcut.py --plan` (timeline only, no render), then
   - `animate.py --dur fit`.

   That way clips are generated after their lengths are known.
   - Fixed-duration models round up to the smallest allowed value.
   - *Alternative:* time-stretch clips to fit. Rejected: slowed character motion looks wrong, and
     exact generation is cheaper.

4. **`shotcut.py` is a pre-step, not a new engine.** It writes `base.mov` (H.264 CRF 14 + PCM) and
   `timeline.json`. The build template then runs `shortform.Project` with one locked segment over
   `base.mov`.
   - *Alternative:* teach `shortform.py` a "generated shots" segment type. Rejected for now: the
     base-take hand-off already works unchanged, and keeps `shortform.py` focused on cutting takes.
   - Music ducking and the end card live in `shotcut.py` because `shortform.py` has no music bus.

5. **Keyframe prompting is built from data plus fixed craft rules in code.** The rules are:
   - "keep each character exactly as in its reference; don't copy the reference backgrounds";
   - `base` edits keep existing characters;
   - no request for empty bands.

   World and cast descriptions are data from `shots.json`.

6. **Cloud voice is a separate module mirroring `voice.py`'s sidecar contract**, rather than an
   engine flag in `voice.py`.
   - The `voice-generation` spec promises no network calls, so `voice.py` keeps that promise.
   - `shotcut.py` accepts any narration folder whose WAVs have sidecars.
   - The HTTP client is the standard library (`urllib`), so there is no SDK dependency.
   - Plan limits come from the API's 402 `paid_plan_required` and `/v1/user/subscription`
     (`tier`, `character_count` / `character_limit`).

7. **Library tool reuses the same client and prompt builder.** The library's `spec.json` has the same
   shape as a project's shot list (`world`, `cast`, entries with `frame` / `motion` / `camera`), so
   one keyframe and one animate code path serve both.
   - Projects reference library clips by id (`"library": "<id>"`). `shots.json` names the brand and
     the library path (written from the project's brand by `new_project.py --characters`), which
     resolves `brands/<slug>/library/`; the tools don't parse `project.md`.

8. **Dependency:** `fal-client` goes in a new uv group `cloud`, and tools are run with
   `uv run --group cloud …`.
   - `uv run` does an inexact sync, so it doesn't strip the `gen` group; this is documented in the
     skill.
   - ElevenLabs needs no package.

9. **Neutral examples only.** Templates, skill and specs use placeholder casts like "hero", "guide",
   "a mascot", "a room". A check task greps tracked files for the pilot brand's
   name, handle and character words before the change is archived.

## Risks / Trade-offs

- [Provider prices or parameters change] → Registry entries are one place to edit. The estimate is
  labelled as listed price, and the skill says to check the provider dashboard.
- [Cheaper model's acting is subtler] → The registry keeps Kling options, and the skill says to A/B
  one shot before switching a project's model.
- [Paid path weakens the free/local stance] → Opt-in by key only, and local tools stay the defaults
  elsewhere. `config.yaml` / `CLAUDE.md` state the exception and its guardrails explicitly.
- [Brand identity leaking into the public repo] → Library and prompts live in gitignored kits, plus
  the archive-time grep check.
- [Free TTS plan used for a commercial post] → Warning on every run (spec); the skill repeats it at
  delivery.
- [768p clips upscaled to 1080p look soft in close-ups] → Documented. The skill caps punch-in crops at
  1.3x and allows a 1080p model per shot.

## Migration Plan

- No migration: the pilot project keeps its own scripts.
- After apply, a pilot under `footage/` re-cuts a short sequence with the new tools from an existing
  brand library to prove parity (task list).
- Rollback: delete the new files and the `--characters` flag. Nothing existing changes behaviour.

## Open Questions

- Whether to add a global monthly spend cap across projects. It can be added to the client later
  without changing these specs.
