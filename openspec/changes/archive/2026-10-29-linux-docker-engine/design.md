# Design

## Context

See proposal.md for why. Current state that shapes the approach:

- Mac-only code lives in three places: `tools/transcribe_local.py` (imports `mlx_whisper` inside `transcribe_one`), `tools/gen/voice.py` (`_load_model`, `_use_dialect` and `synthesize_many` use `mlx_audio`; the model's pipeline mirrors the reference `kokoro` package's `KPipeline`, including the `g2p` attribute `_use_dialect` swaps), and `tools/person_matte.py` (shells out to `person_matte.swift`). `videotoolbox` appears only in CLAUDE.md, never in tools, so encoding needs no change.
- Everything else is already portable: ffmpeg/ffprobe via subprocess, Remotion via `npx remotion` with `cwd=tools/motion`, librosa/numpy, the video-use helpers.
- `pyproject.toml` puts `mlx-whisper` in the default install and `mlx-audio` in the `gen` group; `uv.lock` is a universal lock, so platform markers resolve cleanly.
- Paid tools already read keys from the environment before falling back to `vendor/video-use/.env`, so containers can pass keys as env vars with no code change.
- `tools/storyboard.py` exposes `check / voice / sheet / stills / render` through a `Story` class; `tools/shortform.py` is driven by a per-project `build.py` (Python data file).

## Goals / Non-Goals

**Goals:**
- Same tool commands and outputs on macOS; a Linux path selected automatically at runtime.
- One image that runs every local tool offline, CPU only, as small as reasonable.
- A runner a queue worker can call safely: allow-listed ops, schema-checked args, confined paths, JSON result.

