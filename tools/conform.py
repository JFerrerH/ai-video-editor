"""Conform raw uploads into edit-ready files: edit/conformed/<stem>.mov + edit/conformed/conform.json.

    uv run tools/conform.py footage/<project>                        # every video directly in the project, 9:16
    uv run tools/conform.py footage/<project> --frame source         # keep orientation (plain cuts, long-form)
    uv run tools/conform.py footage/<project> --sources take1.mov --face take1=900,540

Output: H.264 (CRF 12) + PCM 48 kHz stereo in .mov, SDR BT.709 (HLG/PQ tone-mapped), rotation applied,
constant 24/25/30 fps (other rates → 30). PCM keeps the audio sample-exact against the original, so a
transcript of the original still fits the conformed file (same start, same duration ±1 frame).
  --frame 9:16    1080x1920. Wider sources are cropped to 9:16 around the face centre (given with --face,
                  else suggested by tools/face_centre.py), taller ones around it vertically, then scaled.
  --frame source  orientation kept, short side scaled to 1080.
A source already edit-ready for the frame is recorded as `as_is` and not copied. Originals are never touched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from shortform import HDR_TRANSFERS, probe_video

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mxf"}
RATES = (24, 25, 30)
# HDR → SDR: video-use render.py's Hable chain with the input transfer/primaries/matrix stated from the probe
# (ffmpeg builds disagree on whether container or frame tags win, which shifted colours between Mac and Linux).
# npl=140 and saturation 0.9 are calibrated on a real phone HLG take against the phone's own SDR export:
# at render.py's npl=100 / full saturation the result came out ~12 % brighter and ~17 % more saturated.
ZSCALE_PRIMARIES = {"bt2020": "2020", "bt709": "709", "smpte432": "smpte432"}
ZSCALE_MATRIX = {"bt2020nc": "2020_ncl", "bt2020c": "2020_cl", "bt709": "709"}


def tonemap(info: dict) -> str:
    pin = ZSCALE_PRIMARIES.get(info.get("primaries"), "2020")
    min_ = ZSCALE_MATRIX.get(info.get("matrix"), "2020_ncl")
    return (f"zscale=tin={info['transfer']}:pin={pin}:min={min_}:t=linear:npl=140,format=gbrpf32le,"
            "zscale=p=709,tonemap=tonemap=hable:desat=0,zscale=t=709:m=709:r=tv,format=yuv420p,eq=saturation=0.9")


def _rate(s: str | None) -> float:
    if not s or s in ("0/0", "N/A"):
        return 0.0
    a, _, b = s.partition("/")
    return float(a) / float(b or 1)


def _audio(src: Path) -> dict | None:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=codec_name,sample_rate,channels", "-of", "json", str(src)], capture_output=True, text=True)
    st = json.loads(r.stdout or "{}").get("streams") or []
    return st[0] if st else None


def _duration(src: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def target_fps(info: dict) -> int:
    """24/25/30 when the source runs at one of them (avg within 0.5 %, phones drift), else 30."""
    avg = _rate(info.get("avg_frame_rate")) or _rate(info.get("r_frame_rate"))
    return next((r for r in RATES if abs(avg - r) <= 0.005 * r), 30)


def crop_box(w: int, h: int, face: tuple[float, float] | None) -> tuple[int, int, int, int] | None:
    """9:16 window (x, y, cw, ch) inside a w x h frame, centred on the face, or None when already 9:16."""
    if abs(w / h - 9 / 16) <= 0.01 * 9 / 16:
        return None
    fx, fy = face or (w / 2, h / 2)
    if w / h > 9 / 16:  # wider: full height, crop the width around the face
        cw, ch = round(h * 9 / 16 / 2) * 2, h
        return max(0, min(w - cw, round(fx - cw / 2))), 0, cw, ch
    cw, ch = w, round(w * 16 / 9 / 2) * 2  # taller (screen recordings): crop the height
    return 0, max(0, min(h - ch, round(fy - ch / 2))), cw, ch


def is_ready(info: dict, audio: dict | None, frame: str) -> bool:
    size_ok = (info["width"], info["height"]) == (1080, 1920) if frame == "9:16" else \
        min(info["width"], info["height"]) == 1080
    return (size_ok and info["transfer"] not in HDR_TRANSFERS
            and _rate(info.get("r_frame_rate")) in RATES and target_fps(info) == _rate(info.get("r_frame_rate"))
            and audio is not None and audio.get("sample_rate") == "48000" and audio.get("channels") == 2)


def conform_one(src: Path, out: Path, frame: str = "9:16", face: tuple[float, float] | None = None) -> dict:
    info, audio = probe_video(src), _audio(src)
    w, h = info["width"], info["height"]
    if not w or not h:
        raise ValueError(f"{src.name} has no video stream")
    rec = {"original": src.name, "probe": {**info, "audio": audio}, "frame": frame, "as_is": False,
           "fps": target_fps(info), "crop": None, "face": None}
    if is_ready(info, audio, frame):
        return {**rec, "as_is": True, "output": None}
    vf = [tonemap(info)] if info["transfer"] in HDR_TRANSFERS else []
    vf.append(f"fps={rec['fps']}")
    if frame == "9:16":
        if w / h > 9 / 16 * 1.01 and face is None:
            from face_centre import suggest

            face = tuple(suggest(src)["face"] or (w / 2, h / 2))
        box = crop_box(w, h, face)
        if box:
            rec["crop"], rec["face"] = list(box), [round(face[0]), round(face[1])] if face else None
            vf.append("crop={2}:{3}:{0}:{1}".format(*box))
        vf.append("scale=1080:1920:flags=lanczos")
    else:
        vf.append("scale=-2:1080:flags=lanczos" if w >= h else "scale=1080:-2:flags=lanczos")
    vf += ["setsar=1", "format=yuv420p", "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    amap = "0:a:0"
    if audio is None:  # the engine always mixes dialogue: give silent takes a silent track
        cmd += ["-f", "lavfi", "-t", f"{_duration(src):.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = "1:a"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-map", "0:v:0", "-map", amap, "-vf", ",".join(vf),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",  # VUI too (filters can drop tags)
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-map_metadata", "-1", str(out)]
    subprocess.run(cmd, check=True)
    return {**rec, "output": out.name}


def conform(root: Path, sources: list[Path] | None = None, frame: str = "9:16",
            faces: dict[str, tuple[float, float]] | None = None) -> dict:
    """Conform the given sources (default: every video directly in `root`); merges into conform.json."""
    root = root.resolve()
    sources = [s.resolve() for s in sources] if sources else \
        sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT)
    out_dir = root / "edit" / "conformed"
    manifest_p = out_dir / "conform.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {"takes": {}}
    for src in sources:
        print(f"  conform {src.name} ({frame})", flush=True)
        rec = conform_one(src, out_dir / f"{src.stem}.mov", frame, (faces or {}).get(src.stem))
        rec["original"] = str(src.relative_to(root))
        rec["output"] = str((out_dir / rec["output"]).relative_to(root)) if rec["output"] else rec["original"]
        manifest["takes"][src.stem] = rec
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_p.write_text(json.dumps(manifest, indent=1))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="footage/<project>")
    ap.add_argument("--sources", nargs="+", help="files in the project (default: every video directly in it)")
    ap.add_argument("--frame", choices=("9:16", "source"), default="9:16")
    ap.add_argument("--face", nargs="+", default=[], metavar="TAKE=X,Y", help="face centre per take, source px")
    a = ap.parse_args()
    faces = {k: tuple(float(v) for v in xy.split(",")) for k, _, xy in (f.partition("=") for f in a.face)}
    m = conform(a.project, [a.project / s for s in a.sources] if a.sources else None, a.frame, faces)
    for take, r in m["takes"].items():
        print(f"{take}: {'as is' if r['as_is'] else r['output']}  crop={r['crop']}  fps={r['fps']}")


if __name__ == "__main__":
    main()
