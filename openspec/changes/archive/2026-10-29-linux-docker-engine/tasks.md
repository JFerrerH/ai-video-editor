# Tasks

## 1. Platform-aware dependencies

- [x] 1.1 Check that Linux wheels exist for `faster-whisper`/`ctranslate2`, `kokoro`, CPU `torch` and `mediapipe` on both `linux/amd64` and `linux/arm64`; record the result (and the MODNet fallback decision if `mediapipe` has no arm64 wheel) in design.md; verify by `uv pip compile` dry runs for each platform (`--python-platform x86_64-manylinux_2_28` / `aarch64-manylinux_2_28`)
- [x] 1.2 In `pyproject.toml`: Apple marker on `mlx-whisper` and `mlx-audio`; new `asr` group (`faster-whisper`, Linux marker); `kokoro` + `torch` in `gen` with Linux markers; new `matte` group (`mediapipe`, Linux marker); `pytorch-cpu` explicit index as the Linux source for `torch`; run `uv lock` and verify `uv sync` and `uv sync --group gen` on the Mac install the same packages as before (diff `uv pip freeze` before/after shows only the lockfile change)

## 2. Runner skeleton

- [x] 2.1 Create `tools/run_job.py`: read a job from a file or stdin, validate `project` name and `op`, the small schema checker, path confinement helper, result JSON on stdout / logs on stderr, `ok:false` + one-line `error` on any failure; add `tools/tests/test_run_job.py` covering unknown op, unknown argument, escaping path (`../`, absolute, symlink out of the project) and invalid project name; verify `uv run pytest tools/tests/test_run_job.py` passes
- [x] 2.2 Add the `inventory` op (ffprobe every media file directly under `footage/<project>/` → `edit/inventory.json`) and a `--self-check` flag that reports python, ffmpeg filters (`subtitles`, `ass`, `drawtext`), node, Remotion browser, auto-editor, video-use helpers and each backend; verify with a test project under `footage/` (gitignored) and the self-check output on the Mac

## 3. Docker image

- [x] 3.1 Write `Dockerfile` and `.dockerignore` per design §6 (trixie slim, uv, Node 22, ffmpeg, Remotion browser libs, pinned video-use, auto-editor, `npm ci` + `remotion browser ensure`, SFX synth, non-root user, volumes, entrypoint) with `WITH_MODELS=0` support only for now; verify `docker build` succeeds for arm64 on the Mac and `docker run --rm <img> --self-check` reports ffmpeg filters, node, Remotion browser, auto-editor and video-use as ok
- [x] 3.2 Verify the build context excludes gitignored work: `docker run --rm --entrypoint sh <img> -c 'ls footage brands exports; find / -name ".env*" 2>/dev/null'` shows only `brands/_template` and no `.env` files
- [x] 3.3 Verify `torch.version.cuda is None` inside the image (CPU wheel) and the image size is recorded in design.md

## 4. Transcription backend

- [x] 4.1 Add `pick_backend` + `--backend auto|mlx|faster-whisper` to `tools/transcribe_local.py`; adapt faster-whisper segments to the shape `to_scribe_words` reads; record `source.engine`/`model`; clear install hint (`uv sync --group asr`) when a forced backend is missing; unit-test backend choice and the segment adapter with monkeypatched platform values; verify tests pass and a Mac run still reports `mlx-whisper` with an unchanged JSON shape
- [x] 4.2 Add the `transcribe` op to the runner; verify inside the container on a 30 s English clip and a Spanish voice-tool clip: JSON exists, `source.engine` is `faster-whisper`, times are ordered and within the ffprobe duration, ≥ 80% of the Spanish script's words appear, second run prints `cached:`
- [x] 4.3 Update the `transcribe_local.py` docstring and CLAUDE.md's "Transcription: local first" section to name both backends; verify the documented commands run as written

## 5. Voice backend

