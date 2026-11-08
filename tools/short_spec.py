"""Data-only short-form spec: `edit/short.json` → the same `shortform.Project` a build.py makes.

    from short_spec import load, check
    p, report = load(Path("footage/demo/edit/short.json"))   # validated, edges refined, anchors resolved
    p.build(preview=True)
    res = check(Path("footage/demo/edit/short.json"))       # {"errors", "warnings", "duration", "timeline", "edges"}

Nothing in a spec is executed: every field is checked against a fixed shape, every file must sit inside
the project (or the shared assets/), grades are preset names, never filter strings. So a spec written by
someone untrusted is safe to check and render. Shape (all keys optional unless noted):

    {"version": 1, "brand": "none" | "<slug>",
     "sources": {"take1": {"file": "edit/conformed/take1.mov", "face": [540, 900],
                           "head": [380, 520, 760, 1000]}},   required; head optional (else edit/face.json)
     "segments": [{"take", "in" | "from", "out" | "to", "zoom": {"kind": "static", "scale": 1.0},
                   "look": null | "bw" | "low", "freeze_after": 0, "freeze": 0.4 (low only), "lock_in": false,
                   "lock_out": false, "repeat": false, "keep_restart": false, "note": ""}], required
     "captions": {"fixes": {"heard": "said"}, "word_fixes": [{"take", "at", "text"}],
                  "skip": [{"take", "at"}], "props": {}, "style": {}, "engine": "remotion" | "ass"},
     "emphasis": [{"take", "phrase", "after"}],
     "events": [{"type", "start": T, "end": T | "duration": s, "props": {}, "name",
                 "layer": "front" | "behind" | "panel", "object": "<id>"}],
     "camera": [{"kind": "push" | "pull" | "side" | "corner", "start": T, "end": T, "amount": 0.05 (push only)}],
     "sfx": [{"name", "at": T, "gain_db"}],
     "public_files": {"site/img-00.png": "edit/downloads/site/img-00.png"},
     "grade": null | "<preset>", "lufs": -14.0,
     "edges": {"above_floor": 9, "pre": 0.10, "post": 0.12, "min_sil": 0.06}}   refine_edges() settings

`edges.above_floor` 28 suits very low noise floors (iPhone voice isolation): see short-form-pro gotchas.

Cut by words: `"from": {"word", "after"?}` / `"to": {"word", "after"?}` instead of `in` / `out` seconds. The
edge goes in the pause before (`from`) or after (`to`) that word in the segment's take, or at the quietest
5 ms point between it and its neighbour when they run together. A segment given by both drops its inner
pauses of 0.30 s or more (dead air), keeping its zoom and look on every piece.

Timeline rules (errors): two segments of one take may not cover the same source time, before or after edge
refinement (it would play twice), unless the later one says `"repeat": true`. Contiguous cuts of one take
(the next in ≤ 0.6 s after an out) are joined at the quietest point between them. No edge, locked or not,
may sit inside a word (a lock only keeps an edge on sound between words), and an unlocked edge may not land
on sound louder than `above_floor` + 3 dB over the room tone (above `above_floor`, or on a locked edge, it is
a warning). An in-point at source time 0 is clean. A segment may not keep both halves of a false start the
transcript marks (`restarts`; `"keep_restart": true` makes it a warning), and keeping speech the transcript
lists as `untranscribed` is a warning.

Strict mode (`check(…, strict=True)`, `--strict`, job arg `"strict": true`) is for edits nobody reviews by
hand: `lock_in`, `lock_out` and `keep_restart` are errors, and every finding whose kind is in STRICT_KINDS
(the never-list, loud edges, text outside its card, cuts with no air) is an error instead of a warning. `NEVER_LIST` names them.

Zooms: static {scale} | push {from, to} | punch {base, peak, at} | outpunch {from, to, peak, at}, where a
punch's `at` is a SOURCE time in the segment's take: seconds, or {"word", "after"?, "edge"?, "offset"?}.
A time T (event start/end, sfx at) is OUTPUT seconds, or an anchor resolved after edge refinement:
    {"word": "launch", "take": "take1", "after": 12.0, "edge": "start" | "end", "offset": 0.2}
    {"seg": 2, "edge": "start" | "end", "offset": -0.1}

The camera moves the footage on the stage (no overlap; a `panel` event needs a `corner` move; no split screen).
`look: "low"` is the one low moment of a video (a static zoom, 1.0–3.0 s, optional `freeze` of 0.3–0.5 s). Events of
one component sharing an `object` id are one story object coming back; `check` lists where each appears.

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
from shortform import END_TAIL, LOOKS, REPO, SFX_DIR, Finding, Project, Seg, _norm

ASSETS = REPO / "assets"
BRANDS = REPO / "brands"
sys.path.insert(0, str(REPO / "vendor" / "video-use" / "helpers"))
try:
    from grade import PRESETS as _VU_PRESETS
except Exception:  # video-use not cloned: only the engine's own grades
    _VU_PRESETS = {}

DEFAULT_GRADE = Project.__dataclass_fields__["grade"].default
GRADES = {**_VU_PRESETS, "default": DEFAULT_GRADE, "none": ""}

MAX_DURATION, MAX_SEGMENTS, MAX_EVENTS, MAX_SFX, MAX_CAMERA = 180.0, 120, 200, 200, 40
TAKE_RE = re.compile(r"^[A-Za-z0-9][\w-]{0,63}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PUBLIC_RE = re.compile(r"^(?!.*\.\.)[\w-][\w./-]*$")
MEDIA_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
ZOOMS = {"static": ("scale",), "push": ("from", "to"), "punch": ("base", "peak", "at"),
         "outpunch": ("from", "to", "peak", "at")}
CAMERA_KINDS = ("push", "pull", "side", "corner")
MAX_PUSH = 0.08
LOW_LENGTH, LOW_FREEZE = (1.0, 3.0), (0.3, 0.5)
OBJECT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
# the props that make an event the same object again, per component
OBJECT_IDENTITY = {"DocCard": ("kicker", "title", "italic")}
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


# anti-patterns a viewer notices at once: (number, what, the finding kinds that check it)
NEVER_LIST = [
    (1, "text over the face", ("face",)),
    (2, "text unreadable against what is behind it", ("contrast",)),
    (3, "captions on top of overlay text", ("captions_on_text",)),
    (4, "text too small", ("small_text",)),
    (5, "a cut inside a word", ("in_word",)),
    (6, "a false start or untranscribed speech kept", ("restart", "untranscribed")),
    (7, "the same source audio twice", ("same_audio",)),
    (8, "a graphic echoing the words being spoken", ("echo",)),
    (9, "accent text on a fill it doesn't read on", ("contrast",)),
    (10, "`frame` given by hand", ("frame",)),
]
# finding kinds that are errors in strict mode: the never-list, loud edges and text that doesn't show
STRICT_KINDS = {k for _, _, kinds in NEVER_LIST for k in kinds} | {"loud_edge", "no_text", "hidden", "outside", "no_air"}


def strict_split(warnings: list[str]) -> tuple[list[str], list[str]]:
    """(errors, warnings): the warnings strict mode turns into errors, and the rest."""
    hard = [w for w in warnings if getattr(w, "kind", None) in STRICT_KINDS]
    return hard, [w for w in warnings if not any(w is h for h in hard)]


def never_list() -> list[str]:
    return [f"{n:>2}. {what}  [{', '.join(kinds)}]" for n, what, kinds in NEVER_LIST]


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
           "public_files", "grade", "lufs", "edges", "camera"}
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
            if not V.obj(s, w, {"file", "face", "head"}, {"file", "face"}):
                continue
            V.path(s["file"], f"{w}.file", root, ext=MEDIA_EXT)
            f = s["face"]
            if not (isinstance(f, list) and len(f) == 2 and all(_num(x) and 0 <= x <= 8192 for x in f)):
                V.err(f"{w}.face", "must be [x, y] in source pixels (run the face op for a suggestion)")
            hb = s.get("head")
            if hb is not None and not (isinstance(hb, list) and len(hb) == 4 and all(_num(x) and 0 <= x <= 8192 for x in hb)
                                       and hb[0] < hb[2] and hb[1] < hb[3]):
                V.err(f"{w}.head", "must be [x0, y0, x1, y1] in source pixels, or null (the face op measures it)")
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
            if not V.obj(s, w, {"take", "in", "out", "from", "to", "zoom", "look", "freeze_after", "freeze", "lock_in",
                                "lock_out", "note", "repeat", "keep_restart"}, {"take"}):
                continue
            if V.str_(s["take"], f"{w}.take") and s["take"] not in takes:
                V.err(f"{w}.take", f"unknown take {s['take']!r}")
            for sec, word in (("in", "from"), ("out", "to")):
                if sec in s and word in s:
                    V.err(w, f"give one of `{sec}` (seconds) or `{word}` (a word anchor), not both")
                elif sec not in s and word not in s:
                    V.err(w, f"missing field {sec!r} (or {word!r}, a word anchor)")
                elif sec in s:
                    V.num(s[sec], f"{w}.{sec}", 0)
                elif V.obj(s[word], f"{w}.{word}", {"word", "after"}, {"word"}):
                    V.str_(s[word]["word"], f"{w}.{word}.word")
                    if "after" in s[word]:
                        V.num(s[word]["after"], f"{w}.{word}.after", 0)
            if _num(s.get("in")) and _num(s.get("out")):
                if s["out"] - s["in"] < 0.1:
                    V.err(w, "`out` must be at least 0.1 s after `in`")
                planned += s["out"] - s["in"]
            if "freeze_after" in s and V.num(s["freeze_after"], f"{w}.freeze_after", 0, 5):
                planned += s["freeze_after"]
            if s.get("look") is not None:
                V.str_(s["look"], f"{w}.look", choices={k for k in LOOKS if k})
            if "freeze" in s:
                if s.get("look") != "low":
                    V.err(f"{w}.freeze", 'only a segment with "look": "low" takes `freeze`; use `freeze_after` for other holds')
                elif "freeze_after" in s:
                    V.err(w, "give one of `freeze` or `freeze_after`, not both")
                else:
                    V.num(s["freeze"], f"{w}.freeze", *LOW_FREEZE)
            for k in ("lock_in", "lock_out", "repeat", "keep_restart"):
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
        lows = [i for i, s in enumerate(segs) if isinstance(s, dict) and s.get("look") == "low"]
        if len(lows) > 1:
            V.err("segments", f"the low look is used at most once; segments {', '.join(map(str, lows))} all have it")
        for i in lows:
            z = segs[i].get("zoom")
            if isinstance(z, dict) and z.get("kind") != "static":
                V.err(f"segments[{i}].zoom", 'a "low" segment holds a static zoom')
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

    cam = spec.get("camera", [])
    if not isinstance(cam, list):
        V.err("camera", "must be a list")
    elif len(cam) > MAX_CAMERA:
        V.err("camera", f"{len(cam)} moves; the limit is {MAX_CAMERA}")
    else:
        for i, m in enumerate(cam):
            w = f"camera[{i}]"
            if not V.obj(m, w, {"kind", "start", "end", "amount"}, {"kind", "start", "end"}):
                continue
            if m.get("kind") == "split":
                V.err(f"{w}.kind", "split screen is not available (it cuts the speaker in half); "
                                   f"the kinds are {', '.join(CAMERA_KINDS)}")
            elif "kind" in m:
                V.str_(m["kind"], f"{w}.kind", choices=set(CAMERA_KINDS))
            for k in ("start", "end"):
                if k in m:
                    _check_time(V, m[k], f"{w}.{k}", takes, n_segs)
            if "amount" in m:
                if m.get("kind") != "push":
                    V.err(w, f"only a push takes `amount`, not {m.get('kind')!r}")
                else:
                    V.num(m["amount"], f"{w}.amount", 0.0, MAX_PUSH)

    events = spec.get("events", [])
    if not isinstance(events, list):
        V.err("events", "must be a list")
    elif len(events) > MAX_EVENTS:
        V.err("events", f"{len(events)} events; the limit is {MAX_EVENTS}")
    else:
        for i, e in enumerate(events):
            w = f"events[{i}]"
            if not V.obj(e, w, {"type", "start", "end", "duration", "props", "name", "layer", "object"}, {"type", "start"}):
                continue
            V.str_(e["type"], f"{w}.type", choices=OVERLAY_TYPES)
            if "layer" in e and V.str_(e["layer"], f"{w}.layer", choices=set(overlay_schema.LAYERS)) \
                    and e["type"] in OVERLAY_TYPES and e["layer"] not in overlay_schema.layers(e["type"]):
                V.err(f"{w}.layer", f"{e['type']} can't go on the {e['layer']!r} layer; it may use "
                                    f"{', '.join(overlay_schema.layers(e['type']))}")
            if "object" in e:
                V.str_(e["object"], f"{w}.object", OBJECT_RE)
            if e.get("layer") not in (None, "behind") and isinstance(e.get("props"), dict) and e["props"].get("behind"):
                V.err(w, f'`props.behind` puts the event under the speaker, but its layer is {e["layer"]!r}; drop one')
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


def _heads(spec: dict, root: Path, edit_dir: Path) -> dict[str, list[float]]:
    """Each take's head box: the spec's `head`, else the face step's (edit/face.json, keyed by file stem)."""
    try:
        faces = json.loads((edit_dir / "face.json").read_text())
    except (OSError, ValueError):
        faces = {}
    out = {}
    for take, s in spec["sources"].items():
        hb = s["head"] if "head" in s else (faces.get(Path(s["file"]).stem) or {}).get("head")
        if hb:
            out[take] = [float(x) for x in hb]
    return out


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


