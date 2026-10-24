"""<project> → character video (brand: <slug or none>). Data only; the engine is tools/shortform.py.

The take is edit/base.mov from tools/shotcut.py (animated shots cut to the narration, music, end
card), so there is one locked segment over the whole of it. This file adds captions, overlay cards
and SFX; loudness comes from the engine. Times are relative to shot starts read from timeline.json,
so they survive a re-cut. Copy to footage/<project>/edit/build.py (or run new_project.py --characters).

    uv run tools/shotcut.py footage/<project>/edit                                   # → base.mov + timeline.json
    uv run tools/transcribe_local.py footage/<project>/edit/base.mov --edit-dir footage/<project>/edit --language <code>
                                                                                     # → transcripts/base.json
    uv run footage/<project>/edit/build.py --preview                                 # 720p → edit/preview.mp4
    uv run footage/<project>/edit/build.py                                           # 1080p → edit/final.mp4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EDIT = Path(__file__).resolve().parent
REPO = EDIT.parents[2]
sys.path.insert(0, str(REPO / "tools"))
from shortform import Project, Seg  # noqa: E402

BASE = EDIT / "base.mov"
TL = {x["id"]: x for x in json.loads((EDIT / "timeline.json").read_text())}
TOTAL = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(BASE)], capture_output=True, text=True, check=True).stdout)


def T0(sid: str) -> float:
    """Start of a shot in base.mov (= where to look for its words)."""
    return TL[sid]["start"]


def T1(sid: str) -> float:
    return TL[sid]["start"] + TL[sid]["dur"]


def word_at(text: str, sid: str) -> float:
    """Transcript start of the first word containing `text` in shot `sid` (key for caption_word_fixes)."""
    words = [w for w in json.loads((EDIT / "transcripts" / "base.json").read_text())["words"] if w["type"] == "word"]
    return next(w["start"] for w in words if w["start"] >= T0(sid) - 0.05 and text.lower() in w["text"].lower())


SEGMENTS = [Seg("base", 0.0, TOTAL, ("static", 1.00), note="whole video", lock_in=True, lock_out=True)]

p = Project(
    edit_dir=EDIT,
    sources={"base": BASE},
    face={"base": (540, 900)},
    segments=SEGMENTS,
    brand=None,  # "<slug>" → brands/<slug>/brand.json (theme, fonts, caption style); None → neutral
    grade="null",  # the generator's look is the grade; don't touch it
    caption_fixes={},  # Whisper mishearings everywhere: {"heard": "said"}
    caption_word_fixes={},  # one word: {("base", word_at("heard", "s02_meet")): "said"}
    emphasis=[],  # key phrases: ("base", "phrase words", T0("s01_hook"))
)
W = lambda text, after=0.0, end=False: p.word("base", text, after, end)  # noqa: E731  output time of a word


def ev(type_: str, start: float, end: float, **props) -> dict:
    return {"type": type_, "start": round(start, 3), "duration": round(end - start, 3), "props": props}


events, sfx = [], []

# hook title on frame 0: complements the first line, doesn't repeat it
first = next(iter(TL))
events.append(ev("HookTitle", 0.0, min(3.0, T1(first)), lines=[{"text": "Hook line one"}, {"text": "hook line two"}]))
sfx.append(("pop", 0.05, -16))

p.events, p.sfx = events, sfx

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-overlay", action="store_true")
    a = ap.parse_args()
    p.build(a.preview, a.skip_extract, a.skip_overlay)
