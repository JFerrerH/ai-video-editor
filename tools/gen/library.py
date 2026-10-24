"""A brand's clip library (brands/<slug>/library/, gitignored with the kit): generate, import, look up.

    uv run --group cloud tools/gen/library.py <slug> keyframes [id ...] [--n 2] [--redo]   → keyframes/<id>.png
    uv run --group cloud tools/gen/library.py <slug> clips [id ...] [--model …]            → clips/<id>.mp4 + index.json
    uv run tools/gen/library.py <slug> import <project> <shot id> --as <id> --mood warm --use "reveal, payoff"
    uv run tools/gen/library.py <slug> list [--cast hero] [--mood happy] [--use payoff]
    uv run tools/gen/library.py <slug> index                                                # re-measure / add entries

`spec.json` has the shape of a project shot list (`world`, `cast`, `style`, entries under `clips`
with `id`, `cast`, `frame`, `motion`, `camera`, `mood`, `use` and an optional `dur`, default 5 s).
Generation goes through the same keyframe and animate code as projects (estimate, --budget, spend
log in `library/gen_spend.jsonl`) and skips anything already on disk. `index.json` lists every clip
with `id, file, cast, mood, use, action, camera, dur` (measured) and `source` (`library` or the
project it was imported from). Projects use a clip with `"library": "<id>"` in their shots.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import animate
    import fal
    import keyframes
    import sheets
    import shotlist
else:
    from . import animate, fal, keyframes, sheets, shotlist

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DUR = 5.0


def lib_dir(slug: str) -> Path:
    if not (REPO / "brands" / slug / "brand.json").exists():
        raise SystemExit(f"no brand kit brands/{slug}/")
    return REPO / "brands" / slug / "library"


def read_index(lib: Path) -> list[dict]:
    try:
        return json.loads((lib / "index.json").read_text())
    except OSError:
        return []


def write_index(lib: Path, idx: list[dict]) -> None:
    (lib / "index.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False) + "\n")


def entry(cid: str, file: str, shot: dict, dur: float, source: str, **tags) -> dict:
    return {"id": cid, "file": file, "cast": tags.get("cast") or shot.get("cast", []),
            "mood": tags.get("mood") or shot.get("mood", ""), "use": tags.get("use") or shot.get("use", ""),
            "action": tags.get("action") or shot.get("motion", ""), "camera": shot.get("camera", ""),
            "dur": round(dur, 2), "source": source}


def index(lib: Path, spec: shotlist.ShotList | None) -> list[dict]:
    """Add an entry for every generated spec clip that has none; re-measure every `dur`."""
    idx = read_index(lib)
    have = {e["id"] for e in idx}
    for c in spec.shots if spec else []:
        f = lib / "clips" / f"{c['id']}.mp4"
        if c["id"] not in have and f.exists():
            idx.append(entry(c["id"], f"clips/{c['id']}.mp4", c, sheets.duration(f), "library"))
    for e in idx:
        if (lib / e["file"]).exists():
            e["dur"] = round(sheets.duration(lib / e["file"]), 2)
    write_index(lib, idx)
    return idx


def import_shot(lib: Path, project: str, shot_id: str, new_id: str, suffix: str = "", **tags) -> dict:
    edit = REPO / "footage" / project / "edit"
    if any(e["id"] == new_id for e in read_index(lib)) or (lib / "clips" / f"{new_id}.mp4").exists():
        raise SystemExit(f"library id {new_id!r} already exists; pick another --as")
    src = edit / "shots" / f"{shot_id}{suffix}.mp4"
    if not src.exists():
        raise SystemExit(f"no clip {src}")
    shot = next((s for s in shotlist.ShotList(edit / "shots.json").shots if s["id"] == shot_id), {})
    (lib / "clips").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, lib / "clips" / f"{new_id}.mp4")
    kf = edit / "keyframes" / f"{shot_id}.png"
    if kf.exists():
        (lib / "keyframes").mkdir(exist_ok=True)
        shutil.copy2(kf, lib / "keyframes" / f"{new_id}.png")
    e = entry(new_id, f"clips/{new_id}.mp4", shot, sheets.duration(lib / "clips" / f"{new_id}.mp4"), project, **tags)
    write_index(lib, read_index(lib) + [e])
    return e


def matches(e: dict, cast: str | None, mood: str | None, use: str | None) -> bool:
    return ((not cast or cast in e.get("cast", [])) and (not mood or e.get("mood") == mood)
            and (not use or use.lower() in str(e.get("use", "")).lower()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", help="brand slug (brands/<slug>/library)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keyframes", help="first frames for spec.json entries")
    c = sub.add_parser("clips", help="animate spec.json entries that have a keyframe")
    for p in (k, c):
        p.add_argument("ids", nargs="*")
        p.add_argument("--redo", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        fal.add_budget_arg(p)
    k.add_argument("--n", type=int, default=1)
    k.add_argument("--model", default=fal.DEFAULT_IMAGE)
    c.add_argument("--model", default=fal.DEFAULT_VIDEO)
    c.add_argument("--jobs", type=int, default=6)
    i = sub.add_parser("import", help="copy a finished project's shot into the library")
    i.add_argument("project")
    i.add_argument("shot")
    i.add_argument("--as", dest="new_id", required=True, help="library id")
    i.add_argument("--suffix", default="", help="clip variant: shots/<shot><suffix>.mp4")
    i.add_argument("--mood", required=True)
    i.add_argument("--use", required=True, help="what lines it fits, comma list")
    i.add_argument("--cast", help="comma list (default: the shot's cast)")
    i.add_argument("--action", help="what happens (default: the shot's motion text)")
    ls = sub.add_parser("list", help="clips filtered by tag")
    ls.add_argument("--cast")
    ls.add_argument("--mood")
    ls.add_argument("--use")
    sub.add_parser("index", help="add missing entries and re-measure durations")
    a = ap.parse_args()

    lib = lib_dir(a.slug)
    spec_path = lib / "spec.json"
    spec = shotlist.ShotList(spec_path) if spec_path.exists() else None
    log = lib / fal.SPEND_LOG
    if a.cmd in ("keyframes", "clips") and spec is None:
        raise SystemExit(f"no {spec_path}; see brands/_template/library/README.md")
    if a.cmd == "keyframes":
        keyframes.run(spec, a.ids, lib / "keyframes", log, lib / "keyframes_sheet.png", a.n, a.redo, a.budget,
                      a.model, a.dry_run, tool="library-keyframes")
    elif a.cmd == "clips":
        needs = {s["id"]: float(s.get("dur", DEFAULT_DUR)) for s in spec.shots}
        animate.run(spec, a.ids, lib / "keyframes", lib / "clips", log, lib / "verify", a.model, "fit", needs,
                    0.0, "", a.redo, a.budget, a.jobs, a.dry_run, tool="library-clips")
        if not a.dry_run:
            print(f"index: {len(index(lib, spec))} clips")
    elif a.cmd == "import":
        e = import_shot(lib, a.project, a.shot, a.new_id, a.suffix, mood=a.mood, use=a.use,
                        cast=a.cast.split(",") if a.cast else None, action=a.action)
        print(f"imported {e['id']} ({e['dur']:.2f}s) from {a.project}")
    elif a.cmd == "index":
        print(f"index: {len(index(lib, spec))} clips")
    else:
        rows = [e for e in read_index(lib) if matches(e, a.cast, a.mood, a.use)]
        for e in rows:
            print(f"{e['id']:<24} {e['dur']:5.2f}s  {','.join(e.get('cast', [])):<20} {e.get('mood', ''):<10} {e.get('use', '')}")
        print(f"{len(rows)} clip{'s' * (len(rows) != 1)}")


if __name__ == "__main__":
    main()
