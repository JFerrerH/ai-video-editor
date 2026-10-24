"""Image-to-video per shot: keyframe (or `src` still) + motion + camera move → edit/shots/<id><suffix>.mp4.

    uv run --group cloud tools/gen/animate.py footage/<p>/edit --dur fit             # every new shot, exact length
    uv run --group cloud tools/gen/animate.py footage/<p>/edit s03 --model kling-2.5-turbo --suffix _k25   # A/B one shot
    flags: --model (see `tools/gen/fal.py models`)  --dur 5|10|<s>|fit  --suffix ""  --redo  --budget 2
           --jobs 6  --dry-run (estimate only)

`--dur fit` reads `edit/timeline.json` (from `tools/shotcut.py --plan`, after the narration exists)
and asks for each shot's length there + 0.2 s handle. Any-duration models get exactly that;
fixed-duration models get the smallest allowed length that covers it; a shot longer than the model's
maximum stops the run before anything is sent. Shots that point at a brand library clip
(`"library": "<id>"`) and existing clips are skipped (--redo replaces). Each new clip gets a frame
strip in `edit/verify/<id><suffix>_strip.png`: read it before using the clip.
"""

from __future__ import annotations

import argparse
import json
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

HANDLE = 0.2  # s generated past the cut, so the shot never runs out of picture
TAIL = (" Smooth, continuous cinematic camera movement throughout the whole shot; the camera never stays still."
        " Expressive, natural character animation. Characters keep exactly the same design, colours and"
        " proportions as in the first frame. No text.")


def prompt_for(sl: shotlist.ShotList, shot: dict) -> str:
    style = f" {sl.style.strip().rstrip('.')}." if sl.style.strip() else ""
    return f"{shot['motion'].strip()} {shot['camera'].strip()}{TAIL}{style}"


def start_image(sl: shotlist.ShotList, shot: dict, keyframes: Path) -> Path:
    return sl.resolve(shot["src"]) if shot.get("src") else keyframes / f"{shot['id']}.png"


def read_timeline(path: Path) -> dict[str, float]:
    try:
        return {x["id"]: float(x["dur"]) for x in json.loads(path.read_text())}
    except OSError:
        raise SystemExit(f"--dur fit needs {path}; run `tools/shotcut.py <edit> --plan` after the narration") from None


def durations(m: fal.Model, shots: list[dict], dur: str, needs: dict[str, float], handle: float) -> tuple[dict, list]:
    """{shot id: seconds to request} and the errors that stop the run."""
    out, errs = {}, []
    for s in shots:
        if dur == "fit":
            if s["id"] not in needs:
                errs.append(f"shot {s['id']}: not in the timeline; rerun `shotcut.py --plan`")
                continue
            need = needs[s["id"]] + handle
        else:
            need = float(dur)
        try:
            out[s["id"]] = m.fit(need)
        except ValueError as e:
            errs.append(f"shot {s['id']}: {e}")
    return out, errs


def run(sl: shotlist.ShotList, ids: list[str] | None, keyframes: Path, out_dir: Path, log: Path, verify: Path,
        model_name: str = fal.DEFAULT_VIDEO, dur: str = "fit", needs: dict[str, float] | None = None,
        handle: float = HANDLE, suffix: str = "", redo: bool = False, budget: float = fal.DEFAULT_BUDGET,
        jobs: int = 6, dry_run: bool = False, tool: str = "animate") -> list[Path]:
    m = fal.model(model_name, "video")
    picked = sl.by_id(ids)
    for s in picked:
        if shotlist.is_library(s):
            print(f"  library: {s['id']} → {s['library']} (no generation)")
    shots = [s for s in picked if not shotlist.is_library(s) and (ids or s.get("motion"))]
    shotlist.check(sl, shots, "motion")
    errs = [f"shot {s['id']}: start image not found: {start_image(sl, s, keyframes)}"
            for s in shots if not start_image(sl, s, keyframes).exists()]
    secs, derrs = durations(m, shots, dur, needs or {}, handle)
    if errs + derrs:
        raise SystemExit("fix before anything is sent:\n  " + "\n  ".join(errs + derrs))
    out = lambda s: out_dir / f"{s['id']}{suffix}.mp4"  # noqa: E731
    todo = [s for s in shots if redo or not out(s).exists()]
    for s in shots:
        if s not in todo:
            print(f"  kept: {out(s).name}")
    reqs = [fal.Request(tool, m, s["id"], out(s), secs[s["id"]]) for s in todo]
    for r in reqs:
        print(f"  {r.shot}: {r.dur:g}s on {m.name} (${r.usd:.3f})")
    fal.plan(reqs, budget)
    if not reqs or dry_run:
        return []
    fc = fal.client()
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(pair: tuple[dict, fal.Request]) -> Path:
        s, r = pair
        t0 = time.time()
        args = m.video_args(fc.upload_file(str(start_image(sl, s, keyframes))), prompt_for(sl, s), r.dur)
        res = fal.subscribe(fc, m, args)
        fal.download(res["video"]["url"], r.out)
        fal.log_spend(log, r, time.time() - t0)
        got, (w, h) = sheets.duration(r.out), sheets.size(r.out)
        try:  # the clip is paid for and on disk: a failed strip must not lose it
            strip = sheets.frame_strip(r.out, verify / f"{r.out.stem}_strip.png").name
        except Exception as e:  # noqa: BLE001
            strip = f"FAILED ({e}); make it by hand before using the clip"
        need = needs[s["id"]] if dur == "fit" else float(dur)
        warn = f"  WARNING: shorter than the {need:.2f}s needed" if got + 0.02 < need else ""
        warn += "  WARNING: not portrait" if sl.aspect == "9:16" and w >= h else ""
        print(f"  clip: {r.out.name} {got:.2f}s {w}x{h} ({time.time() - t0:.0f}s) strip {strip}{warn}", flush=True)
        return r.out

    with ThreadPoolExecutor(max(1, jobs)) as ex:
        written = list(ex.map(one, zip(todo, reqs)))
    fal.print_total(log)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit", type=Path, help="the project's edit/ folder (holds shots.json)")
    ap.add_argument("ids", nargs="*", help="only these shots (default: every shot with `motion`)")
    ap.add_argument("--model", default=fal.DEFAULT_VIDEO)
    ap.add_argument("--dur", default="fit", help="seconds per clip, or `fit` (timeline.json + handle)")
    ap.add_argument("--suffix", default="", help="output name suffix, e.g. _k25 for an A/B take")
    ap.add_argument("--redo", action="store_true", help="replace existing clips")
    ap.add_argument("--jobs", type=int, default=6, help="requests in parallel")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and estimate, send nothing")
    fal.add_budget_arg(ap)
    a = ap.parse_args()
    if a.dur != "fit":
        try:
            float(a.dur)
        except ValueError:
            ap.error("--dur takes seconds or `fit`")
    edit = a.edit.resolve()
    needs = read_timeline(edit / "timeline.json") if a.dur == "fit" else {}
    run(shotlist.ShotList(edit / "shots.json"), a.ids, edit / "keyframes", edit / "shots", edit / fal.SPEND_LOG,
        edit / "verify", a.model, a.dur, needs, HANDLE, a.suffix, a.redo, a.budget, a.jobs, a.dry_run)


if __name__ == "__main__":
    main()