def _out_time(p: Project, t: Any, bounds: list[tuple[float, float]]) -> float:
    """Output seconds of a time; `bounds[i]` is spec segment i's (start, end) in the output."""
    if _num(t):
        return float(t)
    if "seg" in t:
        return bounds[t["seg"]][1 if t["edge"] == "end" else 0] + t.get("offset", 0.0)
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
            errors.append(Finding(f"{when}segments[{j}] ({b.take} {b.t_in:.2f}–{b.t_out:.2f}) overlaps segments[{i}] "
                                  f"({a.take} {a.t_in:.2f}–{a.t_out:.2f}) by {hi - lo:.2f} s: {said}; {fix}, "
                                  f'or set "repeat": true on segments[{j}] if the repeat is deliberate', "same_audio"))
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


HOP = 0.005
MIN_PAUSE = 0.06  # s: a quiet run this long is a pause
DEAD_AIR, MIN_SPLIT = 0.30, 0.08  # s: a word-anchored segment drops inner pauses this long, when that removes this much


def _core(w: dict) -> float:
    """How long a word's sound surely lasts: Whisper stretches stamps over the pauses around a word, so a
    stamp longer than its letters counts as 0.025 s per letter + 0.02 s."""
    return min(w["end"] - w["start"], 0.025 * sum(c.isalnum() for c in w["text"]) + 0.02)


