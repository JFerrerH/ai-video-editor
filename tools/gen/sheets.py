"""Verification images: a labelled contact sheet of stills, and a frame strip of a clip."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def _font(size: int):
    from PIL import ImageFont

    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def contact_sheet(images: list[Path], out: Path, labels: list[str] | None = None, thumb_h: int = 640,
                  cols: int = 4) -> Path:
    """Thumbnails in a grid, each labelled underneath (default: the file name)."""
    from PIL import Image, ImageDraw

    labels = labels or [p.name for p in images]
    thumbs = []
    for p in images:
        im = Image.open(p).convert("RGB")
        thumbs.append(im.resize((round(im.width * thumb_h / im.height), thumb_h)))
    cols = max(1, min(cols, len(thumbs)))
    rows = -(-len(thumbs) // cols)
    cw, lh, pad = max(t.width for t in thumbs), 44, 12
    sheet = Image.new("RGB", (cols * (cw + pad) + pad, rows * (thumb_h + lh + pad) + pad), "#1b1b1b")
    d, font = ImageDraw.Draw(sheet), _font(28)
    for k, (t, label) in enumerate(zip(thumbs, labels)):
        x, y = pad + (k % cols) * (cw + pad), pad + (k // cols) * (thumb_h + lh + pad)
        sheet.paste(t, (x, y))
        d.text((x + 4, y + thumb_h + 8), label, fill="#f0f0f0", font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def duration(path: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(path)], capture_output=True, text=True, check=True).stdout)


def size(path: Path) -> tuple[int, int]:
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip().split(",")
    return int(w), int(h)


def frame_strip(video: Path, out: Path, n: int = 6, thumb_h: int = 480) -> Path:
    """`n` frames spread over the clip (first and last included), labelled with their time."""
    dur = duration(video)
    times = [round(min(dur - 0.25, dur * k / (n - 1)), 2) for k in range(n)]
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for k, t in enumerate(times):
            f = Path(tmp) / f"{k}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", str(video),
                            "-frames:v", "1", str(f)], check=True)
            if not f.exists():  # a seek past the last decodable frame writes nothing
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.5", "-i", str(video), "-update", "1",
                                str(f)], check=True)
            frames.append(f)
        return contact_sheet(frames, out, [f"{video.stem} {t:.1f}s" for t in times], thumb_h, cols=n)
