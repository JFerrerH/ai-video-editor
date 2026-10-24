"""Shot lists (`edit/shots.json`, or a brand library's `spec.json`) and their validation.

Shape (see templates/shots.json):
    world   text describing the shared set, sent with every keyframe
    style   optional look words added to every animation prompt (e.g. "paper cut-out", "claymation")
    aspect  "9:16" (default), "16:9", "1:1" or "4:5"
    cast    {name: {"ref": still path, "desc": what the character looks like}}
    shots   [{id, line, cast, frame, motion, camera, base?, src?} | {id, line, library}]
            (a library's spec.json names this list `clips`)

Paths (`ref`, `base`, `src`) are relative to the folder holding the JSON. Every check runs before
any paid call and exits naming the shot and the problem.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ASPECTS = {"9:16", "16:9", "1:1", "4:5"}


class ShotList:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.root = self.path.parent
        self.data = json.loads(self.path.read_text())
        self.shots: list[dict] = self.data.get("shots", self.data.get("clips", []))
        self.cast: dict = self.data.get("cast", {})
        self.world: str = self.data.get("world", "")
        self.style: str = self.data.get("style", "")
        self.aspect: str = self.data.get("aspect", "9:16")

    def resolve(self, rel: str) -> Path:
        return (self.root / rel).resolve()

    def by_id(self, ids: list[str] | None) -> list[dict]:
        if not ids:
            return list(self.shots)
        known = {s["id"] for s in self.shots}
        if missing := [i for i in ids if i not in known]:
            raise SystemExit(f"{self.path.name}: no shot {', '.join(missing)}")
        return [s for s in self.shots if s["id"] in ids]

    def library_dir(self) -> Path | None:
        """The brand library a project's `"library": "<id>"` shots read from."""
        if lib := self.data.get("library"):
            return (REPO / lib).resolve()
        brand = self.data.get("brand")
        return REPO / "brands" / brand / "library" if brand and brand != "none" else None

    def library_clip(self, clip_id: str) -> Path:
        lib = self.library_dir()
        if lib is None:
            raise SystemExit(f"shot uses library clip {clip_id!r} but {self.path.name} names no brand or library")
        try:
            idx = {e["id"]: e for e in json.loads((lib / "index.json").read_text())}
        except OSError:
            raise SystemExit(f"no library index at {lib / 'index.json'}") from None
        if clip_id not in idx:
            raise SystemExit(f"library clip {clip_id!r} isn't in {lib / 'index.json'}")
        return lib / idx[clip_id]["file"]


def is_library(shot: dict) -> bool:
    return bool(shot.get("library"))


def errors(sl: ShotList, shots: list[dict], need: str) -> list[str]:
    """Problems that stop a tool before any paid call. `need`: "frame" (keyframes), "motion"
    (animate) or "line" (shot cut)."""
    out = []
    if sl.aspect not in ASPECTS:
        out.append(f"aspect {sl.aspect!r} isn't one of {', '.join(sorted(ASPECTS))}")
    ids = [s.get("id") for s in sl.shots]
    for i in sorted({i for i in ids if ids.count(i) > 1}, key=str):
        out.append(f"shot id {i!r} is used twice")
    for name, c in sl.cast.items():
        if not c.get("ref"):
            out.append(f"cast {name}: no `ref` still")
        elif not sl.resolve(c["ref"]).exists():
            out.append(f"cast {name}: reference still not found: {sl.resolve(c['ref'])}")
    for s in shots:
        sid = s.get("id") or "?"
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(sid)):
            out.append(f"shot {sid!r}: id must be letters, digits, _ or -")
        if need == "line" and not str(s.get("line", "")).strip():
            out.append(f"shot {sid}: no narration `line`")
        if is_library(s):
            continue
        if need in ("frame", "motion"):
            cast = s.get("cast") or []
            if need == "frame" and not cast:
                out.append(f"shot {sid}: empty `cast`")
            for name in cast:
                if name not in sl.cast:
                    out.append(f"shot {sid}: cast member {name!r} isn't defined in `cast`")
        if need == "frame":
            if not str(s.get("frame", "")).strip():
                out.append(f"shot {sid}: no `frame` text")
            if s.get("base") and not sl.resolve(s["base"]).exists():
                out.append(f"shot {sid}: base keyframe not found: {sl.resolve(s['base'])} "
                           "(generate and approve it first)")
        if need == "motion":
            if not str(s.get("motion", "")).strip():
                out.append(f"shot {sid}: no `motion` text")
            if not str(s.get("camera", "")).strip():
                out.append(f"shot {sid}: empty `camera`; every shot needs a camera move")
    return out


def check(sl: ShotList, shots: list[dict], need: str) -> None:
    if errs := errors(sl, shots, need):
        raise SystemExit(f"{sl.path.name}: " + "\n  ".join(["fix before anything is sent:", *errs]))