def _core_end(w: dict) -> float:
    return w["start"] + _core(w)


def _runs(quiet, a: float, b: float, min_len: float = MIN_PAUSE) -> list[tuple[float, float]]:
    """Quiet runs (start, end) of at least `min_len` s that overlap [a, b], each at its full extent."""
    n = len(quiet)
    k, hi, out = max(0, int(a / HOP)), min(n, int(b / HOP) + 1), []
    while k < hi:
        if not quiet[k]:
            k += 1
            continue
        k0, j = k, k
        while k0 > 0 and quiet[k0 - 1]:
            k0 -= 1
        while j < n and quiet[j]:
            j += 1
        if (j - k0) * HOP >= min_len:
            out.append((k0 * HOP, j * HOP))
        k = j
    return out


def _quietest(p: Project, take: str, a: float, b: float) -> float:
    db, _ = p._env(take)
    lo, hi = max(0, int(round(a / HOP))), min(len(db), int(round(b / HOP)) + 1)
    return round((lo + int(db[lo:hi].argmin())) * HOP, 3) if hi > lo else round((a + b) / 2, 3)


def _gap(p: Project, take: str, words: list[dict], i: int, above_floor: float, pre: float,
         post: float) -> tuple[float, float, float] | None:
    """The pause between word i and word i + 1 (i = -1: before the first word; i = last: after it), measured in
    the audio: (out-point for word i, in-point for word i + 1, pause length), or None when the speech runs on.
    The window runs from word i's core to word i + 1's core (Whisper stamps stretch over pauses), the pause is
    the longest quiet run in it (short dips are inside words), followed past the window while it stays quiet."""
    quiet = p._quiet(take, above_floor)
    n = len(quiet)
    if i < 0:
        a, b = 0.0, words[0]["end"] - _core(words[0])
    else:
        a = _core_end(words[i])
        b = max(a, words[i + 1]["end"] - _core(words[i + 1])) if i + 1 < len(words) else min(a + 1.0, n * HOP)
    runs = _runs(quiet, a, b)  # each at its full extent: a pause goes on while the audio stays quiet
    if not runs:
        return None
    qs, qe = max(runs, key=lambda r: r[1] - r[0])
    if i >= 0:
        qs = max(qs, words[i]["start"])
    out_cut, in_cut = min(qs + post, qe), max(qe - pre, qs)
    # a click merged into the pause (room-noise flicker) may sit right at the cut: move each cut on through
    # the pause until the 30 ms the loud-edge check reads beside it is quiet
    db, thr, w = p._env(take)[0], p.silence_db(take, above_floor), round(0.03 / HOP)
    k, end = round(out_cut / HOP), round(qe / HOP) - w
    while k < end and db[max(0, k - w):k].max() >= thr:
        k += 1
    out_cut = k * HOP
    k, start = round(in_cut / HOP), round(qs / HOP) + w
    while k > start and db[k:k + w].max() >= thr:
        k -= 1
    in_cut = k * HOP
    if out_cut > in_cut:
        out_cut = in_cut = (qs + qe) / 2
    return round(out_cut, 3), round(in_cut, 3), round(qe - qs, 3)


