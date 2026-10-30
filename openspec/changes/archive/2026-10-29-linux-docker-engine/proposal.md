# Proposal

## Why

The engine only runs on an Apple Silicon Mac: transcription (`mlx-whisper`), local voice (`mlx-audio`) and the person matte (Swift + Apple Vision) have no other path. That blocks running the same tools on a Linux server, in CI, or for anyone without a Mac, and there is no way to drive a workflow step without a person typing commands. This change makes the engine portable to Linux inside one Docker image and adds a JSON-in/JSON-out job runner, while keeping the macOS defaults exactly as they are.

## What Changes

- **Transcription backends.** `tools/transcribe_local.py` picks a backend at runtime: `mlx-whisper` on Apple Silicon (unchanged default), `faster-whisper` (CTranslate2, CPU int8) everywhere else. Both write the same Scribe-shaped JSON; only `source.engine` differs. A `--backend auto|mlx|faster-whisper` flag overrides the choice.
- **Voice backends.** `tools/gen/voice.py` runs Kokoro-82M through `mlx-audio` on Apple Silicon (unchanged) and through the reference `kokoro` package (PyTorch, CPU) elsewhere. Same presets, languages, pauses, trimming and sidecar; the backend joins the cache key so clips from one backend are never silently reused by the other.
- **Person matte backends.** `tools/person_matte.py` keeps Apple Vision on macOS and adds an open segmentation model (MediaPipe selfie segmenter, Apache-2.0) on Linux, writing the same grey matte video. `tools/shortform.py` behind-the-speaker text works on both.
- **Platform-aware dependencies.** `pyproject.toml` uses environment markers so a Mac install pulls only the MLX packages and a Linux install only the portable ones. Heavy ML packages stay in optional groups (`gen`, new `matte`).
- **Docker image.** A `Dockerfile` (Debian + Python 3.12 + uv, ffmpeg with libass/freetype, Node LTS + Remotion's headless Chrome and its system libraries, auto-editor, pinned video-use helpers, synthesized SFX). Model weights are baked in at build time by default (build arg to skip), so a container starts offline. CPU only.
- **Headless job runner.** New `tools/run_job.py`: reads one job JSON (an operation from a fixed allow-list plus arguments), runs it, prints one result JSON (status, output files, timings, error) and exits non-zero on failure. Paths are confined to the job's project directory; there is no free-form command.
- `scripts/setup.sh` stays the Mac setup; a short `docs`-level note and CLAUDE.md gain a "Linux / Docker" section.

No breaking changes on macOS: same commands, same outputs, same defaults.

## Capabilities

### New Capabilities

- `local-transcription`: offline word-level transcription that writes the Scribe-shaped JSON on any platform, with the backend chosen per platform.
- `person-matte`: a grey person matte for a clip window, same contract on macOS and Linux.
- `engine-container`: the Docker image that runs the engine's tools on Linux, what it contains and how it is checked.
- `headless-jobs`: running one engine operation from a JSON job and getting a JSON result, without a person typing commands.

### Modified Capabilities

- `voice-generation`: adds a requirement that synthesis works on Linux through a portable Kokoro backend, with the backend in the cache key.

## Impact

- **Tools changed:** `tools/transcribe_local.py`, `tools/gen/voice.py`, `tools/person_matte.py`; new `tools/run_job.py`, `Dockerfile`, `.dockerignore`. `tools/shortform.py` and `tools/storyboard.py` unchanged apart from calling the backends through the same functions.
- **Skills / docs:** `CLAUDE.md` (Linux/Docker section, setup gotchas), `.claude/skills/motion-graphics/SKILL.md` (voice setup line names both backends). Workflows affected only in where they can run: **video-use** (transcription), **short-form-pro** (behind-the-speaker matte), **motion-graphics** (narrated explainer voice).
- **New dependencies (Linux only, via markers; nothing new on a Mac):**
  - `faster-whisper` (MIT) + CTranslate2 (MIT); Whisper large-v3-turbo weights (MIT), CTranslate2 conversion ≈ 1.6 GB on disk, ~2–3 GB RAM at int8 on CPU. On a 32 GB M-series Mac it is not used (MLX stays the backend); in Docker on that Mac (arm64, CPU) expect roughly 0.3–0.6× real time.
  - `kokoro` (Apache-2.0) + PyTorch CPU (BSD-3), ~0.7 GB installed; Kokoro-82M weights (Apache-2.0) ≈ 330 MB, < 1 GB RAM. In Docker on an M-series Mac, a 10 s line in roughly 2–5 s.
  - `mediapipe` (Apache-2.0) with the selfie segmenter model (Apache-2.0, a few MB), < 500 MB RAM, roughly 20–60 frames/s at 1080p on CPU.
  - Image: Debian `ffmpeg` (LGPL/GPL build, used inside the image, not redistributed as a binary by this repo), Node LTS, Remotion's Chrome Headless Shell. Expected image size 4–6 GB with weights baked in.
- **Licensing note:** Remotion's own licence (free for individuals and small teams, company licence otherwise) applies unchanged wherever the image is run; the image does not change that.
- **Out of scope:**
  - Any hosting, cloud resources, queues, MCP server or web UI: this change only makes the engine runnable on Linux and from JSON.
  - Driving the short-form engine from a JSON spec instead of a per-project `build.py` (the runner's `shortform.build` op runs an existing `build.py`; a data-only spec is a follow-up change).
  - GPU images, Windows-native (non-Docker) support, and `site_capture.py` in the image (Playwright browsers not installed; follow-up if needed).
  - Speaker diarization on Linux (same limitation as local transcription today).
  - Changing any macOS default, model or output.
