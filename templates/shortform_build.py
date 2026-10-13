"""<project> → vertical short (brand: <slug or none>). Data only; the engine is tools/shortform.py.

Copy to footage/<project>/edit/build.py (or run tools/new_project.py --shortform), then fill
SEGMENTS, events and sfx. Past projects' build.py files on this machine make good worked examples.

    uv run footage/<project>/edit/build.py --preview            # 720p → edit/preview.mp4
    uv run footage/<project>/edit/build.py                      # 1080p → edit/final.mp4
    flags: --skip-extract (reuse segments)  --skip-overlay (reuse Remotion render)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EDIT = Path(__file__).resolve().parent
REPO = EDIT.parents[2]
sys.path.insert(0, str(REPO / "tools"))
from shortform import Project, Seg  # noqa: E402

SEGMENTS = [
    # Seg(take, in, out, zoom, look=None|"bw", freeze_after=0.0, note="spoken line")
    # zooms: ("static", s) ("push", a, b) ("punch", base, peak, src_t) ("outpunch", a, b, peak, src_t)
    Seg("take1", 0.00, 5.00, ("static", 1.00), note="first line"),
]

p = Project(
    edit_dir=EDIT,
    sources={"take1": EDIT.parent / "take1.mov"},
    face={"take1": (540, 900)},  # face centre per take, source px (check a frame first)
    segments=SEGMENTS,
    brand=None,  # "<slug>" → brands/<slug>/brand.json (theme, fonts, caption style); None → neutral
    caption_fixes={},  # Whisper mishearings: {"heard": "said"}
    emphasis=[],  # key phrases: (take, "phrase", after_source_seconds)
    public_files={},  # extra Remotion assets: {"site/img-00.png": EDIT / "downloads/site/img-00.png"}
)
EDGE_REPORT = p.refine_edges()  # widen every cut to measured silence — never clip a word
offs = p.offsets()
W1 = lambda text, after=0.0, end=False: p.word("take1", text, after, end)  # noqa: E731
seg_end = lambda i: offs[i + 1]  # noqa: E731


def ev(type_: str, start: float, end: float, **props) -> dict:
    return {"type": type_, "start": round(start, 3), "duration": round(end - start, 3), "props": props}


def rel(t: float, start: float) -> float:
    return round(t - start, 3)


events, sfx = [], []

# 1 hook title (first frame)
events.append(ev("HookTitle", 0.0, 3.0, lines=[{"text": "Hook line one"}, {"text": "hook line two"}]))
sfx.append(("click", 0.06, -15))

p.events, p.sfx = events, sfx

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-overlay", action="store_true")
    a = ap.parse_args()
    print("\n".join(EDGE_REPORT))
    p.build(a.preview, a.skip_extract, a.skip_overlay)
