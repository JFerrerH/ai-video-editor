# AI Video Editor workspace

Claude edits video here with CLI tools: ffmpeg, auto-editor, local Whisper, video-use, and Remotion. Claude never watches video. It reads transcripts, `ffprobe` data, waveforms and still frames, then cuts with ffmpeg.

This workspace serves any number of unrelated projects, clients and brands. Nothing here is tuned to one brand: per-brand taste lives in `brands/<slug>/`, per-project state in `footage/<project>/edit/project.md`.

## Layout

```
footage/<project>/        raw takes, never modified
footage/<project>/edit/   all working files for that project (video-use convention); project.md first
brands/<slug>/            one brand/client: brand.md (taste + rules), brand.json (colors, fonts, captions), fonts/, logos/, broll/, library/ (animated character clips)
brands/_template/         copy this to add a brand
assets/                   shared, brand-neutral: sfx/ (synth), luts/, music/ (licensed), fonts/
templates/                starting points: project.md, short.json, shortform_build.py, storyboard.json, storyboard_explainer.json, shots.json, character_build.py
exports/                  final deliverables: <project>_<platform>_<YYYYMMDD>.mp4
tools/                    our own helpers
vendor/video-use/         third-party skill (cloned by scripts/setup.sh, don't edit)
```

## Projects and brands

- **Start every new request with a project:** `uv run tools/new_project.py <name> --brand <slug|none> --type <type> --platforms <list> --language <code> [--shortform]`. `--type generated` (no footage) starts from a storyboard instead of raw takes. Name it `<brand-or-client>-<what>` in kebab-case ASCII. If a request continues earlier work, open that project's `edit/project.md` instead.
- **The brand comes from `project.md`, never from habit.** If it names a brand, read `brands/<slug>/brand.md` before planning and pass `brand="<slug>"` to the engine. If it says `none`, use neutral defaults and ask the user about style. Don't apply one brand's taste, examples or rejected ideas to another project. If you can't tell which brand a request belongs to, ask.
- **New brand:** copy `brands/_template/`, then fill in `brand.md` and `brand.json` from the user's site, deck or answers (`site` op below for measured colours, fonts and logo candidates). New font and logo files go in its `incoming/`; then run `uv run tools/brand_check.py brands/<slug>`, which validates them into `fonts/` and `logos/` (deleting any that fail) and checks `brand.json`. This repo is public: every kit except `_template` is gitignored and lives only on the machine that has it. Never name a client, brand, person or private project in a tracked file (skills, tools, templates, docs); use neutral examples. A missing kit means asking the user, not falling back to another brand.
- Skills hold general technique and neutral defaults. Feedback that is only taste ("I don't like yellow") goes into that brand's `brand.md`. Feedback that is about craft ("never clip a word") goes into the skill or tool.

## Which tool for what

