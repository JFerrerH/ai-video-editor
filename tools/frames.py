"""Stills of a SOURCE at chosen times, plus an optional contact sheet, for an editor who can't watch video.

    uv run tools/frames.py footage/<project>/take1.mov --at 1 5 9.5 --sheet
        → footage/<project>/edit/frames/take1_0001.00.png … and take1_sheet.png

At most 24 times per call. Every image is at most 720 px on its long side; the sheet prints each frame's
source time under it. A time past the end fails (naming the duration) before anything is written.
(Frames of the finished short come from `tools/shortform.py stills` instead.)
"""

from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
from pathlib import Path

from short_spec import project_root
from shortform import probe_video

MAX_TIMES, MAX_SIDE, LABEL_H = 24, 720, 28


def _duration(src: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def _fit(w: int, h: int, side: int) -> tuple[int, int]:
    k = min(1.0, side / max(w, h))
    return max(2, round(w * k / 2) * 2), max(2, round(h * k / 2) * 2)


def frames(src: Path, times: list[float], out_dir: Path, sheet: bool = False) -> list[Path]:
    if not times or len(times) > MAX_TIMES:
        raise ValueError(f"give 1–{MAX_TIMES} times, got {len(times)}")
    dur = _duration(src)
    if bad := [t for t in times if not 0 <= t < dur]:
        raise ValueError(f"time(s) {bad} outside {src.name} (duration {dur:.2f} s)")
    info = probe_video(src)
    w, h = _fit(info["width"], info["height"], MAX_SIDE)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in times:
        p = out_dir / f"{src.stem}_{t:07.2f}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"scale={w}:{h}", str(p)], check=True)
        paths.append(p)
    if sheet:
        n = len(times)
        cols = min(n, 6 if h > w else 4)
        rows = math.ceil(n / cols)
        k = min(1.0, MAX_SIDE / cols / w, (MAX_SIDE / rows - LABEL_H) / h)  # cell fits the 720 px sheet
        cw, ch = max(2, int(w * k / 2) * 2), max(2, int(h * k / 2) * 2)
        with tempfile.TemporaryDirectory() as td:
            for i, (t, p) in enumerate(zip(times, paths)):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf",
                                f"scale={cw}:{ch},pad={cw}:{ch + LABEL_H}:0:0:white,"
                                f"drawtext=text='{t:.2f}s':x=(w-tw)/2:y={ch + 6}:fontsize=16:fontcolor=black",
                                str(Path(td) / f"c{i:02d}.png")], check=True)
            for i in range(n, rows * cols):  # blank cells keep the grid square
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=white:s={cw}x{ch + LABEL_H}",
                                "-frames:v", "1", str(Path(td) / f"c{i:02d}.png")], check=True)
            sp = out_dir / f"{src.stem}_sheet.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(Path(td) / "c%02d.png"),
                            "-vf", f"tile={cols}x{rows}", "-frames:v", "1", str(sp)], check=True)
        paths.append(sp)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("--at", type=float, nargs="+", required=True, help="source seconds")
    ap.add_argument("--sheet", action="store_true", help="also write one contact sheet")
    ap.add_argument("-o", "--out", type=Path, help="default: <project>/edit/frames")
    a = ap.parse_args()
    out = a.out or project_root(a.source) / "edit" / "frames"
    try:
        for p in frames(a.source, a.at, out, a.sheet):
            print(p)
    except ValueError as e:
        raise SystemExit(str(e)) from None


if __name__ == "__main__":
    main()
