"""Data-only short-form spec: `edit/short.json` → the same `shortform.Project` a build.py makes.

    from short_spec import load, check
    p, report = load(Path("footage/demo/edit/short.json"))   # validated, edges refined, anchors resolved
    p.build(preview=True)
    res = check(Path("footage/demo/edit/short.json"))       # {"errors", "warnings", "duration", "timeline", "edges"}

Nothing in a spec is executed: every field is checked against a fixed shape, every file must sit inside
the project (or the shared assets/), grades are preset names, never filter strings. So a spec written by
someone untrusted is safe to check and render. Shape (all keys optional unless noted):

    {"version": 1, "brand": "none" | "<slug>",
     "sources": {"take1": {"file": "edit/conformed/take1.mov", "face": [540, 900]}},         required
     "segments": [{"take", "in", "out", "zoom": {"kind": "static", "scale": 1.0}, "look": null | "bw",
                   "freeze_after": 0, "lock_in": false, "lock_out": false, "repeat": false, "note": ""}], required
     "captions": {"fixes": {"heard": "said"}, "word_fixes": [{"take", "at", "text"}],
                  "skip": [{"take", "at"}], "props": {}, "style": {}, "engine": "remotion" | "ass"},
     "emphasis": [{"take", "phrase", "after"}],
     "events": [{"type", "start": T, "end": T | "duration": s, "props": {}, "name"}],
     "sfx": [{"name", "at": T, "gain_db"}],
     "public_files": {"site/img-00.png": "edit/downloads/site/img-00.png"},
     "grade": null | "<preset>", "lufs": -14.0,
     "edges": {"above_floor": 9, "pre": 0.10, "post": 0.12, "min_sil": 0.06}}   refine_edges() settings

`edges.above_floor` 28 suits very low noise floors (iPhone voice isolation): see short-form-pro gotchas.

Timeline rules (errors): two segments of one take may not cover the same source time, before or after edge
refinement (it would play twice), unless the later one says `"repeat": true`. Contiguous cuts of one take
(the next in ≤ 0.6 s after an out) are joined at the quietest point between them. An unlocked edge that
can't reach silence may not sit inside a word, and an unlocked edge may not land on sound louder than
`above_floor` + 3 dB over the room tone (above `above_floor`, or on a locked edge, it is a warning).

Zooms: static {scale} | push {from, to} | punch {base, peak, at} | outpunch {from, to, peak, at}, where a
punch's `at` is a SOURCE time in the segment's take: seconds, or {"word", "after"?, "edge"?, "offset"?}.
A time T (event start/end, sfx at) is OUTPUT seconds, or an anchor resolved after edge refinement:
    {"word": "launch", "take": "take1", "after": 12.0, "edge": "start" | "end", "offset": 0.2}
    {"seg": 2, "edge": "start" | "end", "offset": -0.1}

An event's props follow its component's schema (tools/motion/src/**/<Type>.schema.json, all of them:
`uv run tools/overlay_schema.py --export`). Time props (`lines[].at`, `countEnd`…) are seconds from the
EVENT's start, or an anchor as above, and must land inside the event with every entrance finished
before it ends.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

import overlay_schema
from shortform import LOOKS, REPO, SFX_DIR, Project, Seg, _norm

ASSETS = REPO / "assets"
BRANDS = REPO / "brands"
sys.path.insert(0, str(REPO / "vendor" / "video-use" / "helpers"))
try:
    from grade import PRESETS as _VU_PRESETS
except Exception:  # video-use not cloned: only the engine's own grades
    _VU_PRESETS = {}

DEFAULT_GRADE = Project.__dataclass_fields__["grade"].default
GRADES = {**_VU_PRESETS, "default": DEFAULT_GRADE, "none": ""}

MAX_DURATION, MAX_SEGMENTS, MAX_EVENTS, MAX_SFX = 180.0, 120, 200, 200
TAKE_RE = re.compile(r"^[A-Za-z0-9][\w-]{0,63}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PUBLIC_RE = re.compile(r"^(?!.*\.\.)[\w-][\w./-]*$")
MEDIA_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
ZOOMS = {"static": ("scale",), "push": ("from", "to"), "punch": ("base", "peak", "at"),
         "outpunch": ("from", "to", "peak", "at")}
EDGE_LIMITS = {"above_floor": (3, 40), "pre": (0, 0.5), "post": (0, 0.5), "min_sil": (0.02, 0.3)}
CAPTION_STYLE = {"font": str, "size": int, "outline": int, "shadow": int, "margin_v": int, "active": str, "base": str}


# overlay components and scene primitives both render as events; captions come from the engine
OVERLAY_TYPES = overlay_schema.COMPONENTS
FILE_KEYS = {"src", "logo"}  # the props tools/motion loads with staticFile(): must name a staged public file
SFX_NAMES = {p.stem for p in SFX_DIR.glob("*.wav")}


class SpecError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(errors[0] if errors else "invalid spec")
        self.errors = errors


# ── shape checks (collect every error, each naming its field path) ───────
def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class _V:
    def __init__(self):
        self.errors: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def obj(self, v: Any, where: str, allowed: set[str], required: set[str] = frozenset()) -> bool:
        if not isinstance(v, dict):
            self.err(where, "must be an object")
            return False
        for k in sorted(set(v) - allowed):
            self.err(where, f"unknown field {k!r}")
        for k in sorted(required - set(v)):
            self.err(where, f"missing field {k!r}")
        return True

    def num(self, v: Any, where: str, lo: float | None = None, hi: float | None = None) -> bool:
        if not _num(v):
            self.err(where, "must be a number")
            return False
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            self.err(where, f"must be between {lo} and {hi}, got {v}")
            return False
        return True

    def str_(self, v: Any, where: str, pattern: re.Pattern | None = None, choices=None) -> bool:
        if not isinstance(v, str) or "\x00" in v:
            self.err(where, "must be a string")
            return False
        if pattern and not pattern.fullmatch(v):
            self.err(where, f"invalid value {v!r}")
            return False
        if choices is not None and v not in choices:
            self.err(where, f"must be one of {sorted(choices)}, got {v!r}")
            return False
        return True

    def bool_(self, v: Any, where: str) -> None:
        if not isinstance(v, bool):
            self.err(where, "must be true or false")

    def path(self, v: Any, where: str, root: Path, assets: bool = False, ext: set[str] | None = None) -> Path | None:
        if not self.str_(v, where):
            return None
        p = (root / v).resolve()
        allowed = [root.resolve()] + ([ASSETS.resolve()] if assets else [])
        if not any(p == a or p.is_relative_to(a) for a in allowed):
            self.err(where, f"path {v!r} is outside the project")
            return None
        if not p.is_file():
            self.err(where, f"not found: {v}")
            return None
        if ext and p.suffix.lower() not in ext:
            self.err(where, f"must be a {'/'.join(sorted(ext))} file")
            return None
        return p


def _check_word_anchor(V: _V, a: Any, where: str, takes: set[str], take_required: bool) -> None:
    keys = {"word", "after", "edge", "offset"} | ({"take"} if take_required else set())
    if not V.obj(a, where, keys, {"word"} | ({"take"} if take_required else set())):
        return
    V.str_(a["word"], f"{where}.word")
    if take_required and V.str_(a.get("take"), f"{where}.take") and a["take"] not in takes:
        V.err(f"{where}.take", f"unknown take {a['take']!r}")
    if "after" in a:
        V.num(a["after"], f"{where}.after", 0)
    if "edge" in a:
        V.str_(a["edge"], f"{where}.edge", choices={"start", "end"})
    if "offset" in a:
        V.num(a["offset"], f"{where}.offset", -30, 30)


def _check_time(V: _V, t: Any, where: str, takes: set[str], n_segs: int) -> None:
    if _num(t):
        V.num(t, where, 0, MAX_DURATION)
    elif isinstance(t, dict) and "seg" in t:
        if V.obj(t, where, {"seg", "edge", "offset"}, {"seg", "edge"}):
            if not (isinstance(t["seg"], int) and not isinstance(t["seg"], bool) and 0 <= t["seg"] < n_segs):
                V.err(f"{where}.seg", f"must be a segment index 0–{n_segs - 1}")
            V.str_(t["edge"], f"{where}.edge", choices={"start", "end"})
            if "offset" in t:
                V.num(t["offset"], f"{where}.offset", -30, 30)
    elif isinstance(t, dict):
        _check_word_anchor(V, t, where, takes, take_required=True)
    else:
        V.err(where, "must be seconds, a word anchor or a segment anchor")


def _check_json(V: _V, v: Any, where: str, public: set[str], depth: int = 0) -> None:
    """Overlay props: plain JSON; any file prop (FILE_KEYS) must name a staged public file."""
    if depth > 12:
        V.err(where, "nested too deeply")
    elif isinstance(v, dict):
        for k, x in v.items():
            if k in FILE_KEYS and isinstance(x, str) and x not in public:
                V.err(f"{where}.{k}", f"{x!r} is not a public file (add it to public_files)")
            _check_json(V, x, f"{where}.{k}", public, depth + 1)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _check_json(V, x, f"{where}[{i}]", public, depth + 1)
    elif isinstance(v, str) and len(v) > 4000:
        V.err(where, "string longer than 4000 characters")


def _check_props(V: _V, type_: str, props: dict, where: str, takes: set[str], n_segs: int) -> None:
    """Event props against the component's schema (tools/motion/src/**/<type>.schema.json). Time props
    are seconds from the event's start, or an anchor (same shapes as an event's `start`)."""
    for path, msg in overlay_schema.validate(type_, props, anchors=True):
        V.err(f"{where}.{path} ({type_})" if path else f"{where} ({type_})", msg)
    for path, v, _, _ in overlay_schema.time_fields(type_, props):
        if isinstance(v, dict):
            _check_time(V, v, f"{where}.{path}", takes, n_segs)


def validate(spec: Any, root: Path, edit_dir: Path) -> list[str]:
    """Every shape error in the spec (empty = valid). Reads no media."""
    V = _V()
    top = {"version", "brand", "sources", "segments", "captions", "emphasis", "events", "sfx",
           "public_files", "grade", "lufs", "edges"}
    if not V.obj(spec, "spec", top, {"sources", "segments"}):
        return V.errors
    if spec.get("version", 1) != 1:
        V.err("version", "must be 1")
    brand = spec.get("brand", "none")
    if brand is not None and V.str_(brand, "brand", SLUG_RE) and brand != "none" \
            and not (BRANDS / brand / "brand.json").is_file():
        V.err("brand", f"no brand kit for {brand!r} (brands/{brand}/brand.json); use \"none\" for neutral")
    if spec.get("grade") is not None:
        V.str_(spec["grade"], "grade", choices=set(GRADES))
    if "lufs" in spec:
        V.num(spec["lufs"], "lufs", -24, -9)
    if V.obj(spec.get("edges", {}), "edges", set(EDGE_LIMITS)):
        for k, v in spec["edges"].items() if "edges" in spec else ():
            if k in EDGE_LIMITS:
                V.num(v, f"edges.{k}", *EDGE_LIMITS[k])

    takes: set[str] = set()
    sources = spec.get("sources")
    if V.obj(sources, "sources", set(sources) if isinstance(sources, dict) else set()):
        if not sources:
            V.err("sources", "needs at least one take")
        for take, s in sources.items():
            w = f"sources.{take}"
            if not TAKE_RE.fullmatch(take):
                V.err(w, "take names are letters, digits, _ and - (max 64)")
                continue
            takes.add(take)
            if not V.obj(s, w, {"file", "face"}, {"file", "face"}):
                continue
            V.path(s["file"], f"{w}.file", root, ext=MEDIA_EXT)
            f = s["face"]
            if not (isinstance(f, list) and len(f) == 2 and all(_num(x) and 0 <= x <= 8192 for x in f)):
                V.err(f"{w}.face", "must be [x, y] in source pixels (run the face op for a suggestion)")
            if not (edit_dir / "transcripts" / f"{take}.json").is_file():
                V.err(w, f"no transcript at edit/transcripts/{take}.json (transcribe the take first)")

    segs = spec.get("segments")
    n_segs = 0
    if not isinstance(segs, list) or not segs:
        V.err("segments", "must be a non-empty list")
    elif len(segs) > MAX_SEGMENTS:
        V.err("segments", f"{len(segs)} segments; the limit is {MAX_SEGMENTS}")
    else:
        n_segs = len(segs)
        planned = 0.0
        for i, s in enumerate(segs):
            w = f"segments[{i}]"
            if not V.obj(s, w, {"take", "in", "out", "zoom", "look", "freeze_after", "lock_in", "lock_out", "note",
                                "repeat"}, {"take", "in", "out"}):
                continue
            if V.str_(s["take"], f"{w}.take") and s["take"] not in takes:
                V.err(f"{w}.take", f"unknown take {s['take']!r}")
            if V.num(s["in"], f"{w}.in", 0) and V.num(s["out"], f"{w}.out", 0):
                if s["out"] - s["in"] < 0.1:
                    V.err(w, "`out` must be at least 0.1 s after `in`")
                planned += s["out"] - s["in"]
            if "freeze_after" in s and V.num(s["freeze_after"], f"{w}.freeze_after", 0, 5):
                planned += s["freeze_after"]
            if s.get("look") is not None:
                V.str_(s["look"], f"{w}.look", choices={k for k in LOOKS if k})
            for k in ("lock_in", "lock_out", "repeat"):
                if k in s:
                    V.bool_(s[k], f"{w}.{k}")
            if "note" in s:
                V.str_(s["note"], f"{w}.note")
            z = s.get("zoom", {"kind": "static", "scale": 1.0})
            if V.obj(z, f"{w}.zoom", {"kind", "scale", "from", "to", "base", "peak", "at"}, {"kind"}) \
                    and V.str_(z["kind"], f"{w}.zoom.kind", choices=set(ZOOMS)):
                need = ZOOMS[z["kind"]]
                for k in sorted(set(z) - {"kind"} - set(need)):
                    V.err(f"{w}.zoom", f"{z['kind']} zoom has no field {k!r}")
                for k in need:
                    if k not in z:
                        V.err(f"{w}.zoom", f"{z['kind']} zoom needs {k!r}")
                    elif k == "at":
                        if not _num(z["at"]):
                            _check_word_anchor(V, z["at"], f"{w}.zoom.at", takes, take_required=False)
                    else:
                        V.num(z[k], f"{w}.zoom.{k}", 1.0, 3.0)
        if planned > MAX_DURATION + 2:  # edge refinement adds a little; the exact check runs after load
            V.err("segments", f"about {planned:.0f} s of output; the limit is {MAX_DURATION:.0f} s")

    public: set[str] = set()
    pf = spec.get("public_files", {})
    if V.obj(pf, "public_files", set(pf) if isinstance(pf, dict) else set()):
        for name, src in pf.items():
            if not PUBLIC_RE.fullmatch(name) or name.startswith("fonts/"):
                V.err(f"public_files.{name}", "names are relative (letters, digits, _ - . /), no '..', not under fonts/")
                continue
            if V.path(src, f"public_files.{name}", root, assets=True):
                public.add(name)

    caps = spec.get("captions", {})
    if V.obj(caps, "captions", {"fixes", "word_fixes", "skip", "props", "style", "engine"}):
        fx = caps.get("fixes", {})
        if not (isinstance(fx, dict) and all(isinstance(k, str) and isinstance(x, str) for k, x in fx.items())):
            V.err("captions.fixes", "must map heard → said strings")
        for key, extra in (("word_fixes", {"text"}), ("skip", set())):
            items = caps.get(key, [])
            if not isinstance(items, list):
                V.err(f"captions.{key}", "must be a list")
                continue
            for i, it in enumerate(items):
                w = f"captions.{key}[{i}]"
                if V.obj(it, w, {"take", "at"} | extra, {"take", "at"} | extra):
                    if V.str_(it["take"], f"{w}.take") and it["take"] not in takes:
                        V.err(f"{w}.take", f"unknown take {it['take']!r}")
                    V.num(it["at"], f"{w}.at", 0)
                    if extra:
                        V.str_(it["text"], f"{w}.text")
        if "props" in caps and V.obj(caps["props"], "captions.props", set(caps["props"]) if isinstance(caps["props"], dict) else set()):
            _check_json(V, caps["props"], "captions.props", public)
        st = caps.get("style", {})
        if V.obj(st, "captions.style", set(CAPTION_STYLE)):
            for k, v in st.items():
                if not isinstance(v, CAPTION_STYLE[k]) or isinstance(v, bool) or (isinstance(v, str) and not re.fullmatch(r"[\w &#-]{1,64}", v)):
                    V.err(f"captions.style.{k}", f"must be a {CAPTION_STYLE[k].__name__}")
        if "engine" in caps:
            V.str_(caps["engine"], "captions.engine", choices={"remotion", "ass"})

    emph = spec.get("emphasis", [])
    if not isinstance(emph, list):
        V.err("emphasis", "must be a list")
    else:
        for i, e in enumerate(emph):
            w = f"emphasis[{i}]"
            if V.obj(e, w, {"take", "phrase", "after"}, {"take", "phrase"}):
                if V.str_(e["take"], f"{w}.take") and e["take"] not in takes:
                    V.err(f"{w}.take", f"unknown take {e['take']!r}")
                V.str_(e["phrase"], f"{w}.phrase")
                if "after" in e:
                    V.num(e["after"], f"{w}.after", 0)

    events = spec.get("events", [])
    if not isinstance(events, list):
        V.err("events", "must be a list")
    elif len(events) > MAX_EVENTS:
        V.err("events", f"{len(events)} events; the limit is {MAX_EVENTS}")
    else:
        for i, e in enumerate(events):
            w = f"events[{i}]"
            if not V.obj(e, w, {"type", "start", "end", "duration", "props", "name"}, {"type", "start"}):
                continue
            V.str_(e["type"], f"{w}.type", choices=OVERLAY_TYPES)
            _check_time(V, e["start"], f"{w}.start", takes, n_segs)
            if ("end" in e) == ("duration" in e):
                V.err(w, "give exactly one of `end` or `duration`")
            elif "end" in e:
                _check_time(V, e["end"], f"{w}.end", takes, n_segs)
            else:
                V.num(e["duration"], f"{w}.duration", 0.05, MAX_DURATION)
            if "name" in e:
                V.str_(e["name"], f"{w}.name")
            props = e.get("props", {})
            if V.obj(props, f"{w}.props", set(props) if isinstance(props, dict) else set()):
                _check_json(V, props, f"{w}.props", public)
                if e["type"] in OVERLAY_TYPES:
                    _check_props(V, e["type"], props, f"{w}.props", takes, n_segs)

    sfx = spec.get("sfx", [])
    if not isinstance(sfx, list):
        V.err("sfx", "must be a list")
    elif len(sfx) > MAX_SFX:
        V.err("sfx", f"{len(sfx)} sound effects; the limit is {MAX_SFX}")
    else:
        for i, x in enumerate(sfx):
            w = f"sfx[{i}]"
            if V.obj(x, w, {"name", "at", "gain_db"}, {"name", "at"}):
                if V.str_(x["name"], f"{w}.name") and x["name"] not in SFX_NAMES:
                    V.err(f"{w}.name", f"no sound effect {x['name']!r} in assets/sfx/synth (run tools/sfx_synth.py)")
                _check_time(V, x["at"], f"{w}.at", takes, n_segs)
                if "gain_db" in x:
                    V.num(x["gain_db"], f"{w}.gain_db", -40, 6)
    return V.errors


# ── load: validate → Segs → Project → refine edges → resolve anchors ─────
def project_root(spec_path: Path) -> Path:
    """The project a file belongs to: footage/<project>/ when it sits under footage/, else the
    parent of the directory holding it (spec in <root>/edit/)."""
    spec_path = spec_path.resolve()
    footage = (REPO / "footage").resolve()
    if spec_path.is_relative_to(footage) and len(spec_path.relative_to(footage).parts) >= 2:
        return footage / spec_path.relative_to(footage).parts[0]
    return spec_path.parent.parent


def _read(spec_path: Path) -> Any:
    try:
        return json.loads(spec_path.read_text())
    except FileNotFoundError:
        raise SpecError([f"spec not found: {spec_path.name}"]) from None
    except json.JSONDecodeError as e:
        raise SpecError([f"{spec_path.name} is not valid JSON: {e}"]) from None


def _src_word(p: Project, take: str, a: dict) -> float:
    """SOURCE time of a word anchor (zoom punches are placed in source time)."""
    after = a.get("after", 0.0)
    for w in p._words(take):
        if w["start"] >= after - 0.01 and _norm(w["text"]) == _norm(a["word"]):
            return (w["end"] if a.get("edge") == "end" else w["start"]) + a.get("offset", 0.0)
    raise ValueError(f"word {a['word']!r} not found in {take} after {after}")


def _out_time(p: Project, t: Any, offs: list[float]) -> float:
    if _num(t):
        return float(t)
    if "seg" in t:
        return offs[t["seg"] + (1 if t["edge"] == "end" else 0)] + t.get("offset", 0.0)
    return p.word(t["take"], t["word"], t.get("after", 0.0), t.get("edge") == "end") + t.get("offset", 0.0)


def _zoom(z: dict, at: float | None) -> tuple:
    k = z["kind"]
    if k == "static":
        return ("static", z["scale"])
    if k == "push":
        return ("push", z["from"], z["to"])
    if k == "punch":
        return ("punch", z["base"], z["peak"], at)
    return ("outpunch", z["from"], z["to"], z["peak"], at)


# ── timeline integrity ────────────────────────────────────────────────────
JOIN_GAP = 0.6  # s: same-take cuts closer than this in the source are one continuous cut


def _plain(text: str) -> str:
    return re.sub(r"[.,;:!?…]+$", "", text.strip())


def _overlaps(p: Project, raw: list[dict], refined: bool, skip: set[tuple[int, int]] = frozenset()) -> tuple[list[str], set]:
    """Errors for same-take segments covering the same source time (the later one in output order may
    say `repeat: true`). Returns (errors, pairs reported)."""
    errors, pairs = [], set()
    segs = p.segments
    for j, b in enumerate(segs):
        for i in range(j):
            a = segs[i]
            if a.take != b.take or raw[j].get("repeat") or (i, j) in skip:
                continue
            lo, hi = max(a.t_in, b.t_in), min(a.t_out, b.t_out)
            if hi - lo <= 0.001:
                continue
            words = " ".join(_plain(w["text"]) for w in p._words(a.take) if lo <= (w["start"] + w["end"]) / 2 <= hi)
            said = f'"{words}" would play twice' if words else "that audio would play twice"
            when = "after edge refinement, " if refined else ""
            fix = (f'lock the edges ("lock_in"/"lock_out") or leave a gap between them' if refined else
                   f"start segments[{j}] at {a.t_out:.2f}" if b.t_in >= a.t_in else f"end segments[{j}] at {a.t_in:.2f}")
            errors.append(f"{when}segments[{j}] ({b.take} {b.t_in:.2f}–{b.t_out:.2f}) overlaps segments[{i}] "
                          f"({a.take} {a.t_in:.2f}–{a.t_out:.2f}) by {hi - lo:.2f} s: {said}; {fix}, "
                          f'or set "repeat": true on segments[{j}] if the repeat is deliberate')
            pairs.add((i, j))
    return errors, pairs


def _joins(p: Project) -> list[tuple[int, int]]:
    """(i, j): segment i's out is followed in the same take, within JOIN_GAP s, by segment j's in."""
    out, used = [], set()
    for i, a in enumerate(p.segments):
        for j, b in enumerate(p.segments):
            if i != j and a.take == b.take and 0 <= b.t_in - a.t_out <= JOIN_GAP and (j, "in") not in used:
                out.append((i, j))
                used.add((j, "in"))
                break
    return out


def _pause_near(p: Project, take: str, t: float, edge: str, above_floor: float, reach: float = 3.0) -> float | None:
    """The nearest pause (≥ 60 ms under floor + above_floor) on the outward side of an edge: before an
    in-point, after an out-point; its end next to the speech the cut keeps, with a little air. None within
    `reach` s."""
    db, floor = p._env(take)
    quiet = db < floor + above_floor
    hop, n = 0.005, len(db)
    k, step, stop = int(t / hop), (-1 if edge == "in" else 1), int((t + (-reach if edge == "in" else reach)) / hop)
    run = 0
    while 0 <= k < n and (k > stop if edge == "in" else k < stop):
        run = run + 1 if quiet[k] else 0
        if run * hop >= 0.06:
            # back toward the edge: the end of this pause nearest the speech the cut keeps
            j = k
            while 0 <= j - step < n and quiet[j - step]:
                j -= step
            return round(j * hop - 0.05 if edge == "in" else j * hop + 0.1, 2)
        k += step
    return None


def _on_sound(p: Project, take: str, t: float, above_floor: float) -> bool:
    db, floor = p._env(take)
    k = int(t / 0.005)
    return float(db[max(0, k - 3):k + 3].max() - floor) > above_floor + 3


def _edge_rules(p: Project, details: list[dict], above_floor: float) -> tuple[list[str], list[str], list[dict]]:
    """(errors, warnings, energies): edges inside a word and edges on sound, in words."""
    errors, warnings = [], []
    _, energy = p.edge_energy(detail=True)
    in_word = set()
    for d in details:
        if d["tag"] == "joined" or not (d["locked"] or d["tag"].startswith("WARN")):
            continue
        s = p.segments[d["seg"]]
        w = next((w for w in p._words(s.take) if w["start"] + 0.02 < d["t"] < w["end"] - 0.02), None)
        where = f"segments[{d['seg']}].{d['edge']} {d['t']:.2f}"
        if w:
            msg = f'{where} is inside "{_plain(w["text"])}" ({w["start"]:.2f}–{w["end"]:.2f}): use {w["start"]:.2f} or {w["end"]:.2f}'
            if _on_sound(p, s.take, w["start"], above_floor) and _on_sound(p, s.take, w["end"], above_floor):
                x = _pause_near(p, s.take, d["t"], d["edge"], above_floor)
                msg += (f"; both run into the next word with no pause, the nearest pause {'before' if d['edge'] == 'in' else 'after'}"
                        f" it is at {x:.2f}" if x is not None else "; both run into the next word with no pause")
            (warnings if d["locked"] else errors).append(msg)
            in_word.add((d["seg"], d["edge"]))
        elif not d["locked"]:
            side = "before" if d["edge"] == "in" else "after"
            warnings.append(f"{where}: no silence {side} it within reach, so edge refinement left it where it is")
    by_edge = {(d["seg"], d["edge"]): d for d in details}
    for e in energy:
        for edge, db, verb in (("in", e["head_db"], "starts"), ("out", e["tail_db"], "ends")):
            d = by_edge[(e["seg"], edge)]
            if db <= above_floor or (e["seg"], edge) in in_word or d["tag"] == "joined":
                continue
            where = f"segments[{e['seg']}].{edge} {d['t']:.2f}"
            lock = f'"lock_{edge}"'
            if db > above_floor + 3 and not d["locked"]:
                x = _pause_near(p, p.segments[e["seg"]].take, d["t"], edge, above_floor)
                near = f" (the nearest is at {x:.2f})" if x is not None else ""
                errors.append(f"{where} {verb} in the middle of sound: +{db:.1f} dB over the room tone; "
                              f"move it into a pause{near}, or set {lock}: true if the sound is meant to be cut")
            elif d["locked"] and db > above_floor + 3:
                warnings.append(f"{where} {verb} in the middle of sound: +{db:.1f} dB over the room tone (locked)")
            else:
                warnings.append(f"{where} {verb} on a quiet sound, +{db:.1f} dB over the room tone "
                                f"(a breath or the tail of a word?)")
    return errors, warnings, energy


def _event_props(p: Project, i: int, type_: str, props: dict, start: float, dur: float, offs: list[float],
                 errors: list[str]) -> dict:
    """Props with every time prop resolved to seconds from the event's start (anchors → numbers), each
    checked to land inside the event, and every entrance checked to finish before the event ends."""
    where = f"events[{i}].props"
    bad: list[str] = []
    for path, v, parent, key in overlay_schema.time_fields(type_, props):
        if isinstance(v, dict):
            try:
                out = _out_time(p, v, offs)
            except ValueError as e:
                errors.append(f"{where}.{path} ({type_}): {e}")
                bad.append(path)
                continue
            t = round(out - start, 3)
            if not 0 <= t < dur:
                errors.append(f"{where}.{path} ({type_}): the anchor lands at {out:.2f} s, which is outside the event "
                              f"(it starts at {start:.2f} s and lasts {dur:.1f} s)")
                bad.append(path)
                continue
            parent[key] = t
        elif not 0 <= v < dur:
            hint = f"; prop times are seconds from the event's start: did you mean {v - start:.1f}?" \
                if start <= v < start + dur else ""
            errors.append(f"{where}.{path} ({type_}): {v:g} s is outside the event "
                          f"(it starts at {start:.2f} s and lasts {dur:.1f} s){hint}")
            bad.append(path)
    for path, t, end in overlay_schema.cue_finish(type_, props, p.fps, dur):
        if any(b == path or b.startswith(path + ".") for b in bad):
            continue  # its time is already reported
        if end >= dur:
            errors.append(f"{where}.{path} ({type_}): starts appearing at {t:.2f} s and finishes at {end:.2f} s, "
                          f"after the event ends ({dur:.2f} s); give it an earlier time or make the event longer")
    return props


def load(spec_path: Path, root: Path | None = None) -> tuple[Project, dict]:
    """Validated Project with edges refined and every anchor resolved. Raises SpecError(errors)."""
    spec_path = Path(spec_path).resolve()
    root = (root or project_root(spec_path)).resolve()
    edit_dir = spec_path.parent
    spec = _read(spec_path)
    if errors := validate(spec, root, edit_dir):
        raise SpecError(errors)
    caps = spec.get("captions", {})
    segs = []
    for s in spec["segments"]:
        segs.append(Seg(s["take"], float(s["in"]), float(s["out"]), ("static", 1.0), s.get("look"),
                        float(s.get("freeze_after", 0.0)), s.get("note", ""),
                        s.get("lock_in", False), s.get("lock_out", False)))
    grade = spec.get("grade")
    p = Project(
        edit_dir=edit_dir,
        sources={k: (root / v["file"]).resolve() for k, v in spec["sources"].items()},
        face={k: (round(v["face"][0]), round(v["face"][1])) for k, v in spec["sources"].items()},
        segments=segs,
        brand=None if spec.get("brand") in (None, "none") else spec["brand"],
        public_files={k: (root / v).resolve() for k, v in spec.get("public_files", {}).items()},
        grade=GRADES[grade] if grade else DEFAULT_GRADE,
        caption_fixes=caps.get("fixes", {}),
        caption_word_fixes={(w["take"], float(w["at"])): w["text"] for w in caps.get("word_fixes", [])},
        caption_style=caps.get("style", {}),
        caption_engine=caps.get("engine", "remotion"),
        emphasis=[(e["take"], e["phrase"], float(e.get("after", 0.0))) for e in spec.get("emphasis", [])],
        caption_props=caps.get("props", {}),
        caption_skip=[(w["take"], float(w["at"])) for w in caps.get("skip", [])],
        lufs=float(spec.get("lufs", -14.0)),
    )
    if errors := p.source_errors():
        raise SpecError(errors)
    errors, reported = _overlaps(p, spec["segments"], refined=False)
    settings = spec.get("edges", {})
    edges, details = p.refine_edges(**settings, joins=_joins(p), detail=True)
    errors += _overlaps(p, spec["segments"], refined=True, skip=reported)[0]
    edge_errors, warnings, energy = _edge_rules(p, details, settings.get("above_floor", 9.0))
    errors += edge_errors
    offs = p.offsets()
    for i, (s, raw) in enumerate(zip(p.segments, spec["segments"])):
        z = raw.get("zoom", {"kind": "static", "scale": 1.0})
        at = None
        if "at" in z:
            try:
                at = float(z["at"]) if _num(z["at"]) else _src_word(p, s.take, z["at"])
            except ValueError as e:
                errors.append(f"segments[{i}].zoom.at: {e}")
                at = s.t_in
            if not s.t_in - 0.5 <= at <= s.t_out + 0.5:
                errors.append(f"segments[{i}].zoom.at: {at:.2f} s is outside the segment ({s.t_in:.2f}–{s.t_out:.2f})")
        s.zoom = _zoom(z, at)

    def resolve(t: Any, where: str) -> float | None:
        try:
            return _out_time(p, t, offs)
        except ValueError as e:  # word() / at(): not in the transcript, or cut out
            errors.append(f"{where}: {e}")
            return None

    events = []
    for i, e in enumerate(spec.get("events", [])):
        a = resolve(e["start"], f"events[{i}] ({e['type']}) start")
        b = resolve(e["end"], f"events[{i}] ({e['type']}) end") if "end" in e else \
            (a + e["duration"] if a is not None else None)
        if a is None or b is None:
            continue
        if b - a < 0.05:
            errors.append(f"events[{i}] ({e['type']}): ends {b - a:.2f} s after it starts")
            continue
        start, dur = round(a, 3), round(b - a, 3)
        props = _event_props(p, i, e["type"], copy.deepcopy(e.get("props", {})), start, dur, offs, errors)
        ev = {"type": e["type"], "start": start, "duration": dur, "props": props, "index": i}
        if "name" in e:
            ev["name"] = e["name"]
        events.append(ev)
    sfx = []
    for i, x in enumerate(spec.get("sfx", [])):
        t = resolve(x["at"], f"sfx[{i}] ({x['name']})")
        if t is not None:
            sfx.append((x["name"], round(t, 3), float(x.get("gain_db", -15))))
    if offs[-1] > MAX_DURATION:
        errors.append(f"segments: {offs[-1]:.1f} s of output; the limit is {MAX_DURATION:.0f} s")
    if p.emphasis:
        try:
            p._emph_flags(p.output_words())
        except ValueError as e:
            errors.append(f"emphasis: {e}")
    if errors:
        raise SpecError(errors)
    p.events, p.sfx = events, sfx
    return p, {"edges": edges, "duration": round(offs[-1], 3), "warnings": warnings, "energy": energy}


def timeline(p: Project) -> list[str]:
    offs = p.offsets()
    rows = [f"{'#':>2} {'take':<10} {'in':>7} {'out':>7} {'at':>7}  {'zoom':<9} look  note"]
    for i, s in enumerate(p.segments):
        rows.append(f"{i:>2} {s.take:<10} {s.t_in:7.2f} {s.t_out:7.2f} {offs[i]:7.2f}  {s.zoom[0]:<9} "
                    f"{s.look or '-':<5} {s.note[:40]}")
    return rows


def check(spec_path: Path, root: Path | None = None) -> dict:
    """Validate and plan without rendering: errors, warnings, duration, timeline and edge report."""
    try:
        p, rep = load(spec_path, root)
    except SpecError as e:
        return {"errors": e.errors, "warnings": [], "duration": None, "timeline": [], "edges": []}
    warnings = rep["warnings"] + p.echo_check() + p.sfx_check()
    for e in p.events:
        if e["start"] + e["duration"] > rep["duration"] + 1e-6:
            warnings.append(f"event {e['type']} at {e['start']}s runs past the end ({rep['duration']:.2f}s)")
    return {"errors": [], "warnings": warnings, "duration": rep["duration"], "timeline": timeline(p),
            "edges": rep["edges"]}
