"""Prototype of the engine's missing low-moment look (docs/editing-references.md rule 1), applied after render:
black and white with contrast + muffled voice with a short echo on [start, end], then a freeze of the last frame.

    python3 post.py footage/<p>      # edit/preview.mp4 + edit/xp_post.json -> edit/preview_final.mp4
"""
import json
import subprocess
import sys
from pathlib import Path

proj = Path(sys.argv[1])
edit = proj / "edit"
post = json.loads((edit / "xp_post.json").read_text()) if (edit / "xp_post.json").exists() else {}
src, dst = edit / "preview.mp4", edit / "preview_final.mp4"
low = post.get("low")
if not low:
    subprocess.run(["cp", src, dst], check=True)
    sys.exit(0)
t0, t1, fr = low["start"], low["end"], low["freeze"]
fps = 30
graph = (
    f"[0:v]trim=0:{t0},setpts=PTS-STARTPTS[va];[0:a]atrim=0:{t0},asetpts=PTS-STARTPTS[aa];"
    f"[0:v]trim={t0}:{t1},setpts=PTS-STARTPTS,hue=s=0,eq=contrast=1.15:brightness=-0.02,fps={fps},"
    f"tpad=stop_mode=clone:stop_duration={fr}[vb];"
    f"[0:a]atrim={t0}:{t1},asetpts=PTS-STARTPTS,highpass=f=220,lowpass=f=2400,aecho=0.85:0.6:40|80:0.22|0.1,volume=1.6dB,"
    f"apad=pad_dur={fr},atrim=0:{t1 - t0 + fr:.3f}[ab];"
    f"[0:v]trim={t1},setpts=PTS-STARTPTS[vc];[0:a]atrim={t1},asetpts=PTS-STARTPTS[ac];"
    "[va][aa][vb][ab][vc][ac]concat=n=3:v=1:a=1[v][a]"
)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(dst)],
               check=True)
print(f"{proj.name}: low moment {t0:.2f}–{t1:.2f} s + {fr} s freeze -> {dst.name}")
