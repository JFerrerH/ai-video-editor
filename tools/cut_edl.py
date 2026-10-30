"""Validate a video-use EDL before it reaches render.py, so an untrusted EDL can't run a raw ffmpeg filter or
read outside the project. Used by run_job.py's `cut` op.

    edl, errors = resolve(Path("footage/demo/edit/edl.json"), Path("footage/demo"))

Accepted (anything else is an error):
    {"version": 1,
     "sources": {"C0103": "C0103.MP4"},                                 project-relative video files
     "ranges": [{"source", "start", "end", "beat"?, "quote"?, "reason"?, "note"?}],   inside each source
     "grade": "auto" | "none" | "<video-use preset>",                   never a filter string
     "overlays": [{"file", "start_in_output", "duration"}],             project-relative video files
     "subtitles": "edit/master.srt",                                    a project .srt
     "total_duration_s": 87.4}                                          informational
The resolved EDL carries absolute (confined) paths and the computed total; render.py reads it unchanged.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from short_spec import _VU_PRESETS, MEDIA_EXT, TAKE_RE, _V

MAX_TOTAL, MAX_RANGES = 3 * 3600.0, 2000
GRADES = set(_VU_PRESETS) | {"auto", "none"}
TEXT_FIELDS = ("beat", "quote", "reason", "note")


def _duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def resolve(edl_path: Path, root: Path) -> tuple[dict, list[str]]:
    root = root.resolve()
    try:
        edl: Any = json.loads(Path(edl_path).read_text())
    except (OSError, ValueError) as e:
        return {}, [f"can't read the EDL: {e}"]
    V = _V()
    if not V.obj(edl, "edl", {"version", "sources", "ranges", "grade", "overlays", "subtitles", "total_duration_s"},
                 {"sources", "ranges"}):
        return {}, V.errors
    out: dict = {"version": 1}
    if edl.get("version", 1) != 1:
        V.err("version", "must be 1")
    srcs, durs = {}, {}
    if V.obj(edl["sources"], "sources", set(edl["sources"]) if isinstance(edl["sources"], dict) else set()):
        for name, f in edl["sources"].items():
            if not TAKE_RE.fullmatch(name):
                V.err(f"sources.{name}", "source names are letters, digits, _ and -")
            elif p := V.path(f, f"sources.{name}", root, ext=MEDIA_EXT):
                srcs[name], durs[name] = str(p), _duration(p)
    out["sources"] = srcs
    ranges, total = [], 0.0
    if not isinstance(edl["ranges"], list) or not edl["ranges"]:
        V.err("ranges", "must be a non-empty list")
    elif len(edl["ranges"]) > MAX_RANGES:
        V.err("ranges", f"{len(edl['ranges'])} ranges; the limit is {MAX_RANGES}")
    else:
        for i, r in enumerate(edl["ranges"]):
            w = f"ranges[{i}]"
            if not V.obj(r, w, {"source", "start", "end", *TEXT_FIELDS}, {"source", "start", "end"}):
                continue
            for k in TEXT_FIELDS:
                if k in r:
                    V.str_(r[k], f"{w}.{k}")
            if r["source"] not in srcs:
                V.err(f"{w}.source", f"unknown source {r['source']!r}")
                continue
            if not (V.num(r["start"], f"{w}.start", 0) and V.num(r["end"], f"{w}.end", 0)):
                continue
            if r["end"] - r["start"] < 0.04:
                V.err(w, "`end` must be after `start`")
            elif r["end"] > durs[r["source"]] + 0.05:
                V.err(w, f"ends at {r['end']} s, after the end of {r['source']} ({durs[r['source']]:.2f} s)")
            total += r["end"] - r["start"]
            ranges.append({k: r[k] for k in ("source", "start", "end", *TEXT_FIELDS) if k in r})
    if total > MAX_TOTAL:
        V.err("ranges", f"{total / 3600:.1f} h of output; the limit is 3 h")
    out["ranges"], out["total_duration_s"] = ranges, round(total, 3)
    grade = edl.get("grade", "none")
    if V.str_(grade, "grade", choices=GRADES):
        out["grade"] = grade
    overlays = edl.get("overlays", [])
    if not isinstance(overlays, list):
        V.err("overlays", "must be a list")
    else:
        out["overlays"] = []
        for i, ov in enumerate(overlays):
            w = f"overlays[{i}]"
            if V.obj(ov, w, {"file", "start_in_output", "duration"}, {"file", "start_in_output", "duration"}):
                p = V.path(ov["file"], f"{w}.file", root, ext=MEDIA_EXT)
                ok = V.num(ov["start_in_output"], f"{w}.start_in_output", 0, MAX_TOTAL) & \
                    V.num(ov["duration"], f"{w}.duration", 0.04, MAX_TOTAL)
                if p and ok:
                    out["overlays"].append({"file": str(p), "start_in_output": float(ov["start_in_output"]),
                                            "duration": float(ov["duration"])})
    if edl.get("subtitles") is not None:
        p = V.path(edl["subtitles"], "subtitles", root, ext={".srt"})
        if p:
            out["subtitles"] = str(p)
    return out, V.errors