def word_edge(p: Project, take: str, a: dict, edge: str, above_floor: float, pre: float = 0.10,
              post: float = 0.12) -> float:
    """Source seconds of a word-anchored edge: `in` in the pause before the word, `out` in the pause after it
    (`_gap`), with `pre` / `post` s of air; with no pause, the quietest 5 ms point between the word and its
    neighbour, never inside either. Raises ValueError if the word isn't there."""
    words = p._words(take)
    after = a.get("after", 0.0)
    k = next((i for i, w in enumerate(words) if w["start"] >= after - 0.01 and _norm(w["text"]) == _norm(a["word"])), None)
    if k is None:
        raise ValueError(f"word {a['word']!r} not found in {take} after {after:g}")
    i = k if edge == "out" else k - 1
    if g := _gap(p, take, words, i, above_floor, pre, post):
        return g[0] if edge == "out" else g[1]
    if i < 0:
        return 0.0 if words[0]["start"] <= 0.02 else _quietest(p, take, 0.0, words[0]["start"])
    if i + 1 >= len(words):
        return round(words[i]["end"], 3)
    x0, x1 = sorted((words[i]["end"], words[i + 1]["start"]))
    return _quietest(p, take, x0 - 0.02, x1 + 0.02)


def _pause_near(p: Project, take: str, t: float, edge: str, above_floor: float, reach: float = 3.0) -> float | None:
    """The nearest pause (≥ 60 ms of silence, Project._quiet) on the outward side of an edge: before an
    in-point, after an out-point; its end next to the speech the cut keeps, with a little air. None within
    `reach` s."""
    quiet = p._quiet(take, above_floor)
    hop, n = HOP, len(quiet)
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
        # refined and word-anchored edges sit in measured silence; joined ones at the quietest point
        if d["tag"] in ("joined", "anchored") or not (d["locked"] or d["tag"].startswith("WARN")):
            continue
        s = p.segments[d["seg"]]
        # inside a word's stamp and on sound: Whisper stamps words early, over the silence before them, and an
        # edge in that silence cuts nothing
        quiet = p._quiet(s.take, above_floor)
        k = int(d["t"] / HOP)
        silent = bool(quiet[max(0, k - 3):k + 3].all())
        w = None if silent else next((w for w in p._words(s.take) if w["start"] + 0.02 < d["t"] < w["end"] - 0.02), None)
        where = f"segments[{d['seg']}].{d['edge']} {d['t']:.2f}"
        if w:
            msg = f'{where} is inside "{_plain(w["text"])}" ({w["start"]:.2f}–{w["end"]:.2f}): use {w["start"]:.2f} or {w["end"]:.2f}'
            if _on_sound(p, s.take, w["start"], above_floor) and _on_sound(p, s.take, w["end"], above_floor):
                x = _pause_near(p, s.take, d["t"], d["edge"], above_floor)
                msg += (f"; both run into the next word with no pause, the nearest pause {'before' if d['edge'] == 'in' else 'after'}"
                        f" it is at {x:.2f}" if x is not None else "; both run into the next word with no pause")
            if d["locked"]:
                msg += "; a lock only keeps an edge on sound between words"
            errors.append(Finding(msg, "in_word"))  # locked or not: a cut word is never right
            in_word.add((d["seg"], d["edge"]))
        elif not d["locked"]:
            side = "before" if d["edge"] == "in" else "after"
            warnings.append(f"{where}: no silence {side} it within reach, so edge refinement left it where it is")
    by_edge = {(d["seg"], d["edge"]): d for d in details}
    for e in energy:
        take = p.segments[e["seg"]].take
        # the take's silence threshold over its floor: `above_floor`, or more where the speech sets it (a very
        # quiet room), so an edge placed in measured silence is never called loud
        quiet_db = p.silence_db(take, above_floor) - p._env(take)[1]
        for edge, db, verb in (("in", e["head_db"], "starts"), ("out", e["tail_db"], "ends")):
            d = by_edge[(e["seg"], edge)]
            if db <= quiet_db or (e["seg"], edge) in in_word or d["tag"] == "joined":
                continue
            if edge == "in" and d["t"] <= HOP:
                continue  # the media starts here: nothing precedes it to cut away
            where = f"segments[{e['seg']}].{edge} {d['t']:.2f}"
            word = "from" if edge == "in" else "to"
            if db > quiet_db + 3 and not d["locked"]:
                x = _pause_near(p, take, d["t"], edge, above_floor)
                near = f" (the nearest is at {x:.2f})" if x is not None else ""
                errors.append(Finding(f"{where} {verb} in the middle of sound: +{db:.1f} dB over the room tone; "
                                      f'move it into a pause{near}, or give the edge as "{word}": a word', "loud_edge"))
            elif d["locked"] and db > quiet_db + 3:
                warnings.append(Finding(f"{where} {verb} in the middle of sound: +{db:.1f} dB over the room tone "
                                        f"(locked)", "loud_edge"))
            else:
                warnings.append(Finding(f"{where} {verb} on a quiet sound, +{db:.1f} dB over the room tone "
                                        f"(a breath or the tail of a word?)", "loud_edge"))
    return errors, warnings, energy


