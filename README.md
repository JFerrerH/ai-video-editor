# AI video editor

A workspace where you edit video by talking to [Claude Code](https://claude.com/claude-code). Claude never watches the footage. It reads transcripts, `ffprobe` data, waveforms and still frames, proposes an edit in plain English, and once you approve it, renders with ffmpeg and Remotion.

It serves any number of unrelated projects and brands: talking heads, vertical shorts, tutorials, interviews, podcasts, montages, captions-only jobs, and format conversions. It can also make videos **from scratch, with no footage**: motion graphics from a storyboard file, and narrated explainers where a local AI voice tells the story while the headline, a stick figure and UI cards move in time with the words. Everything runs locally and free; there are no paid APIs. Each brand's taste lives in its own folder, so one client's style never leaks into another's.

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
  | Optional: local voice (`gen` group: Kokoro-82M weights + voices, mlx-audio, misaki, spaCy model) | ~0.4 GB |
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

For narrated videos, install the optional local voice once:

```sh
uv sync --group gen
```

This adds Kokoro-82M text-to-speech (Apache-2.0) on MLX, about 0.4 GB on first use and then fully offline. The phonemiser it needs (`espeak-ng`) comes bundled; there's nothing to install with Homebrew. A plain `uv sync` removes the group again, so keep passing `--group gen` once you use it.

## How to use it

There are two ways in: [editing footage you shot](#editing-footage) or [making a video from scratch](#videos-from-scratch-no-footage).

### Editing footage

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

### Videos from scratch (no footage)

You don't write files or run commands; you talk to Claude. There are two kinds:

- **Motion graphics:** animated titles, kinetic type, stats, charts and lists, with music and sound effects. Good for promos, intros, data stories and chapter cards.
- **Narrated explainer:** a local AI voice tells a short story. The words build on screen as they're spoken, a stick figure reacts in each beat, and UI cards (a terminal typing, a counter ticking, a checklist getting stamped) show what's being said.

**Before the first narrated video:** run `uv sync --group gen` once (see [Setup](#setup)). Motion graphics need nothing extra.

#### Step 1: Ask for the video

Open the repo in Claude Code and describe it. The more of these you give, the fewer questions Claude asks:

| Tell Claude | Example |
|---|---|
| Topic, and the one thing the viewer should remember | "Small teams can launch in an afternoon if they skip the busywork" |
| Kind of video | "a narrated explainer" or "motion graphics, no voice" |
| Platform (this sets the shape and length) | Reels, TikTok or Shorts → vertical 9:16; YouTube → 16:9; LinkedIn → 4:5 |
| Length | "about 30 seconds" |
| Language | English or Spanish (also French, Italian, Portuguese, Hindi) |
| Brand | a kit in `brands/`, or "no brand" for the neutral look |
| Call to action | "follow for part 2", "link in bio" |
| Script (optional) | paste your own lines, or let Claude write them |

For example:

> *Make a 30-second narrated explainer for Reels, in English, no brand: why small teams should launch in an afternoon instead of planning for a week. End with "follow for the checklist". Write the script for me.*

Claude creates the project, `footage/<project>/`, where every file for this video lives.

#### Step 2: Approve the beat sheet (checkpoint 1)

Claude replies with a table, one row per beat of 2–4 seconds. Each row has:
- the line that's spoken (narration);
- what's on screen: the widget and the figure's pose;
- the word each animation lands on;
- for motion graphics, the scene type, duration and transition.

Change anything you like: wording, order, which beats exist, what's shown. Nothing has been rendered yet, so changes are free. **Claude doesn't continue until you say it's OK.**

#### Step 3: Check the stills and the voice (checkpoint 2)

Claude makes the voice clips for every line (narrated videos only), then renders one frame per beat into a contact sheet: `footage/<project>/edit/stills/contact.png`.

- **Look at the contact sheet:** layout, text size, colours, figure poses.
- **Listen to the clips** in `footage/<project>/edit/audio/narration/`. Claude can't hear audio, so this part is on you. If a voice doesn't suit you, ask Claude to list the others and try a few. Ask Claude to respell any word it mispronounces. To use your own voice on a line, record it and give Claude the file.

Editing a line only re-records that line.

#### Step 4: Watch the preview (checkpoint 3)

Claude renders a 720p preview, about 20 s for a 30 s video: `footage/<project>/edit/preview.mp4`. Before showing it to you, it checks frames at the cue words and measures the loudness. Give feedback in plain words, for example:
- "beat 3 is too fast"
- "make the counter go to 500"
- "use a dark background when it turns negative"
- "add a whoosh on the cut to beat 5"

Claude edits and re-renders. Repeat until you're happy.

#### Step 5: Final export

Say it's approved. Claude renders full quality and copies the file to `exports/<project>_<platform>_<YYYYMMDD>.mp4`. That's the file you upload.

Want the same video in another shape (e.g. 16:9 for YouTube)? Ask for it. The layout adapts, and Claude re-checks the stills.

**Coming back later:** everything is logged in `footage/<project>/edit/project.md`. Say "continue the `<project>` video" and Claude picks up from there.

<details>
<summary>Under the hood (if you want to run the steps yourself)</summary>

The whole video is one file, `footage/<project>/edit/storyboard.json`, holding scenes, narration, cues, transitions and audio. Templates are in `templates/storyboard.json` and `templates/storyboard_explainer.json`.

```sh
uv run tools/new_project.py acme-explainer --type generated --platforms reels --language en --explainer
uv run tools/storyboard.py footage/acme-explainer/edit check               # timeline, warnings, errors
uv run --group gen tools/storyboard.py footage/acme-explainer/edit voice   # voice clips + word times
uv run tools/storyboard.py footage/acme-explainer/edit sheet poses         # reference sheet (or: sheet widgets)
uv run tools/storyboard.py footage/acme-explainer/edit stills              # edit/stills/contact.png
uv run tools/storyboard.py footage/acme-explainer/edit render --preview    # edit/preview.mp4
uv run tools/storyboard.py footage/acme-explainer/edit render --export reels
```

Leave out `--explainer` for motion graphics. The storyboard format and the craft rules are in [.claude/skills/motion-graphics/SKILL.md](.claude/skills/motion-graphics/SKILL.md).

</details>

## Layout

```
footage/<project>/        raw takes (gitignored, never modified)
footage/<project>/edit/   working files + project.md (brand, type, platforms, language, session log)
brands/<slug>/            brand kit: brand.md (taste + rules), brand.json (colors, fonts, captions), fonts/, logos/, broll/
brands/_template/         copy to add a brand
assets/                   shared, brand-neutral: sfx/, luts/, music/, fonts/
templates/                project.md, shortform_build.py, storyboard.json, storyboard_explainer.json
exports/                  deliverables (gitignored)
tools/                    helpers (below)
openspec/                 specs for the workspace's own behaviour + archived changes
.claude/skills/           short-form-pro, motion-graphics, Remotion skills, OpenSpec, video-use (symlink to vendor/)
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
| `tools/new_project.py` | Scaffolds `footage/<name>/edit/project.md`, plus a short-form `build.py` (`--shortform`) or a storyboard (`--type generated`, `--explainer`) |
| `tools/transcribe_local.py` | Offline Whisper → Scribe-shaped word JSON for video-use (always pass `--language`) |
| `tools/shortform.py` | Short-form engine: cuts with silence-snapped edges, zooms, looks, Remotion overlay, captions, SFX mix, loudnorm |
| `tools/storyboard.py` | From-scratch engine: `check`, `voice`, `sheet`, `stills`, `render` a `storyboard.json` (any aspect) |
| `tools/narration.py` | Narration timing: script words, alignment to Whisper word times, headline phrases, `@word` cues |
| `tools/gen/voice.py` | Local text-to-speech (Kokoro-82M, Apache-2.0): a line → WAV + sidecar, cached (`--list` for voices) |
| `tools/brand.py` | Loads `brands/<slug>/brand.json` into the theme, fonts and caption style |
| `tools/motion/` | Remotion project: the transparent overlay layer for shorts, and the full-frame `Story` for videos from scratch (see its README) |
| `tools/sfx_synth.py` | Builds the license-free SFX library in `assets/sfx/synth/` |
| `tools/site_capture.py` | Phone-viewport and full-page screenshots of a site, for product B-roll |
| `tools/person_matte.py` | Person matte with Apple Vision, for text behind the speaker |

Delivery specs, workflow rules and gotchas are in [CLAUDE.md](CLAUDE.md). The short-form playbook is in [.claude/skills/short-form-pro/SKILL.md](.claude/skills/short-form-pro/SKILL.md), and the from-scratch playbook in [.claude/skills/motion-graphics/SKILL.md](.claude/skills/motion-graphics/SKILL.md).

## Developing the workspace

Changes to the workspace itself (tools, skills, templates, CLAUDE.md) go through [OpenSpec](https://github.com/Fission-AI/OpenSpec). Current behaviour is specified in `openspec/specs/` (project setup, storyboard video, explainer graphics, voice generation). A new feature goes `/opsx:propose` → review → `/opsx:apply` → `/opsx:verify` → `/opsx:archive`, on a branch. Repo-wide rules (local and free only, commercially licensed models, no client names in tracked files) are in `openspec/config.yaml`. Editing a client's video isn't a spec change; that lives in the project's `project.md`.

Checks before a commit:

```sh
uv run --with pytest pytest -q tools/tests   # narration timing
cd tools/motion && npx tsc --noEmit && npm run lint
```

## Rights

Only use footage, music, fonts and logos that you have rights to. The SFX are synthesized and license-free. The local voice model (Kokoro-82M) is Apache-2.0, so generated narration can be used in client work. Any new model added to the workspace has to allow commercial use. Remotion is free for teams of up to 3; larger companies need a [license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