**Non-Goals:**
- Speed parity with MLX/Metal on Linux CPU.
- Bit-identical audio or timestamps across backends (only the contracts in the specs).
- Making `shortform.build` safe for untrusted input (it executes the project's `build.py`; see Risks).

## Decisions

### 1. Backend selection inside each tool, not a new abstraction layer

Each of the three tools gets a small `pick_backend(requested: str | None)` that returns `mlx`/`vision` on `sys.platform == "darwin" and platform.machine() == "arm64"` (Vision: macOS with `swift` available) and the portable backend otherwise; `--backend` overrides. The rest of each tool keeps one code path (audio extraction, Scribe flattening, pause/trim logic, ffmpeg matte encode).
*Alternative:* a shared `tools/backends/` package. Rejected: three tools, one switch each; a package adds indirection without reuse (rule: extend existing engines).

### 2. Transcription: faster-whisper, turbo weights, int8 on CPU

`faster-whisper` (MIT) on CTranslate2 with the large-v3-turbo conversion, `compute_type="int8"`, `word_timestamps=True`, same `language`, `initial_prompt` (VERBATIM_PROMPTS) and `condition_on_previous_text=False`. Its segments/words are adapted to the dict shape `to_scribe_words` already consumes (`word`, `start`, `end`, `probability`), so the output code is shared. `source.engine` becomes `faster-whisper`.
*Alternatives:* `openai-whisper` (PyTorch, much slower on CPU); `whisper.cpp` (fast, but a compiled binary and a different word-timing path). faster-whisper gives the closest options to mlx-whisper with the least glue.

### 3. Voice: reference `kokoro` package on PyTorch CPU

On Linux, `voice.py` loads `kokoro.KModel` + `KPipeline` per language code (weights `hexgrad/Kokoro-82M`, Apache-2.0, same voices). A thin adapter exposes what `synthesize_many` uses today: `sample_rate`, `generate(text, voice, speed, lang_code)` yielding float arrays, and the per-language pipeline for `_use_dialect`. Pauses, trimming, sidecar and `pieces()` stay shared. The sidecar gains `backend`, and `is_fresh` compares it, so a Mac clip is re-synthesised on Linux (spec: Portable backend).
PyTorch is pulled from the CPU wheel index for Linux only (`[[tool.uv.index]]` `pytorch-cpu`, `explicit = true`, `[tool.uv.sources] torch` with a `sys_platform == 'linux'` marker); otherwise Linux resolves the CUDA build (several GB).
*Alternative:* `kokoro-onnx` + onnxruntime (smaller, ~50 MB vs ~0.7 GB). Rejected for now: its own phonemiser path differs from misaki's, which would break dialect handling and the pronunciation behaviour already in the specs. Revisit only if image size becomes a problem.

### 4. Person matte: MediaPipe selfie segmenter

On Linux, `make_matte` keeps the ffmpeg frame extraction and the ffmpeg gblur + ProRes encode; only the middle step changes: each PNG frame goes through MediaPipe's ImageSegmenter (selfie segmenter, Apache-2.0, model file in the models dir) and its confidence mask is written as an 8-bit grey PNG. A light temporal smoothing (exponential moving average across frames, α≈0.6) reduces flicker before the existing blur.
*Alternatives:* Robust Video Matting (GPL-3.0: out), BiRefNet (MIT, too slow on CPU per frame), rembg/U²-Net human (MIT, slower and worse edges), MODNet (Apache-2.0, better hair, but weights only on Google Drive and needs an ONNX export). MediaPipe is the fastest commercially licensed option with a stable download; MODNet is the fallback (see Risks).

### 5. Dependencies by marker and group

- Default install: unchanged (`mlx-whisper` gets a `sys_platform == 'darwin' and platform_machine == 'arm64'` marker so a Linux default install no longer fails on it).
- New group `asr`: `faster-whisper` with a `sys_platform == 'linux'` marker. Without it, Linux transcription exits with `uv sync --group asr`.
- `gen` group: `mlx-audio` gets the Apple marker; `kokoro` gets the Linux marker; `torch` is listed unmarked so `[tool.uv.sources]` can route it (CPU index on Linux, PyPI elsewhere; see Verification Notes); `misaki` and the spaCy model stay unconditional.
- New group `matte`: `mediapipe` with the Linux marker.
A Mac `uv sync` therefore installs exactly what it does today.

### 6. Image layout

- Base `python:3.12-slim-trixie` (Debian 13): its `ffmpeg` 7.1 package is built with libass, freetype and libx264, so `subtitles`, `ass` and `drawtext` work without a custom build. `uv` copied from its official image; Node 22 LTS copied from `node:22-*-slim`.
- System packages: ffmpeg, the Chrome Headless Shell libraries Remotion documents for Debian (nss, atk, gbm, asound, xkbcommon, pango, cairo, cups…), `fontconfig` + a basic font set, `git`, `espeak-ng` is not needed (bundled by `espeakng-loader`).
- Steps: copy repo (`.dockerignore` excludes footage/, brands/* except _template, exports/, vendor/, .env*, node_modules, __pycache__) → `uv sync --frozen --group gen --group asr --group matte` → clone video-use at a pinned commit (`ARG VIDEO_USE_REF`) into `vendor/video-use` → auto-editor's pinned GitHub release binary for the build arch (`ARG AUTO_EDITOR_VERSION`; PyPI's 29.x has a different CLI) → `npm ci` in `tools/motion` + `npx remotion browser ensure` → `uv run tools/sfx_synth.py` → if `ARG WITH_MODELS=1`, `run_job.py --prefetch` downloads Whisper, Kokoro (+ every voice preset) and the MediaPipe model into `/opt/models` (`HF_HOME`), with `HF_HUB_OFFLINE=1` set afterwards.
- Runs as a non-root user; `WORKDIR /engine`; volumes at `/engine/footage`, `/engine/brands`, `/engine/exports`, `/engine/assets/music`.
- `ENTRYPOINT ["uv", "run", "--no-sync", "tools/run_job.py"]`; `docker run … --self-check` prints the toolchain report.
- Multi-arch by construction (the one arch-specific download, auto-editor, picks its binary from `uname -m`); local builds on an M-series Mac use arm64, servers use amd64.

### 7. Runner: in-process calls, hand-written schemas

`tools/run_job.py` maps each op to a function plus an argument schema (a dict of name → type/choices/required, validated by a ~30-line checker; no new dependency). Ops call existing functions in-process (`transcribe_one`, `Story(...).check/voice/sheet/stills/render`, `make_matte`, `synthesize_many`), with `contextlib.redirect_stdout(sys.stderr)` so only the result JSON reaches stdout. `SystemExit` and exceptions become `ok: false` with a one-line `error` (traceback to stderr). `inventory` runs ffprobe on every media file directly under `footage/<project>/` and writes `edit/inventory.json`. `shortform.build` runs `uv run footage/<project>/edit/build.py [--preview]` as a subprocess. Outputs are detected as files created or modified under the project during the job.
Path confinement: every path argument is resolved with `Path.resolve()` (symlinks followed) and must be inside `footage/<project>/`; the project name must match `^[a-z0-9]+(-[a-z0-9]+)*$`.
*Alternative:* shelling out to each CLI. Rejected: stdout mixing, argument re-quoting, and losing structured errors.

## Risks / Trade-offs

- [CPU transcription is slow on long footage] → int8 turbo; the job reports `seconds`; GPU image is a later change.
- [Word timestamps differ between backends] → cut points already come from measured RMS silence (`refine_edges`), not word starts; the specs only require ordering and bounds.
- [MediaPipe edges/hair are weaker than Apple Vision; possible flicker] → temporal smoothing + existing blur; Mac keeps Vision; if stills show unacceptable edges in verification, switch the Linux backend to MODNet (same contract, task noted).
- [No MediaPipe wheel for linux/arm64] → verified first in tasks; if missing, arm64 local builds skip the matte group (self-check reports it) and the MODNet fallback is used.
- [PyTorch resolves to the CUDA build] → explicit CPU index source with a Linux marker; build check asserts `torch.version.cuda is None`.
- [Image size 4–6 GB → slow first pull] → acceptable for workers; `WITH_MODELS=0` gives a small image that downloads on first use.
- [`shortform.build` executes project Python] → documented in the runner's help and CLAUDE.md as trusted-input only; a hosted caller must not let users author `build.py`. A data-only short-form spec is a follow-up change.
- [Licences inside the image] → ffmpeg (LGPL/GPL Debian build) and Remotion's licence apply to whoever runs the image; the image is not published publicly by this repo.

## Verification Notes

- **Linux wheels (task 1.1).** `uv pip compile --only-binary :all: --python-version 3.12` with the PyTorch CPU index resolves binary wheels on both `x86_64-manylinux_2_28` and `aarch64-manylinux_2_28`: `faster-whisper 1.2.1`, `ctranslate2 4.8.4`, `kokoro 0.9.4`, `torch 2.15.0+cpu` (no `nvidia-*` packages), `mediapipe 1.2.0`. MediaPipe has an arm64 wheel, so the MODNet fallback is not needed for packaging; it remains the fallback only if matte quality fails verification.
- **Mac install unchanged (task 1.2).** `torch` is listed directly in `gen` (unmarked) because `[tool.uv.sources]` only binds direct dependencies: with a Linux-only entry the Mac's transitive torch (via mlx-whisper) was resolved from the CPU index and moved 2.14.1 → 2.15.0. A second source entry keeps non-Linux torch on PyPI. `uv pip freeze` before/after on the Mac is identical for `uv sync`, `--group gen` and `--group gen --group asr --group matte`.
- **auto-editor (deviation from §6).** PyPI stops at 29.x (different CLI from the Mac's Homebrew 31.x), so the image downloads the pinned GitHub release binary (`ARG AUTO_EDITOR_VERSION=31.7.2`, `auto-editor-linux-{x86_64,aarch64}`) instead of `uv tool install`.
- **Matte edges (refines §4).** MediaPipe's full-size confidence mask is blocky (the model runs at 256x256). The frame is segmented at 360 px wide and the mask upscaled bicubically before the EMA + existing blur: smoother edges, ~3× faster (111 frames at 1080x1920: 10 s vs 33 s on an M-series Mac), IoU 0.96 against Apple Vision on a talking-head window. mediapipe pulls `opencv-contrib-python`, so the image adds `libgl1` and `libglib2.0-0`.
- **Image (tasks 3.1–3.3).** arm64 build on an M-series Mac: `--self-check` reports every item ok (Python 3.12.16, ffmpeg 7.1 with subtitles/ass/drawtext, Node 22, Remotion's headless shell, auto-editor 31.7.2, video-use helpers, faster-whisper, torch, mediapipe). `torch 2.15.0+cpu`, `torch.version.cuda is None`. Build context: `footage/` and `exports/` empty, `brands/` holds only `_template`, the only `.env*` file is video-use's upstream `.env.example` (no keys). Size with `WITH_MODELS=0`: 4.0 GB unpacked filesystem (`docker image ls` shows 5.62 GB, which counts compressed + unpacked layers); the venv is 2.5 GB of it (torch 0.69 GB) and Remotion's node_modules 0.53 GB.
- **Voice cache key.** For `mlx` the key is byte-for-byte the pre-change key (so Mac clips and the storyboard word-time signatures built from it stay cached); the `torch` key adds `backend` and has a different `model`, so clips never cross backends. The sidecar always records `backend`.

- **faster-whisper input.** faster-whisper 1.2.1 decodes files through PyAV with an argument (`metadata_errors`) the resolved PyAV no longer accepts; the tool already extracts 16 kHz mono PCM with ffmpeg, so it passes the samples as an array and PyAV is never used. Container: 30 s English clip in ~7 s (int8, arm64); Spanish voice-tool clip 25/26 script words.
- **Native libraries.** MediaPipe's native library links `libEGL.so.1`/`libGLESv2.so.2` and is only loaded when a task is created, so `find_spec` alone missed it; the image adds `libegl1 libgles2`, and `--self-check` now loads every backend (MediaPipe's native library included) instead of only finding the package.
- **Offline image (task 8.1).** `WITH_MODELS=1` (default): 5.8 GB unpacked, of which 1.9 GB weights in `/opt/models`; with `--network none` a container transcribes, synthesises and renders a still. `docker image ls` reports 9.4 GB (compressed + unpacked).
- **Fonts.** The neutral theme names macOS fonts (Georgia, Helvetica Neue, Menlo); on Linux they fall back to Noto Serif/Sans. Branded projects ship font files and match. Documented, not changed (would alter Mac defaults).
- **Pilot (task 9.1).** Container: storyboard preview 9.70 s (planned 9.70), −14.0 LUFS / −1.5 dBTP; short preview with one behind event −14.0 LUFS / −1.5 dBTP, text visible on the background and hidden behind the head (pixel diff vs a build without the event: title area mean 53, wall 0.2). Mac: the same pilot rendered by HEAD and by this change gives identical video frames and audio for both the storyboard and the short.

## Migration Plan

No migration on macOS: same commands, outputs and defaults; existing voice clips stay cached on the Mac (backend in the sidecar matches). Rollback is reverting the change; nothing persistent depends on the image yet.

## Open Questions

None open. Resolved: faster-whisper ships with `compute_type="int8"` and its default beam size; the pilot met the transcription specs (ordering, bounds, 25/26 Spanish script words) without further tuning.