- [x] 5.1 Add the Kokoro (PyTorch CPU) adapter to `tools/gen/voice.py` (load, `sample_rate`, `generate`, per-language pipeline for `_use_dialect`), backend in the sidecar and in `is_fresh`, help text naming the backend's model id and licence; extend the voice tests for backend choice and the sidecar check; verify tests pass and a Mac re-run of an existing clip still reports `cached:`
- [x] 5.2 Add the `voice` op to the runner; verify inside the container: the spec's English line gives a ≥ 24 kHz mono WAV of 1.0–4.0 s with ≤ 50 ms edge silence; a two-sentence Spanish line has one 0.15–0.4 s gap; without the `gen` group the command prints `uv sync --group gen`
- [x] 5.3 Update `.claude/skills/motion-graphics/SKILL.md` (voice setup line) to name both backends; verify the setup command it shows works on the Mac

## 6. Person matte backend

- [x] 6.1 Add `pick_backend` + `--backend auto|vision|mediapipe` to `tools/person_matte.py`, the MediaPipe frame-mask step with temporal smoothing, model path under the models dir, and the `uv sync --group matte` hint; verify on the Mac that the Vision path output is unchanged (same dimensions/frame count as before on the same clip)
- [x] 6.2 Add the `matte` op to the runner; verify inside the container on a 1080x1920 talking-head clip with `--start 8.0 --dur 3.7`: 1080x1920, 30 fps, 111 ± 1 frames; mid-frame mean ≥ 200 in the face region and ≤ 50 in the top-left corner; read the matte still (PNG) and judge the edges; if unacceptable, switch to the MODNet fallback before continuing
- [x] 6.3 Update `.claude/skills/short-form-pro/SKILL.md` where behind-the-speaker text mentions macOS/Vision; verify the text matches the shipped behaviour

## 7. Remaining runner ops

- [x] 7.1 Add the `storyboard` op (`check`, `voice`, `sheet`, `stills`, `render` with `preview`/`export`) calling `Story` in-process; verify in the container that `stills` through the runner and through `tools/storyboard.py` write the same file names and dimensions on the same project
- [x] 7.2 Add `shortform.build` (subprocess `uv run footage/<project>/edit/build.py [--preview]`) and document in its help that it executes project code (trusted input only); verify a template short builds a 720p preview in the container

## 8. Offline image and docs

- [x] 8.1 Add `--prefetch` to the runner (Whisper turbo, Kokoro weights + every voice preset, MediaPipe model into `/opt/models`) and wire `WITH_MODELS=1` as the Dockerfile default with `HF_HUB_OFFLINE=1`; verify a container with `--network none` transcribes a clip, synthesises a line and renders one storyboard still
- [x] 8.2 Verify no secrets in the image: search the filesystem for `.env` files and for `FAL_API_KEY`, `FAL_KEY`, `ELEVENLABS_API_KEY` values; verify a paid tool reads its key from `-e FAL_API_KEY=...` at run time (estimate-only run, nothing sent)
- [x] 8.3 Add a "Linux / Docker" section to CLAUDE.md (build, self-check, run a job, mounts, `shortform.build` trusted-only, CPU speed expectations) and a "Which tool" row for `run_job.py`; verify each documented command runs as written

## 9. Integration pilot

- [x] 9.1 In the container (mounts for `footage/` and `brands/_template`), render a pilot under `footage/linux-pilot/`: a short narrated storyboard (voice → check → stills → preview render) and a vertical short from a talking-head clip with one behind-the-speaker event; pull frames at each cut and mid-event, read the PNGs, and measure loudness (`ffmpeg -af ebur128`) to report integrated LUFS and true peak against the delivery spec; run the same pilot on the Mac and confirm Mac outputs and defaults are unchanged

## Workflow follow-up

- Run `/opsx:verify`, then archive the change after review.
- Merge `feat/linux-docker-engine` into `main`, tag a release, and bump the engine pin in the product repo that consumes this engine.