| Task | Tool |
|---|---|
| Edit raw footage by conversation (talking head, tutorial, interview, montage) | **`video-use` skill**: read `.claude/skills/video-use/SKILL.md` and follow its hard rules |
| Fast silence / dead-air removal | `auto-editor in.mp4 --margin 0.15s -o out.mp4 --no-open` |
| Rough cut to finish in an NLE | `auto-editor in.mp4 --export resolve` (or `premiere` / `final-cut-pro`) |
| **Vertical short (Reels/TikTok/Shorts) that should look professional / keep attention** | **`short-form-pro` skill**: read `.claude/skills/short-form-pro/SKILL.md` after video-use. The edit is data in `edit/short.json` (`uv run tools/shortform.py check\|stills\|render <spec>`); `build.py` only for one-off code. Engine `tools/shortform.py`, overlays `tools/motion/` (overlays are 1080x1920 only for now) |
| Long-form (YouTube, course, webinar) | `video-use` for the cut; chapters from the transcript; Remotion for lower thirds/titles at 1920x1080 |
| Interview / podcast (multi-speaker) | `video-use`; recommend Scribe for diarization; ffmpeg `xstack`/crop for multicam layouts |
| Montage / music-driven (travel, event, product, wedding) | beat grid from `librosa` (`beat_track`) → cut list on beats → ffmpeg concat; no transcript needed |
| Captions / subtitles only | `transcribe_local.py` → SRT/ASS → burn with ffmpeg `subtitles`/`ass`, or deliver the sidecar file |
| Raw uploads from phones/cameras (4K, HDR, 60 fps, variable rate, horizontal for a vertical short) | `uv run tools/conform.py footage/<project> [--frame 9:16\|source]` → `edit/conformed/<stem>.mov` (SDR, constant 24/25/30 fps, PCM audio, same timeline so the original's transcript fits; 9:16 crops around `tools/face_centre.py`'s suggestion). Look before cutting: `tools/frames.py <take> --at … --sheet` |
| Reformat / convert (aspect, platform, codec, loudness) | ffmpeg directly; face-aware crop for reframes; delivery specs below |
| Transcribe | `uv run tools/transcribe_local.py <video...> --language <es\|en…>` (offline, free, see below) |
| B-roll from the brand's own website / app | `uv run tools/site_capture.py <url> -o <edit>/downloads/site` (phone viewport + full-page PNG) |
| Start a brand kit from the brand's website (colours by area, fonts and their source, logo candidates, page text) | op `site`: `echo '{"op":"site","project":"<p>","args":{"url":"<url>"}}' \| uv run tools/run_job.py -` → `footage/<p>/site/` (`capture.json`, `viewport.png`, validated `images/`, Google Fonts files in `fonts/`). Every request goes through a network guard. Facts only: choosing the kit stays with you and the user |
| Sound effects (license-free) | `uv run tools/sfx_synth.py` → `assets/sfx/synth/*.wav` + `attack.json` |
| **Video from scratch, no footage** (explainer, kinetic type, data story, promo, intro/outro) | **`motion-graphics` skill**: `new_project.py --type generated` → `edit/storyboard.json` → `tools/storyboard.py check / stills / render`. Any aspect (9:16, 16:9, 1:1, 4:5). Promos animate the mechanism with `NetworkScene` (hub, messages), `IsoOffice` (agents at work, replay) and close on `EndCard`; screenshots only as brief proof |
| **Narrated explainer** (story first: a voice tells it; headline builds with the voice; a metaphor-driven story plays in one continuous `WorldScene` world: objects roll, break and grow under a moving camera; UI cards only for lists of facts) | **`motion-graphics` skill**, "Narrated explainer": `new_project.py --type generated --explainer` → `storyboard.py voice` (local TTS + word times) → `check / sheet / stills / render` |
| **Brand characters that act** (the brand's own mascot stills, real motion, a camera move in every shot, cut to narration). **Paid, opt-in** | **`character-video` skill**: `new_project.py --type generated --characters` → narration → `shotcut.py --plan` → `gen/keyframes.py` → `gen/animate.py --dur fit` → `shotcut.py` → `build.py`. Reuse `brands/<slug>/library/` clips first (`gen/library.py list`) |
| Run one step without a person typing (queue worker, CI, a Linux box) | `uv run tools/run_job.py job.json` (JSON in → one JSON result out; fixed ops, paths confined to the project; see "Linux / Docker"). A video-use EDL cut runs headless as op `cut` (validated: preset grades only, no outside paths) |
| Voiceover for a script line (local, free) | `uv run tools/gen/voice.py "<line>" -o out.wav --lang <code>` (Kokoro-82M, Apache-2.0; `--list` for voices) |
| Motion craft (timing, easing, transitions, typography) for any graphics, including overlays on footage | **`motion-graphics` skill** (craft rules); Remotion API questions → `remotion-best-practices` |
| Animated captions, Remotion API details | **Remotion skills** (`remotion-best-practices` covers all of them) |
| Download reference or source clips | `yt-dlp` (only content the user has rights to) |
| Anything else (reframe, speed, grade, LUTs, concat, overlays) | `ffmpeg` directly (full build with libass + freetype) |

## Paid APIs: one opt-in exception

The workspace is free and local by default. The only paid path is character animation and cloud narration (`character-video` skill: fal.ai image models and image-to-video, ElevenLabs TTS). It runs only when the user has put the key in `vendor/video-use/.env` (`FAL_API_KEY` or `FAL_KEY`, `ELEVENLABS_API_KEY`; never committed, never printed). Guardrails, built into the tools: every run prints the request count and estimated cost first, stops before sending if the estimate is over `--budget` (default $2), and logs every request to `edit/gen_spend.jsonl`. Test one shot before a batch and reuse the brand library first. ElevenLabs' free plan has no commercial licence; say so at delivery. Don't add another paid service without an OpenSpec change.

## Transcription: local first

video-use expects ElevenLabs Scribe (`ELEVENLABS_API_KEY` in `vendor/video-use/.env`). **If no key is set, use `tools/transcribe_local.py` instead.** It writes the same JSON to `<edit>/transcripts/<stem>.json`, so `pack_transcripts.py` and `render.py` work unchanged. Pass `--language` when you know it; without it the language is detected from 30 s of speech first (recorded as `language_detected`) and that language's prompt is used, never another language's (an English prompt on Spanish audio makes it translate). Local transcription has no speaker labels and no `(laughs)` tags. When diarization matters (interviews, podcasts), recommend Scribe.

Whisper can skip whole stretches of speech without a word. The transcriber checks: speech (the same RMS envelope `refine_edges` uses) that no word covers for 1.5 s or more is transcribed again on its own, with no prompt, and merged (`source.patched` lists each patch); speech still without words goes in `untranscribed` and is printed as a WARN. Read those ranges before cutting around them. The prompt per backend and language is the one that measured best (`tools/transcribe_prompts.md`).

The backend is picked at runtime: `mlx-whisper` on Apple Silicon (default install), `faster-whisper` on CPU everywhere else (Linux/Docker: `uv sync --group asr`). Both use Whisper large-v3-turbo and write the same JSON; `source.engine` says which ran. `--backend mlx|faster-whisper` forces one.

Run video-use helpers from the repo root: `uv run vendor/video-use/helpers/<helper>.py ...`

`storyboard.py voice` reuses the same local Whisper to time each narration clip's words, then aligns them to the script, so the headline shows the script's exact words.

## Linux / Docker

The same tools run on Linux (CPU only) in one image, with the backends chosen at runtime: faster-whisper instead of mlx-whisper, Kokoro on PyTorch instead of mlx-audio, MediaPipe instead of Apple Vision for the person matte. On the Mac nothing changes.

- **Build:** `docker build -t video-engine .` (weights baked in, so a container starts offline; ~2 GB more). `--build-arg WITH_MODELS=0` builds without them; they download on first use. It builds for the host's arch (arm64 on an M-series Mac); use `--platform linux/amd64` for x86 servers.
- **Self-check:** `docker run --rm video-engine --self-check` loads every backend and reports Python, ffmpeg filters, Node, Remotion's browser, auto-editor, video-use and the three backends. It exits 1 if anything is missing.
- **Run a job:** `docker run --rm -i -v "$PWD/footage:/engine/footage" video-engine - < job.json`, where a job looks like `{"op": "transcribe", "project": "acme-launch", "args": {"source": "take1.mov", "language": "en"}}`. Ops: `inventory`, `transcribe`, `voice`, `matte`, `storyboard` (`cmd`: check/voice/sheet/stills/render), `conform`, `pack`, `frames`, `face`, `shortform` (`cmd`: check/stills/render, from `edit/short.json`), `cut` (`cmd`: check/render, from `edit/edl.json`), `site` (`url` → `site/`), `brand` (`cmd`: check; validates `<dir>/incoming/` into `fonts/` and `logos/`, default dir `brand`), `schema` (no project, no args: every overlay component's props schema, also baked into the image at `tools/motion/overlay_schema.json`), `shortform.build`. `transcribe` also returns `language_detected` (when no language was given), `patched` and `untranscribed`; `shortform stills` returns one `stills` entry per still (event stills carry `event` and `type`) and `warnings` (text that doesn't show, captions that can't clear a scene). A raw-footage short runs as `inventory → conform → transcribe → pack → face → frames → shortform check → stills → render`, e.g. `{"op": "shortform", "project": "acme-launch", "args": {"cmd": "render", "preview": true}}`. Arguments are listed in `uv run tools/run_job.py --help`. Only the result JSON goes to stdout; logs go to stderr.
- **Mounts, never baked in:** `footage/`, `brands/` (include `_template`), `assets/music/` and `exports/` at `/engine/<same path>`. The image holds no projects, brand kits or keys. Paid tools read keys from `-e FAL_API_KEY=… -e ELEVENLABS_API_KEY=…` at run time. The container runs as uid 1000, so on a Linux host the mounted dirs must be writable by that uid.
- **`shortform.build` runs the project's `build.py`:** that is Python code, so treat it as trusted input only. A hosted service must never let its users author `build.py`. Users' edits go through `shortform` (`short.json`) and `cut` (EDL) instead: both are validated data, never executed, with every path confined to the project.
- **Speed on CPU (Docker on an M-series Mac, arm64):** transcription about 4× real time (a 30 s clip in ~7 s), a voice line in 3–7 s including model load, a 3.7 s 1080x1920 matte window in ~8 s, a 10 s storyboard preview in ~10 s, a 10 s short preview with one behind-the-speaker event in ~17 s. `site` takes 4–7 s for a light page (the local test page 3.5 s on the Mac, 4.2 s in an emulated amd64 container; `example.com` 4.2 s and 6.6 s) and is capped at 30 s; `brand check` is under a second, plus about a second of browser start when there is an SVG. x86 servers vary; there is no GPU path yet.
- **Differences from the Mac:** voice and transcript timing are close but not bit-identical, and a clip made by one backend is re-synthesised by the other (`storyboard.py voice` again after switching machines). The MediaPipe matte is softer around loose hair. Unbranded projects name the Mac faces first (Georgia, Helvetica Neue, Menlo), then Noto Serif, Noto Sans and Noto Sans Mono, which the image ships and Linux renders use: Chromium there ignores fontconfig's substitutes, so a face with no listed fallback comes out in its default serif. Brand kits ship their own font files, so branded renders match.

## Workflow rules

0. **Project first.** Every request gets a `footage/<project>/` with `project.md` stating its brand, type, platforms and language (`tools/new_project.py`).
1. **Inventory first.** `ffprobe` every source (codec, fps, resolution, audio tracks, duration) before planning. (From-scratch projects: brief, story spine, then beat sheet. Storytelling leads; graphics and the stick figure serve it and are never the format itself.)
2. **Plan, then cut.** Propose the edit in plain English and wait for approval before rendering. This rule comes from video-use.
3. **Never touch originals.** Write to `footage/<project>/edit/`, and copy finals to `exports/`.
4. **Preview at 720p** (`render.py --preview`) and render full quality only after approval.
5. **Verify before presenting.** Pull frames at each cut (`ffmpeg -ss T -i out.mp4 -frames:v 1 f.png`, then Read the PNG). Measure loudness and report the numbers.
6. Keep `edit/project.md` up to date so later sessions can pick up where the last one stopped.

## Developing the workspace (OpenSpec)

Changes to the workspace itself (`tools/`, `tools/motion/`, `.claude/skills/`, `templates/`, this file) go through OpenSpec spec-driven development. Specs live in `openspec/specs/`, and repo-wide rules for proposals, designs and tasks live in `openspec/config.yaml`.

- New capability or behaviour change: `/opsx:explore` (optional) → `/opsx:propose "<idea>"` → **user approves** → `/opsx:apply` → `/opsx:verify` → `/opsx:archive`.
- Small fixes (a typo, a one-line bug) don't need a change. If one alters behaviour a spec describes, update that spec.
- Editing a project's video is **not** an OpenSpec change. That work is tracked in `footage/<project>/edit/project.md`.
- Work on a branch, never directly on `main`.

## Delivery specs

| Platform | Frame | Loudness | Encode |
|---|---|---|---|
| YouTube | 1920x1080 or 3840x2160, 16:9 | -14 LUFS, -1 dBTP | H.264 `-crf 18 -preset slow -pix_fmt yuv420p`, AAC 320k, `-movflags +faststart` |
| Shorts / Reels / TikTok | 1080x1920, 9:16, ≤ 60–90s | -14 LUFS | same; keep captions and text inside the center safe zone (avoid the top ~15% / 290 px where IG blurs its header, the bottom ~20% and the right ~15% UI) |
| LinkedIn / X feed | 1080x1080 or 1080x1350 | -14 LUFS | same |
| Master / archive | source res | -16 to -23 LUFS | ProRes 422 HQ (`-c:v prores_ks -profile:v 3`) |

Use `h264_videotoolbox` / `hevc_videotoolbox` for fast hardware previews. Use libx264/libx265 for finals because they give better quality per bit.

## Gotchas

- `ffmpeg` on PATH is Homebrew's **ffmpeg-full** (needed for the `subtitles`/`ass`/`drawtext` filters). If those filters go missing after a `brew upgrade`, run `brew unlink ffmpeg && brew link --force ffmpeg-full`.
- The first `transcribe_local.py` run downloads Whisper large-v3-turbo (about 1.6 GB, then cached).
- Local voice (`tools/gen/voice.py`, `storyboard.py voice`) needs the optional group: `uv sync --group gen` (~0.37 GB on first use, then offline). A plain `uv sync` removes it again; the phonemiser (`espeak-ng`) comes bundled, no Homebrew install.
- Vertical reframes of 16:9 talking heads: crop around the face (check a frame first) rather than center-cropping blindly.
- Only use music, fonts and footage that the user has rights to.
- iPhone exports can have a U+202F (narrow no-break space) before "am/pm" in the filename. Rename sources to plain ASCII before scripting.
- Whisper stamps a segment's first word early (inside the silence before it). Set cut in-points from measured RMS silence, not word starts.
- Stock footage: no free API is available right now (Pexels paused keys). Use the brand's own site/app captures and Remotion graphics instead, and never scrape stock sites.
