# AI Video Editor workspace

Claude edits video here with CLI tools: ffmpeg, auto-editor, local Whisper, video-use, and Remotion. Claude never watches video. It reads transcripts, `ffprobe` data, waveforms and still frames, then cuts with ffmpeg.

This workspace serves any number of unrelated projects, clients and brands. Nothing here is tuned to one brand: per-brand taste lives in `brands/<slug>/`, per-project state in `footage/<project>/edit/project.md`.

## Layout

```
footage/<project>/        raw takes, never modified
footage/<project>/edit/   all working files for that project (video-use convention); project.md first
brands/<slug>/            one brand/client: brand.md (taste + rules), brand.json (colors, fonts, captions), fonts/, logos/, broll/
brands/_template/         copy this to add a brand
assets/                   shared, brand-neutral: sfx/ (synth), luts/, music/ (licensed), fonts/
templates/                starting points: project.md, shortform_build.py, storyboard.json, storyboard_explainer.json
exports/                  final deliverables: <project>_<platform>_<YYYYMMDD>.mp4
tools/                    our own helpers
vendor/video-use/         third-party skill (cloned by scripts/setup.sh, don't edit)
```

## Projects and brands

- **Start every new request with a project:** `uv run tools/new_project.py <name> --brand <slug|none> --type <type> --platforms <list> --language <code> [--shortform]`. `--type generated` (no footage) starts from a storyboard instead of raw takes. Name it `<brand-or-client>-<what>` in kebab-case ASCII. If a request continues earlier work, open that project's `edit/project.md` instead.
- **The brand comes from `project.md`, never from habit.** If it names a brand, read `brands/<slug>/brand.md` before planning and pass `brand="<slug>"` to the engine. If it says `none`, use neutral defaults and ask the user about style. Don't apply one brand's taste, examples or rejected ideas to another project. If you can't tell which brand a request belongs to, ask.
- **New brand:** copy `brands/_template/`, then fill in `brand.md` and `brand.json` from the user's site, deck or answers. Fonts go in its `fonts/`. This repo is public: every kit except `_template` is gitignored and lives only on the machine that has it. Never name a client, brand, person or private project in a tracked file (skills, tools, templates, docs); use neutral examples. A missing kit means asking the user, not falling back to another brand.
- Skills hold general technique and neutral defaults. Feedback that is only taste ("I don't like yellow") goes into that brand's `brand.md`. Feedback that is about craft ("never clip a word") goes into the skill or tool.

## Which tool for what

| Task | Tool |
|---|---|
| Edit raw footage by conversation (talking head, tutorial, interview, montage) | **`video-use` skill**: read `.claude/skills/video-use/SKILL.md` and follow its hard rules |
| Fast silence / dead-air removal | `auto-editor in.mp4 --margin 0.15s -o out.mp4 --no-open` |
| Rough cut to finish in an NLE | `auto-editor in.mp4 --export resolve` (or `premiere` / `final-cut-pro`) |
| **Vertical short (Reels/TikTok/Shorts) that should look professional / keep attention** | **`short-form-pro` skill**: read `.claude/skills/short-form-pro/SKILL.md` after video-use. Engine `tools/shortform.py`, overlays `tools/motion/` (overlays are 1080x1920 only for now) |
| Long-form (YouTube, course, webinar) | `video-use` for the cut; chapters from the transcript; Remotion for lower thirds/titles at 1920x1080 |
| Interview / podcast (multi-speaker) | `video-use`; recommend Scribe for diarization; ffmpeg `xstack`/crop for multicam layouts |
| Montage / music-driven (travel, event, product, wedding) | beat grid from `librosa` (`beat_track`) → cut list on beats → ffmpeg concat; no transcript needed |
| Captions / subtitles only | `transcribe_local.py` → SRT/ASS → burn with ffmpeg `subtitles`/`ass`, or deliver the sidecar file |
| Reformat / convert (aspect, platform, codec, loudness) | ffmpeg directly; face-aware crop for reframes; delivery specs below |
| Transcribe | `uv run tools/transcribe_local.py <video...> --language <es\|en…>` (offline, free, see below) |
| B-roll from the brand's own website / app | `uv run tools/site_capture.py <url> -o <edit>/downloads/site` (phone viewport + full-page PNG) |
| Sound effects (license-free) | `uv run tools/sfx_synth.py` → `assets/sfx/synth/*.wav` + `attack.json` |
| **Video from scratch, no footage** (explainer, kinetic type, data story, promo, intro/outro) | **`motion-graphics` skill**: `new_project.py --type generated` → `edit/storyboard.json` → `tools/storyboard.py check / stills / render`. Any aspect (9:16, 16:9, 1:1, 4:5) |
| **Narrated explainer** (a voice tells it; headline builds with the voice; stick figure + UI cards) | **`motion-graphics` skill**, "Narrated explainer": `new_project.py --type generated --explainer` → `storyboard.py voice` (local TTS + word times) → `check / sheet / stills / render` |
| Voiceover for a script line (local, free) | `uv run tools/gen/voice.py "<line>" -o out.wav --lang <code>` (Kokoro-82M, Apache-2.0; `--list` for voices) |
| Motion craft (timing, easing, transitions, typography) for any graphics, including overlays on footage | **`motion-graphics` skill** (craft rules); Remotion API questions → `remotion-best-practices` |
| Animated captions, Remotion API details | **Remotion skills** (`remotion-best-practices` covers all of them) |
| Download reference or source clips | `yt-dlp` (only content the user has rights to) |
| Anything else (reframe, speed, grade, LUTs, concat, overlays) | `ffmpeg` directly (full build with libass + freetype) |

## Transcription: local first

video-use expects ElevenLabs Scribe (`ELEVENLABS_API_KEY` in `vendor/video-use/.env`). **If no key is set, use `tools/transcribe_local.py` instead.** It writes the same JSON to `<edit>/transcripts/<stem>.json`, so `pack_transcripts.py` and `render.py` work unchanged. Always pass `--language`: without it Whisper can mis-detect, and an English prompt on non-English audio makes it translate instead of transcribe. Local transcription has no speaker labels and no `(laughs)` tags. When diarization matters (interviews, podcasts), recommend Scribe.

Run video-use helpers from the repo root: `uv run vendor/video-use/helpers/<helper>.py ...`

`storyboard.py voice` reuses the same local Whisper to time each narration clip's words, then aligns them to the script, so the headline shows the script's exact words.

## Workflow rules

0. **Project first.** Every request gets a `footage/<project>/` with `project.md` stating its brand, type, platforms and language (`tools/new_project.py`).
1. **Inventory first.** `ffprobe` every source (codec, fps, resolution, audio tracks, duration) before planning. (From-scratch projects: brief and beat sheet first.)
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
