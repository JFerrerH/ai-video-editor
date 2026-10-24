"""Base take for a character video: shot clips cut to their narration lines → edit/base.mov + edit/timeline.json.

    uv run tools/shotcut.py footage/<p>/edit --plan      # timeline only (run after narration, before animate --dur fit)
    uv run tools/shotcut.py footage/<p>/edit             # render base.mov (1080x1920, 30 fps, H.264 CRF 14 + PCM)
    flags: --vo audio/vo  --suffix _k25 (clip variant)  --out base.mov  --music <file>|none  --music-db -20
           --end-card <png>|none  --end-dur 3

Each shot lasts its narration clip + 0.15 s lead + 0.25 s tail (at least 2.0 s), rounded to a frame;
shots are joined by hard cuts and the voice starts 0.15 s into its shot. Narration clips are
`<vo>/<shot id>.wav` from tools/gen/voice.py or tools/gen/voice_cloud.py (their sidecar duration is
used when present). Clips come from `edit/shots/<id><suffix>.mp4`, or from the brand library for
shots with `"library": "<id>"`. Optional music is looped under the voice with sidechain ducking and
faded out over the last 1.5 s; an optional end-card image follows after a 0.4 s crossfade.
Defaults for vo / music / end card can sit in shots.json under `cut`.

Captions, overlay cards, SFX and loudness come next, from tools/shortform.py with base.mov as the
single source (templates/character_build.py).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "gen"))
import shotlist  # noqa: E402
from sheets import duration  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LEAD, TAIL, MIN_SHOT, FADE, MUSIC_FADE = 0.15, 0.25, 2.0, 0.4, 1.5
FPS, W, H = 30, 1080, 1920


def frames(t: float, fps: int = FPS) -> float:
    return round(t * fps) / fps


def vo_duration(wav: Path) -> float:
    try:
        return float(json.loads(wav.with_suffix(".json").read_text())["duration"])
    except (OSError, ValueError, KeyError):
        return duration(wav)


def clip_for(sl: shotlist.ShotList, shot: dict, edit: Path, suffix: str) -> Path:
    return sl.library_clip(shot["library"]) if shotlist.is_library(shot) else edit / "shots" / f"{shot['id']}{suffix}.mp4"


def timeline(sl: shotlist.ShotList, edit: Path, vo_dir: Path, suffix: str = "", need_clips: bool = False) -> list[dict]:
    shotlist.check(sl, sl.shots, "line")
    missing = [s["id"] for s in sl.shots if not (vo_dir / f"{s['id']}.wav").exists()]
    if missing:
        raise SystemExit(f"no narration clip in {vo_dir} for: {', '.join(missing)} (run the voice step first)")
    tl, t, errs = [], 0.0, []
    for s in sl.shots:
        vo = vo_dir / f"{s['id']}.wav"
        d = frames(max(LEAD + vo_duration(vo) + TAIL, MIN_SHOT))
        clip = clip_for(sl, s, edit, suffix)
        have = duration(clip) if clip.exists() else None
        if need_clips and have is None:
            errs.append(f"shot {s['id']}: clip not found: {clip}")
        elif need_clips and have + 1e-3 < d:
            fix = "pick a longer library clip" if shotlist.is_library(s) else \
                f"regenerate it: tools/gen/animate.py {edit.relative_to(REPO) if edit.is_relative_to(REPO) else edit} " \
                f"{s['id']} --dur fit --redo"
            errs.append(f"shot {s['id']}: needs {d:.2f}s but its clip has {have:.2f}s; {fix}")
        tl.append({"id": s["id"], "start": round(t, 3), "dur": round(d, 3), "voice_start": round(t + LEAD, 3),
                   "vo": str(vo), "clip": str(clip), "clip_dur": None if have is None else round(have, 3),
                   "source": f"library:{s['library']}" if shotlist.is_library(s) else "shots", "line": s["line"]})
        t += d
    if errs:
        raise SystemExit("fix before cutting:\n  " + "\n  ".join(errs))
    return tl


def find(p: str | None, edit: Path) -> Path | None:
    if not p or p == "none":
        return None
    for base in (edit, REPO):
        if (base / p).exists():
            return (base / p).resolve()
    raise SystemExit(f"not found: {p} (looked in {edit} and {REPO})")


def render(tl: list[dict], out: Path, music: Path | None, music_db: float, end_card: Path | None,
           end_dur: float) -> float:
    shots_end = tl[-1]["start"] + tl[-1]["dur"]
    total = shots_end + (end_dur if end_card else 0.0)
    ins, fc, n = [], [], len(tl)
    fit = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,format=yuv420p"
    for i, x in enumerate(tl):
        ins += ["-i", x["clip"]]
        fc.append(f"[{i}:v]trim=0:{x['dur']:.4f},setpts=PTS-STARTPTS,fps={FPS},{fit}[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,settb=1/{FPS}[body]")
    k = n
    if end_card:
        ins += ["-loop", "1", "-t", f"{end_dur + FADE:.3f}", "-i", str(end_card)]
        fc.append(f"[{k}:v]fps={FPS},{fit},settb=1/{FPS}[ec]")
        fc.append(f"[body][ec]xfade=transition=fade:duration={FADE}:offset={shots_end - FADE:.3f}[vout]")
        k += 1
    else:
        fc.append("[body]null[vout]")
    for i, x in enumerate(tl):
        ins += ["-i", x["vo"]]
        ms = round(x["voice_start"] * 1000)
        fc.append(f"[{k + i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}|{ms},apad[a{i}]")
    k += n
    fc.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,atrim=0:{total:.3f}"
              + (",asplit[voice][key]" if music else "[aout]"))
    if music:
        ins += ["-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,atrim=0:{total:.3f},volume={music_db}dB,"
                  f"afade=t=out:st={max(0.0, total - MUSIC_FADE):.3f}:d={MUSIC_FADE}[mus]")
        fc.append("[mus][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[ducked]")
        fc.append("[voice][ducked]amix=inputs=2:normalize=0[aout]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[vout]",
                    "-map", "[aout]", "-r", str(FPS), "-c:v", "libx264", "-crf", "14", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", "48000", "-t", f"{total:.3f}", str(out)],
                   check=True)
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit", type=Path, help="the project's edit/ folder (holds shots.json)")
    ap.add_argument("--plan", action="store_true", help="write timeline.json only (no clips needed)")
    ap.add_argument("--vo", help="narration folder relative to edit/ (default: cut.vo or audio/vo)")
    ap.add_argument("--suffix", default="", help="clip variant: shots/<id><suffix>.mp4")
    ap.add_argument("--out", default="base.mov", help="output name in edit/")
    ap.add_argument("--music", help="music file (edit/- or repo-relative), or none (default: cut.music)")
    ap.add_argument("--music-db", type=float, help="music gain before ducking (default: cut.music_db or -20)")
    ap.add_argument("--end-card", help="end-card image, or none (default: cut.end_card)")
    ap.add_argument("--end-dur", type=float, help="end-card seconds (default: cut.end_dur or 3)")
    a = ap.parse_args()
    edit = a.edit.resolve()
    sl = shotlist.ShotList(edit / "shots.json")
    cut = sl.data.get("cut") or {}
    vo_dir = edit / (a.vo or cut.get("vo") or "audio/vo")
    tl = timeline(sl, edit, vo_dir, a.suffix, need_clips=not a.plan)
    (edit / "timeline.json").write_text(json.dumps(tl, indent=1, ensure_ascii=False) + "\n")
    shots_end = tl[-1]["start"] + tl[-1]["dur"]
    for x in tl:
        have = "" if x["clip_dur"] is None else f"  clip {x['clip_dur']:.2f}s"
        print(f"  {x['start']:6.2f}  {x['dur']:5.2f}  {x['id']:<20} {x['source']}{have}")
    print(f"timeline.json: {len(tl)} shots, {shots_end:.2f}s")
    if a.plan:
        return
    music = find(a.music if a.music is not None else cut.get("music"), edit)
    end_card = find(a.end_card if a.end_card is not None else cut.get("end_card"), edit)
    end_dur = a.end_dur if a.end_dur is not None else float(cut.get("end_dur", 3.0))
    music_db = a.music_db if a.music_db is not None else float(cut.get("music_db", -20))
    total = render(tl, edit / a.out, music, music_db, end_card, end_dur)
    print(f"{a.out}: {total:.2f}s ({W}x{H} {FPS} fps); shots end at {shots_end:.2f}s"
          + (f", end card {end_dur:g}s" if end_card else "") + (f", music {music.name}" if music else ""))


if __name__ == "__main__":
    main()