def _air_rules(p: Project, details: list[dict], above_floor: float, pre: float, post: float) -> list[Finding]:
    """`no_air`: an edge whose silence (the quiet run it sits in, between the sound before and the sound after) is
    shorter than the refinement's own air: `pre` before an in-point, `post` after an out-point. Edges the video's
    start and end make (the tail handles the last out-point), joins, and edges on sound (`loud_edge`, `in_word`
    report those) are left out."""
    out = []
    last = len(p.segments) - 1
    for d in details:
        if d["tag"] == "joined" or (d["edge"] == "out" and d["seg"] == last) or (d["edge"] == "in" and d["t"] <= HOP):
            continue
        quiet = p._quiet(p.segments[d["seg"]].take, above_floor)
        k = min(len(quiet) - 1, int(d["t"] / HOP))
        if not quiet[k]:
            continue
        a, b = k, k
        while a > 0 and quiet[a - 1]:
            a -= 1
        while b + 1 < len(quiet) and quiet[b + 1]:
            b += 1
        air, need = (b + 1 - a) * HOP, post if d["edge"] == "out" else pre
        if air < need - 1e-9:
            where = f"segments[{d['seg']}].{d['edge']} {d['t']:.2f}"
            other = (f"the next sound starts at {(b + 1) * HOP:.2f}" if d["edge"] == "out"
                     else f"the sound before it ends at {a * HOP:.2f}")
            out.append(Finding(f"{where} has {air:.2f} s of silence {'after' if d['edge'] == 'out' else 'before'} the "
                               f"speech it keeps, under the {need:g} s of air a cut needs ({other})", "no_air"))
    return out


def _transcript(p: Project, take: str) -> dict:
    cache = p.__dict__.setdefault("_transcript_cache", {})
    if take not in cache:
        cache[take] = json.loads((p.edit_dir / "transcripts" / f"{take}.json").read_text())
    return cache[take]


def _kept_speech(p: Project, raw: list[dict], strict: bool) -> tuple[list[str], list[str]]:
    """(errors, warnings): segments that keep both halves of a marked false start, or speech with no words."""
    errors, warnings = [], []
    for i, (s, r) in enumerate(zip(p.segments, raw)):
        t = _transcript(p, s.take)
        for rs in t.get("restarts", []):
            (a, b), again = rs["abandoned"], rs["again"]
            if not (s.t_in < b - 0.05 and s.t_out > again + 0.05):
                continue
            fix = (f"start it at {again:.2f}" if s.t_in >= a - 0.3 else
                   f"end it at {a:.2f} and start a new segment at {again:.2f}")
            keep = "" if strict else ', or set "keep_restart": true if both are meant to play'
            msg = (f'segments[{i}] ({s.take} {s.t_in:.2f}–{s.t_out:.2f}) keeps a false start: "{rs["words"]}" '
                   f"({a:.2f}–{b:.2f}) and its restart at {again:.2f}; {fix}{keep}")
            (warnings if r.get("keep_restart") and not strict else errors).append(Finding(msg, "restart"))
        for a, b in t.get("untranscribed", []):
            if min(s.t_out, b) - max(s.t_in, a) > 0.05:
                warnings.append(Finding(f"segments[{i}] ({s.take} {s.t_in:.2f}–{s.t_out:.2f}) keeps {a:.2f}–{b:.2f}, "
                                        f"speech the transcript has no words for; listen to it, or cut around it",
                                        "untranscribed"))
    return errors, warnings


