"""Person matte video for a time window of a clip (macOS: Apple Vision; elsewhere: MediaPipe).

    uv run tools/person_matte.py in.mov --start 8.0 --dur 3.7 -o matte.mov
    uv run tools/person_matte.py in.mov --start 8.0 --dur 3.7 -o matte.mov --backend mediapipe

Writes a grey matte (white = person) at the clip's resolution and frame rate, starting at
frame 0 = `start`. Used by tools/shortform.py to put text BEHIND the speaker (events with
`behind: true`): text layer under the matted person, over the background.

Backends (chosen at runtime; `--backend` forces one):
  - vision     macOS with `swift`: Apple Vision person segmentation (person_matte.swift)
  - mediapipe  anywhere else (Linux, Docker): MediaPipe selfie segmenter (Apache-2.0, a few MB, kept in
               $ENGINE_MODELS_DIR, default ~/.cache/ai-video-editor); `uv sync --group matte`
Both feed the same ffmpeg soften + ProRes encode, so the output contract is the same.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SWIFT = Path(__file__).resolve().parent / "person_matte.swift"
BACKENDS = ("vision", "mediapipe")
MODELS_DIR = Path(os.environ.get("ENGINE_MODELS_DIR", Path.home() / ".cache" / "ai-video-editor"))
SEGMENTER_URL = ("https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/"
                 "float16/1/selfie_segmenter.tflite")
SEGMENTER = MODELS_DIR / "mediapipe" / "selfie_segmenter.tflite"
SEG_W = 360  # frame width sent to the segmenter (its input is 256x256)
SMOOTH = 0.6  # weight of the current frame in the running mask average (MediaPipe flickers at edges)


def pick_backend(requested: str | None) -> str:
    """`vision` on macOS with swift, `mediapipe` everywhere else; `requested` overrides."""
    if requested in (None, "auto"):
        return "vision" if sys.platform == "darwin" and shutil.which("swift") else "mediapipe"
    if requested not in BACKENDS:
        sys.exit(f"unknown matte backend {requested!r}; use auto, {', '.join(BACKENDS)}")
    return requested


def backend_missing(backend: str) -> str | None:
    """None if `backend` can run here, else what to do about it."""
    if backend == "vision":
        if sys.platform != "darwin":
            return "Apple Vision needs macOS; use --backend mediapipe"
        return None if shutil.which("swift") else "swift not found (install the Xcode command line tools)"
    if importlib.util.find_spec("mediapipe") is None:
        return "not installed; run: uv sync --group matte"
    return None


def fetch_segmenter() -> Path:
    """The selfie segmenter model, downloaded once into MODELS_DIR."""
    if not SEGMENTER.exists():
        if os.environ.get("HF_HUB_OFFLINE") == "1":
            sys.exit(f"matte model missing at {SEGMENTER} and the container is offline; "
                     "rebuild with WITH_MODELS=1 or run `tools/run_job.py --prefetch`")
        SEGMENTER.parent.mkdir(parents=True, exist_ok=True)
        print(f"  downloading the MediaPipe selfie segmenter → {SEGMENTER}", flush=True)
        tmp = SEGMENTER.with_suffix(".part")
        urllib.request.urlretrieve(SEGMENTER_URL, tmp)
        tmp.replace(SEGMENTER)
    return SEGMENTER


def _mediapipe_masks(frames: Path, mattes: Path, fps: int) -> None:
    """Each frame PNG → 8-bit grey confidence mask PNG of the same size, smoothed over time."""
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import BaseOptions, vision
    from PIL import Image

    mattes.mkdir(exist_ok=True)
    opts = vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(fetch_segmenter())),
                                        running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True)
    avg = None
    with vision.ImageSegmenter.create_from_options(opts) as seg:
        for k, f in enumerate(sorted(frames.glob("*.png"))):
            im = Image.open(f).convert("RGB")
            # the model sees 256x256 anyway: segment a small copy and upscale the mask bicubically,
            # which gives smooth edges instead of the task's blocky full-size mask
            small = im.resize((SEG_W, max(1, round(im.height * SEG_W / im.width))), Image.BILINEAR)
            rgb = np.ascontiguousarray(np.asarray(small))
            res = seg.segment_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), round(k * 1000 / fps))
            mask = res.confidence_masks[0].numpy_view().astype(np.float32).reshape(rgb.shape[:2])
            avg = mask if avg is None else SMOOTH * mask + (1 - SMOOTH) * avg
            full = Image.fromarray(np.clip(avg, 0, 1).astype(np.float32), "F").resize(im.size, Image.BICUBIC)
            Image.fromarray((np.clip(np.asarray(full), 0, 1) * 255).round().astype(np.uint8), "L").save(mattes / f.name)


def make_matte(src: Path, start: float, dur: float, out: Path, fps: int = 30, soften: float = 1.2,
               backend: str | None = None) -> Path:
    backend = pick_backend(backend)
    if err := backend_missing(backend):
        sys.exit(f"matte backend {backend!r}: {err}")
    with tempfile.TemporaryDirectory() as td:
        frames, mattes = Path(td) / "f", Path(td) / "m"
        frames.mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
                        "-vf", f"fps={fps}", str(frames / "%05d.png")], check=True)
        if backend == "vision":
            subprocess.run(["swift", str(SWIFT), str(frames), str(mattes)], check=True, capture_output=True)
        else:
            _mediapipe_masks(frames, mattes, fps)
        # gblur softens the mask edge (hair) a touch; ProRes 422 keeps the grey ramp clean
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
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--backend", choices=["auto", *BACKENDS], default="auto",
                    help="auto: vision on macOS, mediapipe elsewhere")
    a = ap.parse_args()
    print(make_matte(a.src, a.start, a.dur, a.out, fps=a.fps, backend=a.backend))


if __name__ == "__main__":
    main()
