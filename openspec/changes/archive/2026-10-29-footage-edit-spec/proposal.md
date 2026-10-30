# Proposal

## Why

Today a headless job can make a video from a storyboard, but it can't edit raw footage safely. A polished short runs from `edit/build.py`, which is Python, and a plain cut needs someone at the CLI. Editing footage someone uploads is the workflow most people need, so a hosted runner has to be able to edit raw footage for untrusted users. That means the whole edit is described as data the engine validates, and nothing in a job can execute code, inject ffmpeg filters or reach outside the project.

A second gap shows up as soon as the footage comes from strangers. Every short made so far started from 1080x1920, 30 fps, SDR footage, and `tools/shortform.py` quietly assumes it: its crop math is fixed to 1080x1920. Phones record 4K, HDR (HLG / Dolby Vision), 60 fps and variable frame rate, and some people film horizontally.

## What Changes

- **Short-form edit spec (`edit/short.json`).** A JSON form of everything `templates/shortform_build.py` and past `build.py` files express:
  - sources and face centres
  - segments with zoom, look, freeze and edge locks
  - brand, caption fixes, per-word caption fixes, caption skips and emphasis
  - overlay events, including behind-the-speaker events
  - SFX and public files

  Times that `build.py` computes with Python lambdas (`W1("word")`, `seg_end(i)`) become declarative anchors: a word in a take, or a segment's start or end, plus an offset. The same `tools/shortform.py` engine renders it.
- **`tools/shortform.py` gains a spec loader and `check`.**
  - The loader builds a `Project` from the spec.
  - `check` validates the spec and reports the planned timeline, the edge refinement report, edge energy, echo and SFX warnings. It changes no files.
  - `stills` renders frames of the finished short at chosen output times.
  - The existing `build.py` path keeps working unchanged.
- **The engine accepts any vertical source size** by scaling to the 1080x1920 work frame instead of assuming it, so face centres and zooms behave the same for 4K and 1080p takes.
- **Source conform (`tools/conform.py`).** It turns any upload into an edit-ready file in `edit/conformed/`:
  - SDR BT.709 (HDR is tone-mapped)
  - constant frame rate (24, 25 or 30 kept; 50/60 and variable rates go to 30)
  - 48 kHz audio, rotation applied
  - 9:16 output either scaled (vertical sources) or face-centred cropped (horizontal sources); or kept at source orientation for plain cuts

  The original is never touched. It records the mapping from conformed file to original in `edit/conformed/conform.json`.
- **Planner read-outs.** These let a remote planner that never sees video write a spec from text and stills:
  - a packed transcript (`takes_packed.md`, through the existing video-use helper)
  - still frames and a contact sheet of any source at chosen times
  - an automatic face-centre suggestion per take, from the existing person matte
- **New headless ops in `tools/run_job.py`:**
  - `conform`
  - `pack`
  - `frames`
  - `face`
  - `shortform` (`check | stills | render`, from `edit/short.json`)
  - `cut` (`check | render`): a plain EDL cut at any aspect through video-use's `render.py`. The EDL is validated first: sources and overlay files confined to the project, grade limited to named presets, `auto` or `none` (no raw ffmpeg filter strings), subtitles either generated or a project file.
- `shortform.build` stays, still marked trusted input only. The new ops are the ones a hosted runner exposes.
- `tools/new_project.py --shortform` also writes `edit/short.json` from a new `templates/short.json`.
- Skills and docs: `short-form-pro` documents `short.json` as the way to describe a short and `build.py` as the escape hatch for one-off code. CLAUDE.md documents `conform` and the validated `cut` op for video-use work, and its routing and the "Linux / Docker" section list the new ops.

## Out of scope

- Moving face tracking (a crop that follows a speaker who walks). Conform uses one face centre per take, which suits tripod and selfie talking heads.
- Multicam layouts, diarized interviews and music-driven montage as hosted ops. They keep their CLI routes.
- New overlay components or caption styles. The spec uses the existing `tools/motion/` registry and brand kits.
- Automatic edit planning (choosing cuts, hooks or zooms). The engine validates and renders. Deciding the edit stays with whoever authors the spec.
- The hosted service itself (queue, storage sync, accounts). That lives outside this repo.
- Converting existing `build.py` files to `short.json` automatically. They keep running as they are.

## Capabilities

### New Capabilities

- `shortform-spec`: the data-only short-form edit spec. Its format, validation (`check`), anchors, stills and rendering through the short-form engine, which gives the same result as the equivalent `build.py`.
- `footage-prep`: getting raw uploads ready to edit and readable without watching them. Conform to an edit-ready format, packed transcript, source stills and contact sheet, face-centre suggestion.

### Modified Capabilities

- `headless-jobs`: the fixed op list grows to include `conform`, `pack`, `frames`, `face`, `shortform` and `cut`. `cut` validates its EDL so no raw ffmpeg filter or outside path can reach the renderer.
- `project-setup`: the short-form starter also writes `edit/short.json`.

## Impact

- **Code:** `tools/shortform.py` (spec loader, `check`, `stills`, source-size handling), new `tools/conform.py` and `tools/short_spec.py` (schema and anchor resolution), `tools/run_job.py` (six ops), `tools/new_project.py`, `templates/short.json`.
- **Vendor:** `vendor/video-use/helpers/render.py` and `pack_transcripts.py` are called as they are, never edited. The `cut` op sanitises the EDL before calling `render.py`.
- **Skills and docs:** `.claude/skills/short-form-pro/SKILL.md` and CLAUDE.md. The `video-use` skill is a symlink into `vendor/` and isn't edited, so its notes on `conform` and `cut` go in CLAUDE.md.
- **Workflows affected:**
  - `short-form-pro` gains the JSON form; `build.py` still works.
  - `video-use` cuts can run headless.
  - `motion-graphics` is unchanged.
- **Dependencies:** none new. Conform uses ffmpeg (`zscale` tone-mapping is already in the ffmpeg-full build and the Docker image). The face suggestion reuses the person matte backends (Apple Vision on the Mac, MediaPipe on Linux), so there are no new models, licences or disk cost.
- **Speed (32 GB M-series Mac, estimate):**
  - conforming a 60 s 4K HDR clip: about 20–40 s with libx264 (`veryfast`, intermediate quality); the hardware encoder for previews
  - `check`: under 2 s
  - face suggestion: about 2–4 s per take (matte on 5 sampled frames)