def _strict_findings(spec: dict, errors: list[str], warnings: list[str]) -> tuple[list[str], list[str]]:
    """Strict mode: locks and keep_restart refused, and every STRICT_KINDS warning made an error."""
    for i, s in enumerate(spec["segments"]):
        for k in ("lock_in", "lock_out"):
            if s.get(k):
                word = "from" if k == "lock_in" else "to"
                errors.append(Finding(f"segments[{i}].{k}: locks aren't accepted here; the edge must sit in a pause "
                                      f'or between words (give it as "{word}": a word)', "lock"))
        if s.get("keep_restart"):
            errors.append(Finding(f"segments[{i}].keep_restart: a false start can't be kept here; cut it out",
                                  "restart"))
    for i, e in enumerate(spec.get("events", [])):
        if "frame" in e.get("props", {}):
            errors.append(Finding(f"events[{i}].props.frame ({e['type']}): placing by hand isn't accepted here; drop "
                                  f"`frame` and the engine places a floating overlay above the speaker's head", "frame"))
    hard, warnings = strict_split(warnings)
    return errors + hard, warnings


def _split_dead_air(p: Project, raw: list[dict], above_floor: float, pre: float, post: float) -> list[int]:
    """Split every segment given by `from` and `to` at its inner pauses of DEAD_AIR s or more, keeping `post` s
    after the word before and `pre` s before the word after (only where that removes MIN_SPLIT s or more).
    Pieces keep the segment's zoom and look; the freeze stays on the last. Returns each piece's spec index."""
    segs, index = [], []
    for i, (s, r) in enumerate(zip(p.segments, raw)):
        cuts = []
        if "from" in r and "to" in r:
            words = p._words(s.take)
            inside = [k for k, w in enumerate(words) if s.t_in <= (w["start"] + w["end"]) / 2 <= s.t_out]
            for k in inside[:-1]:
                g = _gap(p, s.take, words, k, above_floor, pre, post)
                if g and g[2] >= DEAD_AIR and g[1] - g[0] >= MIN_SPLIT and s.t_in < g[0] and g[1] < s.t_out:
                    cuts.append(g[:2])
            merged: list[tuple[float, float]] = []  # a word stamped over a pause finds it from both sides
            for a, b in sorted(set(cuts)):
                if merged and a <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], b))
                elif a - (merged[-1][1] if merged else s.t_in) >= 0.1:  # never a piece under 0.1 s
                    merged.append((a, b))
            cuts = [c for c in merged if s.t_out - c[1] >= 0.1]
        if not cuts:
            segs.append(s)
            index.append(i)
            continue
        edges = [s.t_in] + [x for c in cuts for x in c] + [s.t_out]
        n = len(cuts) + 1
        for k in range(n):
            t0, t1 = edges[2 * k], edges[2 * k + 1]
            segs.append(Seg(s.take, t0, t1, _piece_zoom(s.zoom, s.t_in, s.t_out, t0, t1), s.look,
                            s.freeze_after if k == n - 1 else 0.0, s.note,
                            s.lock_in and k == 0, s.lock_out and k == n - 1,
                            anchored_in=k > 0 or s.anchored_in, anchored_out=k < n - 1 or s.anchored_out))
            index.append(i)
    p.segments = segs
    return index


def _piece_zoom(z: tuple, a: float, b: float, t0: float, t1: float) -> tuple:
    """A piece's share of its segment's zoom: a push continues across the pieces; a punch plays in the piece
    that holds its time, pieces before it hold the zoom it starts from and pieces after it hold its peak."""
    if z[0] == "push":
        f = lambda t: round(z[1] + (z[2] - z[1]) * (t - a) / max(1e-6, b - a), 4)  # noqa: E731
        return ("push", f(t0), f(t1))
    if z[0] in ("punch", "outpunch") and not t0 <= z[-1] <= t1:
        before, peak = (z[1], z[2]) if z[0] == "punch" else (z[2], z[3])
        return ("static", before if t1 < z[-1] else peak)
    return z


def _event_props(p: Project, i: int, type_: str, props: dict, start: float, dur: float,
                 bounds: list[tuple[float, float]], errors: list[str]) -> dict:
    """Props with every time prop resolved to seconds from the event's start (anchors → numbers), each
    checked to land inside the event, and every entrance checked to finish before the event ends."""
    where = f"events[{i}].props"
    bad: list[str] = []
    for path, v, parent, key in overlay_schema.time_fields(type_, props):
        if isinstance(v, dict):
            try:
                out = _out_time(p, v, bounds)
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


