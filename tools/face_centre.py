"""Suggest a take's face centre (source px) from the person matte, for shortform `face` and 9:16 conform crops.

    uv run tools/face_centre.py footage/<project>/take1.mov [more takes…]     # prints JSON per take

Samples 5 frames (10/30/50/70/90 % of the duration), runs the person matte on them (Apple Vision on macOS,
MediaPipe elsewhere), takes the top 30 % of the person's height as the head band and returns its centroid
x and middle y, the median over frames with a person. confidence = share of frames with a person, halved
when the head touches the top edge. A person in fewer than 3 of the 5 frames (a screen recording that shows a
photo, say) is not a speaker take → face null, confidence 0. Same file + backend → same answer.
Check the point on a still before trusting it (tools/frames.py).
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import tempfile
from pathlib import Path

from person_matte import make_matte, pick_backend
from shortform import probe_video

SAMPLES = (0.1, 0.3, 0.5, 0.7, 0.9)
WORK_W = 270  # matte analysed at this width (enough for a crop centre, fast)


def _duration(src: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def suggest(src: Path, backend: str | None = None) -> dict:
    import numpy as np

    info = probe_video(src)
    w, h = info["width"], info["height"]
    dur = _duration(src)
    if not w or not h or dur <= 0:
        raise ValueError(f"{src.name}: no video to analyse")
    wh = round(h * WORK_W / w / 2) * 2
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for k, f in enumerate(SAMPLES):  # one frame per sample, display orientation (autorotate)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * f:.3f}", "-i", str(src), "-frames:v", "1",
                            str(td / f"s{k}.png")], check=True)
        clip = td / "samples.mov"  # the matte works on a clip: 5 frames at 1 fps
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(td / "s%d.png"),
                        "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        str(clip)], check=True)
        matte = td / "matte.mov"
        make_matte(clip, 0, len(SAMPLES), matte, fps=1, backend=backend)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(matte), "-vf", f"scale={WORK_W}:{wh}",
                              "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, wh, WORK_W)[:len(SAMPLES)]
    points, cut_top = [], 0
    for m in frames:
        mask = m > 127
        if mask.mean() < 0.02:
            continue
        rows = np.flatnonzero(mask.sum(axis=1) >= max(2, 0.01 * WORK_W))
        top, bottom = int(rows[0]), int(rows[-1])
        band = mask[top:top + max(1, round(0.3 * (bottom - top + 1)))]
        xs = np.nonzero(band)[1]
        points.append((float(xs.mean()), top + band.shape[0] / 2))
        cut_top += top <= 1
    if len(points) < 3:
        return {"face": None, "confidence": 0.0, "backend": pick_backend(backend)}
    k = w / WORK_W
    x = statistics.median(p[0] for p in points) * k
    y = statistics.median(p[1] for p in points) * k
    conf = len(points) / len(SAMPLES) * (0.5 if cut_top > len(points) / 2 else 1.0)
    return {"face": [round(x), round(y)], "confidence": round(conf, 2), "backend": pick_backend(backend)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", type=Path, nargs="+")
    ap.add_argument("--backend", choices=["auto", "vision", "mediapipe"], default="auto")
    a = ap.parse_args()
    print(json.dumps({s.stem: suggest(s, a.backend) for s in a.sources}, indent=1))


if __name__ == "__main__":
    main()
