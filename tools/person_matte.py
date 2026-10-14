"""Person matte video for a time window of a clip (macOS: Apple Vision person segmentation).

    uv run tools/person_matte.py in.mov --start 8.0 --dur 3.7 -o matte.mov

Writes a grey matte (white = person) at the clip's resolution and frame rate, starting at
frame 0 = `start`. Used by tools/shortform.py to put text BEHIND the speaker (events with
`behind: true`): text layer under the matted person, over the background.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

SWIFT = Path(__file__).resolve().parent / "person_matte.swift"


def make_matte(src: Path, start: float, dur: float, out: Path, fps: int = 30, soften: float = 1.2) -> Path:
    with tempfile.TemporaryDirectory() as td:
        frames, mattes = Path(td) / "f", Path(td) / "m"
        frames.mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
                        "-vf", f"fps={fps}", str(frames / "%05d.png")], check=True)
        subprocess.run(["swift", str(SWIFT), str(frames), str(mattes)], check=True, capture_output=True)
        # gblur softens Vision's mask edge (hair) a touch; ProRes 422 keeps the grey ramp clean
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(mattes / "%05d.png"),
                        "-vf", f"format=gray,gblur=sigma={soften}", "-c:v", "prores_ks", "-profile:v", "2",
                        "-pix_fmt", "yuv422p10le", str(out)], check=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    if not shutil.which("swift"):
        raise SystemExit("swift not found (needs macOS with Xcode command line tools)")
    print(make_matte(a.src, a.start, a.dur, a.out))


if __name__ == "__main__":
    main()