def _camera(raw: list[dict], resolve, errors: list[str], total: float) -> list[dict]:
    """Camera moves in output seconds, sorted by start; errors for a move that doesn't end after it starts,
    runs past the end, or overlaps another (moves are one at a time)."""
    moves = []
    for i, m in enumerate(raw):
        a, b = (resolve(m[k], f"camera[{i}].{k}") for k in ("start", "end"))
        if a is None or b is None:
            continue
        if b - a < 0.1:
            errors.append(f"camera[{i}] ({m['kind']}): ends {b - a:.2f} s after it starts; a move needs to end after it starts")
            continue
        if b > total + 1e-6:
            errors.append(f"camera[{i}] ({m['kind']}) {a:.2f}–{b:.2f}: runs past the end of the video ({total:.2f} s)")
            continue
        move = {"kind": m["kind"], "start": round(a, 3), "end": round(b, 3), "index": i}
        if "amount" in m:
            move["amount"] = float(m["amount"])
        moves.append(move)
    moves.sort(key=lambda m: m["start"])
    for j, b in enumerate(moves):
        for a in moves[:j]:
            lo, hi = max(a["start"], b["start"]), min(a["end"], b["end"])
            if hi - lo > 0.001:
                errors.append(f"camera[{a['index']}] ({a['kind']} {a['start']:.2f}–{a['end']:.2f}) and camera[{b['index']}] "
                              f"({b['kind']} {b['start']:.2f}–{b['end']:.2f}) overlap by {hi - lo:.2f} s; "
                              f"moves don't overlap: end one before the next starts")
    return moves


def _layer_rules(events: list[dict], camera: list[dict], errors: list[str]) -> None:
    """A `panel` event is only drawn while a `corner` move is on, so it must sit inside one."""
    corners = [m for m in camera if m["kind"] == "corner"]
    for e in events:
        if e["layer"] != "panel":
            continue
        a, b = e["start"], e["start"] + e["duration"]
        if not any(m["start"] - 0.05 <= a and b <= m["end"] + 0.05 for m in corners):
            errors.append(f"events[{e['index']}] ({e['type']}) {a:.2f}–{b:.2f}: a panel needs a `corner` move covering "
                          f"all of it; add one to `camera` (or use another layer)")


def _object_rules(events: list[dict], errors: list[str]) -> None:
    """Events sharing an `object` id are one component and agree on its identifying props."""
    by_id: dict[str, list[dict]] = {}
    for e in events:
        if "object" in e:
            by_id.setdefault(e["object"], []).append(e)
    for oid, group in by_id.items():
        first = group[0]
        for e in group[1:]:
            if e["type"] != first["type"]:
                errors.append(f'object "{oid}" is used by {first["type"]} (events[{first["index"]}]) and {e["type"]} '
                              f"(events[{e['index']}]); one object is one component")
                continue
            for k in OBJECT_IDENTITY.get(e["type"], ()):
                if first["props"].get(k) != e["props"].get(k):
                    errors.append(f'object "{oid}": events[{first["index"]}] and events[{e["index"]}] ({e["type"]}) differ in '
                                  f'{k} ({first["props"].get(k)!r} vs {e["props"].get(k)!r}); an object keeps '
                                  f'{", ".join(OBJECT_IDENTITY[e["type"]])} wherever it comes back')


