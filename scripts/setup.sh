#!/usr/bin/env bash
# Reproduce this workspace's toolchain on a fresh Mac (Apple Silicon).
set -euo pipefail
cd "$(dirname "$0")/.."

brew install ffmpeg yt-dlp uv auto-editor ffmpeg-full
# ffmpeg-full is keg-only; it adds libass/freetype (subtitles + drawtext filters).
brew unlink ffmpeg && brew link --force ffmpeg-full

if [ ! -d vendor/video-use ]; then
  git clone --depth 1 https://github.com/browser-use/video-use vendor/video-use
else
  git -C vendor/video-use pull --ff-only
fi
ln -sfn ../../vendor/video-use .claude/skills/video-use

uv sync --python 3.12
uv run tools/sfx_synth.py  # license-free SFX into assets/sfx/synth/ (ignored by git)
(cd vendor/video-use && uv sync --python 3.12)

npx --yes skills add remotion-dev/skills --agent claude-code --yes || true

ffmpeg -hide_banner -filters | grep -q " subtitles " && echo "ok: ffmpeg has subtitles filter"
echo "done"
