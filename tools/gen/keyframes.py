"""First frames for a character shot list: the cast's reference stills + the shared world → one still per shot.

    uv run --group cloud tools/gen/keyframes.py footage/<p>/edit                 # every `frame` shot without a keyframe
    uv run --group cloud tools/gen/keyframes.py footage/<p>/edit s02 s05 --n 2   # 2 candidates each → <id>_1/_2.png
    uv run --group cloud tools/gen/keyframes.py footage/<p>/edit s02 --redo      # replace an existing keyframe
    flags: --model nano-banana-edit  --budget 2  --dry-run (estimate only)

Reads `edit/shots.json`; writes `edit/keyframes/<id>.png` (or `<id>_<k>.png` with --n K) and a
labelled contact sheet `edit/verify/keyframes_sheet.png`. Pick a candidate by copying it to
`<id>.png`. Existing keyframes are kept unless --redo. A shot with `base` edits that approved
keyframe and sends only its newly listed characters as extra references, so characters already
approved in it stay as they are (several references in one request drift characters off-model).
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fal
    import sheets
    import shotlist
else:
    from . import fal, sheets, shotlist

# Craft rules, learnt in the first character pilot; world and cast text come from the shot list.
KEEP_REFS = ("Keep each character exactly as in its reference image (same design, colours, texture, proportions), "
             "but do NOT copy the reference backgrounds.")
FULL_FRAME = "The image fills the whole frame edge to edge: one single picture, no borders, no split image."
NO_TEXT = "No text, no letters, no logos."


def prompt_for(sl: shotlist.ShotList, shot: dict) -> str:
    """Never asks for empty "bands" for text: image models pad the frame with blurred bars. Place
    the characters ("in the lower half of the frame") in the `frame` text instead."""
    off = 1 if shot.get("base") else 0
    who = "; ".join(f"{n.upper()} = {sl.cast[n]['desc']} (reference image {k + 1 + off})"
                    for k, n in enumerate(shot["cast"]))
    if off:
        return (f"Edit image 1 (an approved film still): keep its setting, lighting, camera and the characters "
                f"already in it exactly as they are. Characters to add: {who}. {KEEP_REFS} "
                f"Change: {shot['frame']} {FULL_FRAME} {NO_TEXT}")
    return (f"Create one new film still. Characters: {who}. {KEEP_REFS} "
            f"Scene: {shot['frame']} Setting: {sl.world} {FULL_FRAME} {NO_TEXT}")


def images_for(sl: shotlist.ShotList, shot: dict) -> list[Path]:
    """Base keyframe first (if any), then the listed characters' stills in cast order."""
    base = [sl.resolve(shot["base"])] if shot.get("base") else []
    return base + [sl.resolve(sl.cast[n]["ref"]) for n in shot["cast"]]


def outputs(out_dir: Path, sid: str, n: int) -> list[Path]:
    return [out_dir / f"{sid}.png"] if n == 1 else [out_dir / f"{sid}_{k}.png" for k in range(1, n + 1)]


def run(sl: shotlist.ShotList, ids: list[str] | None, out_dir: Path, log: Path, sheet: Path, n: int = 1,
        redo: bool = False, budget: float = fal.DEFAULT_BUDGET, model_name: str = fal.DEFAULT_IMAGE,
        dry_run: bool = False, tool: str = "keyframes") -> list[Path]:
    m = fal.model(model_name, "image")
    shots = [s for s in sl.by_id(ids) if not shotlist.is_library(s) and (ids or s.get("frame"))]
    shotlist.check(sl, shots, "frame")
    todo = [s for s in shots if redo or not all(p.exists() for p in outputs(out_dir, s["id"], n))]
    for s in shots:
        if s not in todo:
            print(f"  kept: {', '.join(p.name for p in outputs(out_dir, s['id'], n))}")
    reqs = [fal.Request(tool, m, s["id"], outputs(out_dir, s["id"], n)[0], n=n) for s in todo]
    fal.plan(reqs, budget)
    if not reqs or dry_run:
        return []
    fc = fal.client()
    up = fal.Uploads(fc)
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(pair: tuple[dict, fal.Request]) -> list[Path]:
        s, r = pair
        t0 = time.time()
        res = fal.subscribe(fc, m, {"prompt": prompt_for(sl, s), m.image_param: [up(p) for p in images_for(sl, s)],
                                    "aspect_ratio": sl.aspect, "num_images": n, **m.extra})
        outs = [fal.download(img["url"], p) for img, p in zip(res["images"], outputs(out_dir, s["id"], n))]
        fal.log_spend(log, r, time.time() - t0, outs)
        print(f"  keyframe: {', '.join(p.name for p in outs)} ({time.time() - t0:.0f}s)", flush=True)
        return outs

    with ThreadPoolExecutor(4) as ex:
        written = [p for outs in ex.map(one, zip(todo, reqs)) for p in outs]
    sheets.contact_sheet(written, sheet)
    print(f"  sheet: {sheet}")
    fal.print_total(log)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit", type=Path, help="the project's edit/ folder (holds shots.json)")
    ap.add_argument("ids", nargs="*", help="only these shots (default: every shot with a `frame`)")
    ap.add_argument("--n", type=int, default=1, help="candidates per shot")
    ap.add_argument("--redo", action="store_true", help="replace existing keyframes")
    ap.add_argument("--model", default=fal.DEFAULT_IMAGE)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and estimate, send nothing")
    fal.add_budget_arg(ap)
    a = ap.parse_args()
    edit = a.edit.resolve()
    run(shotlist.ShotList(edit / "shots.json"), a.ids, edit / "keyframes", edit / fal.SPEND_LOG,
        edit / "verify" / "keyframes_sheet.png", a.n, a.redo, a.budget, a.model, a.dry_run)


if __name__ == "__main__":
    main()