def load(spec_path: Path, root: Path | None = None, strict: bool = False) -> tuple[Project, dict]:
    """Validated Project with edges placed (word anchors resolved, the rest refined) and every anchor
    resolved. `strict`: see the module doc. Raises SpecError(errors)."""
    spec_path = Path(spec_path).resolve()
    root = (root or project_root(spec_path)).resolve()
    edit_dir = spec_path.parent
    spec = _read(spec_path)
    if errors := validate(spec, root, edit_dir):
        raise SpecError(errors)
    caps = spec.get("captions", {})
    segs = []
    for s in spec["segments"]:
        segs.append(Seg(s["take"], float(s.get("in", 0.0)), float(s.get("out", 0.0)), ("static", 1.0), s.get("look"),
                        float(s.get("freeze_after", s.get("freeze", 0.0))), s.get("note", ""),
                        s.get("lock_in", False), s.get("lock_out", False),
                        anchored_in="from" in s, anchored_out="to" in s))
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
        head=_heads(spec, root, edit_dir),
    )
    if errors := p.source_errors():
        raise SpecError(errors)
    settings = spec.get("edges", {})
    above = settings.get("above_floor", 9.0)
    pre, post = settings.get("pre", 0.10), settings.get("post", 0.12)
    for i, (s, raw) in enumerate(zip(p.segments, spec["segments"])):
        for edge, key in (("in", "from"), ("out", "to")):
            if key in raw:
                try:
                    setattr(s, f"t_{edge}", word_edge(p, s.take, raw[key], edge, above, pre, post))
                except ValueError as e:
                    errors.append(f"segments[{i}].{key}: {e}")
        if not errors and s.t_out - s.t_in < 0.1:
            errors.append(f"segments[{i}]: its out ({s.t_out:.2f}) must be at least 0.1 s after its in ({s.t_in:.2f})")
    if errors:
        raise SpecError(errors)
    errors, reported = _overlaps(p, spec["segments"], refined=False)
    edges, details = p.refine_edges(**settings, joins=_joins(p), detail=True)
    errors += _overlaps(p, spec["segments"], refined=True, skip=reported)[0]
    edge_errors, warnings, energy = _edge_rules(p, details, above)
    errors += edge_errors
    warnings += _air_rules(p, details, above, pre, post)
    kept_errors, kept_warnings = _kept_speech(p, spec["segments"], strict)
    errors += kept_errors
    warnings += kept_warnings
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
        if s.look == "low" and not LOW_LENGTH[0] <= s.dur <= LOW_LENGTH[1]:
            errors.append(f'segments[{i}] has look "low" and lasts {s.dur:.2f} s; the low line is '
                          f"{LOW_LENGTH[0]:.1f}–{LOW_LENGTH[1]:.1f} s long")
    p.pieces = _split_dead_air(p, spec["segments"], above, pre, post)
    p.segments[-1].freeze_after = max(p.segments[-1].freeze_after, END_TAIL)  # the video never stops on a syllable
    offs = p.offsets()
    bounds = [(offs[p.pieces.index(i)], offs[len(p.pieces) - p.pieces[::-1].index(i)])
              for i in range(len(spec["segments"]))]

    def resolve(t: Any, where: str) -> float | None:
        try:
            return _out_time(p, t, bounds)
        except ValueError as e:  # word() / at(): not in the transcript, or cut out
            errors.append(f"{where}: {e}")
            return None

    events = []
    for i, e in enumerate(spec.get("events", [])):
        pr = e.get("props", {})
        if pr.get("full") and (pr.get("bg") == "dark") != bool(pr.get("dark")) and "bg" in pr:
            errors.append(f'events[{i}] ({e["type"]}): "bg": "{pr["bg"]}" draws on a {pr["bg"]} background, but its '
                          f'backdrop is {"dark" if pr.get("dark") else "light"}; set "dark": '
                          f'{"true" if pr["bg"] == "dark" else "false"} or drop "bg": "{pr["bg"]}"')
        a = resolve(e["start"], f"events[{i}] ({e['type']}) start")
        b = resolve(e["end"], f"events[{i}] ({e['type']}) end") if "end" in e else \
            (a + e["duration"] if a is not None else None)
        if a is None or b is None:
            continue
        if b - a < 0.05:
            errors.append(f"events[{i}] ({e['type']}): ends {b - a:.2f} s after it starts")
            continue
        start, dur = round(a, 3), round(b - a, 3)
        props = _event_props(p, i, e["type"], copy.deepcopy(e.get("props", {})), start, dur, bounds, errors)
        ev = {"type": e["type"], "start": start, "duration": dur, "props": props, "index": i,
              "layer": e.get("layer") or ("behind" if pr.get("behind") else "front")}
        if "object" in e:
            ev["object"] = e["object"]
        if "name" in e:
            ev["name"] = e["name"]
        events.append(ev)
    camera = _camera(spec.get("camera", []), resolve, errors, offs[-1])
    _layer_rules(events, camera, errors)
    _object_rules(events, errors)
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
    if strict:
        errors, warnings = _strict_findings(spec, errors, warnings)
    if errors:
        raise SpecError(errors)
    p.events, p.sfx, p.camera = events, sfx, camera
    return p, {"edges": edges, "duration": round(offs[-1], 3), "warnings": warnings, "energy": energy}


def timeline(p: Project) -> list[str]:
    """One row per segment; the pieces of a segment split at its dead air are numbered <segment>.<piece>."""
    offs = p.offsets()
    pieces = getattr(p, "pieces", None) or list(range(len(p.segments)))
    rows = [f"{'#':>4} {'take':<10} {'in':>7} {'out':>7} {'at':>7}  {'zoom':<9} look  note"]
    for i, s in enumerate(p.segments):
        n = pieces[i]
        label = f"{n}.{i - pieces.index(n)}" if pieces.count(n) > 1 else str(n)
        rows.append(f"{label:>4} {s.take:<10} {s.t_in:7.2f} {s.t_out:7.2f} {offs[i]:7.2f}  {s.zoom[0]:<9} "
                    f"{s.look or '-':<5} {s.note[:40]}")
    for m in p.camera:
        rows.append(f"camera {m['kind']:<7} {m['start']:.2f}–{m['end']:.2f}")
    objects: dict[str, list[dict]] = {}
    for e in p.events:
        if "object" in e:
            objects.setdefault(e["object"], []).append(e)
    for oid, group in objects.items():
        rows.append(f"object {oid}: {group[0]['type']} at {', '.join(f'{e['start']:.2f}' for e in group)}")
    return rows


def check(spec_path: Path, root: Path | None = None, strict: bool = False) -> dict:
    """Validate and plan without rendering: errors, warnings, duration, timeline and edge report."""
    try:
        p, rep = load(spec_path, root, strict)
    except SpecError as e:
        return {"errors": e.errors, "warnings": [], "duration": None, "timeline": [], "edges": []}
    warnings = rep["warnings"] + [Finding(w, "echo") for w in p.echo_check()] + p.sfx_check()
    for e in p.events:
        if e["start"] + e["duration"] > rep["duration"] + 1e-6:
            warnings.append(f"event {e['type']} at {e['start']}s runs past the end ({rep['duration']:.2f}s)")
    errors, warnings = strict_split(warnings) if strict else ([], warnings)
    return {"errors": errors, "warnings": warnings, "duration": rep["duration"] if not errors else None,
            "timeline": timeline(p), "edges": rep["edges"]}
