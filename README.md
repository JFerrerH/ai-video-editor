# AI video editor

A workspace where you edit video by talking to [Claude Code](https://claude.com/claude-code). Claude never watches the footage. It reads transcripts, `ffprobe` data, waveforms and still frames, proposes an edit in plain English, and once you approve it, renders with ffmpeg and Remotion.

It serves any number of unrelated projects and brands: talking heads, vertical shorts, tutorials, interviews, podcasts, montages, captions-only jobs, and format conversions. Each brand's taste lives in its own folder, so one client's style never leaks into another's.

## Requirements

### Machine

| | Minimum | Recommended |
|---|---|---|
| Computer | Mac with Apple Silicon (M1 or later) | M1 Pro / M2 or later |
| macOS | 13 Ventura | 14 Sonoma or later |
| RAM (unified memory) | 8 GB | 16 GB or more |
| Free disk | 15 GB | 50 GB or more, on an SSD |
| Network | Needed for setup and the first transcription | |

Why these numbers:

- **Apple Silicon is required.** Local transcription uses `mlx-whisper`, which only runs on Apple Silicon, and the person matte (`tools/person_matte.py`, text behind the speaker) uses Apple's Vision framework through `swift`. Intel Macs, Linux and Windows aren't supported as-is.
- **RAM.** Whisper large-v3-turbo needs about 3–4 GB while it runs. A Remotion overlay render opens several headless Chrome tabs (by default one per two CPU threads), each taking a few hundred MB. 8 GB works if you close other apps and expect slower renders; 16 GB is comfortable; 4K sources or long-form projects want 32 GB.
- **Disk.** The toolchain takes about 6 GB once installed:

  | Item | Size |
  |---|---|
  | Homebrew packages (ffmpeg-full and its ~100 libraries, yt-dlp, uv, auto-editor, Node) | ~1–2 GB |
  | Python env (`.venv`) | ~1.3 GB |
  | video-use env (`vendor/video-use/.venv`) | ~0.3 GB |
  | Whisper model (`~/.cache/huggingface`) | ~1.6 GB |
  | Remotion (`tools/motion/node_modules`, includes Chrome Headless Shell) | ~0.9 GB |
  | Xcode Command Line Tools | ~1–2 GB if not already installed |

  On top of that, each project needs room for its sources plus working files. Intermediates such as ProRes 4444 overlay layers and mattes are large: a 60 s vertical short typically uses 1–2 GB in `footage/<project>/`, and long-form or 4K projects can use tens of GB. Delete `footage/<project>/edit/` intermediates once the export is final.

### Software

Install these before running the setup script:

- [Homebrew](https://brew.sh)
- Xcode Command Line Tools: `xcode-select --install` (provides `git` and `swift`)
- Node.js 18 or later: `brew install node` (for Remotion)
- [Claude Code](https://claude.com/claude-code)
- Optional: Google Chrome. `tools/site_capture.py` uses it if present; otherwise run `uv run playwright install chromium` (~150 MB more).

The setup script installs everything else. Python 3.12 is provisioned by `uv`, so you don't need a system Python.

Optional: an ElevenLabs API key for Scribe transcription with speaker labels (see below).

## Setup

```sh
scripts/setup.sh
```

The script installs ffmpeg-full, yt-dlp, uv and auto-editor; clones the [video-use](https://github.com/browser-use/video-use) skill into `vendor/`; syncs the Python env; installs the Remotion skills; and synthesizes the license-free SFX library. Then run `cd tools/motion && npm i` once for the overlay renderer.

Transcription runs locally with Whisper (`tools/transcribe_local.py`; the model downloads once, about 1.6 GB). If you want speaker labels, put an ElevenLabs Scribe key in `vendor/video-use/.env`.

## How to use it

1. Open the repo in Claude Code and describe what you want, e.g. *"Cut these two takes into a 60 s Reel for acme"*.
2. Claude creates a project for the request:

   ```sh
   uv run tools/new_project.py acme-launch-teaser --brand acme --type short-form --platforms reels,tiktok --language en --shortform
   ```

   Put the raw takes in `footage/acme-launch-teaser/`. They are never modified.
3. Claude inventories the takes, transcribes them, proposes the cut, and waits for your OK.
4. It renders a 720p preview, checks frames at every cut and the loudness, and iterates with you.
5. The final render goes to `exports/<project>_<platform>_<YYYYMMDD>.mp4`.

Every decision is logged in `footage/<project>/edit/project.md`, so a later session can pick up where the last one stopped.

## Layout

```
footage/<project>/        raw takes (gitignored, never modified)
footage/<project>/edit/   working files + project.md (brand, type, platforms, language, session log)
brands/<slug>/            brand kit: brand.md (taste + rules), brand.json (colors, fonts, captions), fonts/, logos/, broll/
brands/_template/         copy to add a brand
assets/                   shared, brand-neutral: sfx/, luts/, music/, fonts/
templates/                project.md, shortform_build.py
exports/                  deliverables (gitignored)
tools/                    helpers (below)
.claude/skills/           short-form-pro, Remotion skills, video-use (symlink to vendor/)
```

## Brands

A project is either unbranded (neutral look) or names one brand in `brands/`. To add one:

```sh
cp -r brands/_template brands/acme
```

Then fill in `brand.md` (taste, hook rules, caption style, things the client rejected) and `brand.json` (colours, fonts, caption size and colour), and put the font files in `brands/acme/fonts/`. Short-form builds pick the kit up with `Project(brand="acme")`.

Brand kits are client data, so git ignores every folder in `brands/` except `_template/`. Kits stay on your machine; back them up separately (or `git add -f` one that's fine to publish).

## Tools

| Tool | What it does |
|---|---|
| `tools/new_project.py` | Scaffolds `footage/<name>/edit/project.md` (and optionally a short-form `build.py`) |
| `tools/transcribe_local.py` | Offline Whisper → Scribe-shaped word JSON for video-use (always pass `--language`) |
| `tools/shortform.py` | Short-form engine: cuts with silence-snapped edges, zooms, looks, Remotion overlay, captions, SFX mix, loudnorm |
| `tools/brand.py` | Loads `brands/<slug>/brand.json` into the theme, fonts and caption style |
| `tools/motion/` | Remotion project that renders the transparent overlay layer (see its README) |
| `tools/sfx_synth.py` | Builds the license-free SFX library in `assets/sfx/synth/` |
| `tools/site_capture.py` | Phone-viewport and full-page screenshots of a site, for product B-roll |

Delivery specs, workflow rules and gotchas are in [CLAUDE.md](CLAUDE.md). The short-form playbook is in [.claude/skills/short-form-pro/SKILL.md](.claude/skills/short-form-pro/SKILL.md).

## Rights

Only use footage, music, fonts and logos that you have rights to. The SFX are synthesized and license-free. Remotion is free for teams of up to 3; larger companies need a [license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
