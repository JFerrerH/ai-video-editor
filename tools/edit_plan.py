"""Edit plans: the transcript as numbered sentences, and a compiler from a plan to `edit/short.json`.

    uv run tools/edit_plan.py ids   <project>              # F1, F2, … with take, start, duration and restart flags
    uv run tools/edit_plan.py build <project> [plan.json]  # edit/plan.json → edit/short.json, then check --strict
    uv run tools/edit_plan.py schema                       # the plan's JSON Schema

The author of the edit (a person or a Claude) decides which lines to keep and what each moment needs; the
compiler only executes that: cuts by word, the timing of every graphic from its word, layers, camera, sound
effects, caps and a pacing report. A plan names lines by sentence ID and word and contains no seconds
(`edit/plan.json`, version 1):

    {"version": 1, "brand": "none" | "<slug>",
     "keep": ["F1-F2", "F4"],                                    sentence IDs or ranges, in the order they play
     "hook": {"title": ["Line one", "Line two"], "emphasis": "two"},
     "beats": [{"at": "F4", "word": "thesis",                    the sentence, and the word it lands on (default: its first)
                "device": "DocCard", "props": {…},               a component (`overlay_schema` has every props schema)
                "layer": "front" | "behind" | "panel", "object": "<id>",   optional; defaults per device
                "camera": "push" | "pull" | "side" | "corner" | {"kind": "push", "amount": 0.06} | "none",
                "punch": true,                                   a punch-in on the word
                "until": "F5", "through": "word"}],              hold to the end of this sentence (default: `at`), or of
                                                                 this word in it (a long sentence); at most 6 s
     "low": {"at": "F10", "words": "it is too late"},            the one low moment: words of one kept sentence
     "cta": {"at": "F15", "word": "follow", "handle": "…", "kicker": "…"},
     "captions": {"fixes": {"Akme": "Acme"}},                    a misheard word and what was said, everywhere
     "assets": {"site/img-04.png": "edit/downloads/site/img-04.png"}}

A time prop of a device (an entrance, a stamp) is the word it lands on, `{"word": "stamp"}`, searched from the
beat's word to the end of its hold. Seconds are an error. The compiler never adds a device, a camera move or a
look the plan didn't ask for.
"""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import overlay_schema  # noqa: E402

SENT_GAP = 0.8                    # s: a pause this long ends a sentence
RESTART_GAP, RESTART_WIN, RESTART_FILLER = 0.3, 6.0, 2  # an opening said again right after a pause of 0.3 s (at most 2 words between): the first was abandoned
HOLD_MIN, HOLD_MAX = 1.5, 6.0     # s: a graphic is read at a glance, and holds a thought, never longer
NEXT_GAP = 0.05                   # s between one beat's end and the next one's start
CUE_MARGIN = 0.3                  # s the last entrance stays readable before the event ends
HOLD_FIXED = {"Flash": 0.3}       # s: a device that is over at once
HOOK_MIN, HOOK_MAX = 2.0, 3.0
PUNCH_MAX = 2                     # punch-ins besides the hook's
PUNCH_PEAK = 1.12
BREAK_GAP = 0.25                  # s of pause a punch-in's or the low line's cut needs on each side (else it cuts through a word)
SPLIT_GAP, MIN_PIECE = 0.65, 1.0  # a pause this long inside a run is a jump cut of its own (a new frame size); never a piece under 1 s
LOW_MAX, LOW_FROM = 3.0, 3.0      # the low line is at most 3 s and never in the hook
PACING_WARN, PACING_MAX = 5.0, 8.0  # s with no visual aid on screen: a warning, then a refusal (the references' median is ~5 s)
CUE_MIN = 0.05                    # s: the least an entrance may stay before its event ends when the margin doesn't fit
CAMERA = ("push", "pull", "side", "corner")
PUSH_DEFAULT = 0.06
FPS = 30

TIME_WORDS = {"start", "end", "duration", "time", "t", "seconds", "from", "to", "pre", "post", "offset"}

# per device: the layer and the camera move it comes with; PhonePanel's depend on its mode
DEFAULT_LAYER = {"BehindWord": "behind", "Gauge": "behind", "CodePanel": "behind"}
DEFAULT_CAMERA = {"BehindWord": "pull", "Stuck": "push", "CodePanel": "side"}
PHONE_PANEL = {"corner": ("panel", "corner"), "side": ("front", "side")}

# sound effects: (name, volume) per moment. One per visible, important change, nothing else.
SFX = {"hook": ("pop", 0.3), "corner": ("swipe", 0.3), "side": ("swipe", 0.3), "pull": ("whoosh_short", 0.35),
       "StageDrawer": ("thud", 0.6), "Gauge": ("stamp", 0.45), "Notice": ("chime", 0.25), "Stickers": ("pop", 0.3),
       "turn": ("whoosh", 0.45), "cta": ("click", 0.35), "Waitlist": ("click", 0.35)}
# the prop a device's sound lands on (else the beat's start)
SFX_PROP = {"StageDrawer": "shutAt", "Gauge": "slamAt", "Stickers": "items[0].at", "Waitlist": "submitAt"}
SFX_SUBSTITUTE = {"pop": ["tap", "click"], "swipe": ["whoosh_short"], "whoosh_short": ["swipe"], "thud": ["impact", "sub"],
                  "stamp": ["impact", "thud"], "chime": ["sparkle", "tick"], "click": ["tap", "tick"],
                  "whoosh": ["swipe", "whoosh_short"]}
ALWAYS_BANNED = {"pluck"}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


class PlanError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(errors[0] if errors else "invalid plan")
        self.errors = errors


# ── transcript → numbered sentences ─────────────────────────────────────────
def load_words(root: Path, order: list[str] | None = None) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """({take: words}, {take: the transcript's `restarts`}), takes in `order` (the rest after them), else in name
    order. The same order gives the same sentence IDs."""
    words, restarts = {}, {}
    rank = {take: n for n, take in enumerate(order or [])}
    for f in sorted((root / "edit" / "transcripts").glob("*.json"), key=lambda p: (rank.get(p.stem, len(rank)), p.stem)):
        d = json.loads(f.read_text())
        words[f.stem] = [w for w in d["words"] if w.get("type", "word") == "word" and w["text"].strip()]
        restarts[f.stem] = d.get("restarts") or []
    if not words:
        raise PlanError([f"no transcripts in {root / 'edit' / 'transcripts'}; run transcribe first"])
    return words, restarts


def sentences(words: dict[str, list[dict]], restarts: dict[str, list[dict]] | None = None) -> list[dict]:
    """Sentences F1…Fn across the takes. One ends on final punctuation or a pause of `SENT_GAP`, or where its own
    opening (two words) is said again after a pause: the first half was abandoned."""
    sents: list[dict] = []
    for take, ws in words.items():
        cur: list[int] = []
        for i, w in enumerate(ws):
            cur.append(i)
            t = w["text"].strip()
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            gap = nxt["start"] - w["end"] if nxt else 99
            again = (nxt is not None and len(cur) >= 2 and gap >= RESTART_GAP and i + 2 < len(ws)
                     and [norm(ws[cur[0]]["text"]), norm(ws[cur[1]]["text"])]
                     == [norm(nxt["text"]), norm(ws[i + 2]["text"])])
            if re.search(r"[.?!]$", t) or t.endswith(("…", "...")) or gap >= SENT_GAP or again:
                sents.append({"take": take, "a": cur[0], "b": cur[-1]})
                cur = []
        if cur:
            sents.append({"take": take, "a": cur[0], "b": cur[-1]})
    for k, s in enumerate(sents):
        ws = words[s["take"]]
        s["id"] = f"F{k + 1}"
        s["start"], s["end"] = ws[s["a"]]["start"], ws[s["b"]]["end"]
        s["dur"] = round(s["end"] - s["start"], 2)
        s["text"] = " ".join(ws[i]["text"].strip() for i in range(s["a"], s["b"] + 1))
    _mark_restarts(sents, words)
    for take, rs in (restarts or {}).items():  # the transcript's own marks, when the sentence split didn't see them
        for r in rs:
            a = next((s for s in sents if s["take"] == take and s["start"] - 0.05 <= r["abandoned"][0] <= s["end"]), None)
            b = next((s for s in sents if s["take"] == take and s["start"] - 0.05 <= r["again"] <= s["end"]), None)
            if a and b and a is not b and not a.get("restart_of"):
                a["restart_of"] = b["id"]
    return sents


def _mark_restarts(sents: list[dict], words: dict) -> None:
    for k, s in enumerate(sents):
        ws = words[s["take"]]
        last = ws[s["b"]]["text"].strip()
        gap = ws[s["b"] + 1]["start"] - ws[s["b"]]["end"] if s["b"] + 1 < len(ws) else 0
        abandoned = last.endswith(("…", "...")) or (gap >= RESTART_GAP and not re.search(r"[.?!]$", last))
        if not abandoned or s["b"] - s["a"] < 1:
            continue
        head = [norm(ws[i]["text"]) for i in (s["a"], s["a"] + 1)]
        for t in sents[k + 1:]:
            if t["take"] != s["take"] or t["start"] - s["end"] > RESTART_WIN or t["a"] - s["b"] - 1 > RESTART_FILLER:
                break
            tw = words[t["take"]]
            if t["b"] > t["a"] and [norm(tw[i]["text"]) for i in (t["a"], t["a"] + 1)] == head:
                s["restart_of"] = t["id"]
                break


def plan_ids(root: Path, order: list[str] | None = None) -> list[dict]:
    words, restarts = load_words(root, order)
    return [{"id": s["id"], "take": s["take"], "start": round(s["start"], 2), "dur": s["dur"], "text": s["text"],
             **({"restart_of": s["restart_of"]} if s.get("restart_of") else {})} for s in sentences(words, restarts)]


def print_ids(root: Path) -> None:
    for s in plan_ids(root):
        flag = f"  [false start: said again in {s['restart_of']}]" if s.get("restart_of") else ""
        print(f"{s['id']:>4} [{s['take']} {s['start']:.2f} +{s['dur']:.1f}s]{flag} {s['text']}")


# ── the plan's shape ────────────────────────────────────────────────────────
def plan_schema() -> dict:
    """JSON Schema of `edit/plan.json` (the checks that need the transcript are in `validate_plan`)."""
    sid = {"type": "string", "pattern": r"^F[1-9][0-9]*$", "description": "a sentence ID from `plan ids`"}
    camera = {"oneOf": [{"enum": [*CAMERA, "none"]},
                        {"type": "object", "additionalProperties": False, "required": ["kind"],
                         "properties": {"kind": {"enum": list(CAMERA)}, "amount": {"type": "number", "maximum": 0.08}}}]}
    return {
        "title": "plan", "type": "object", "additionalProperties": False, "required": ["keep"],
        "properties": {
            "version": {"const": 1},
            "brand": {"type": "string"},
            "keep": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": r"^F[1-9][0-9]*(-F[1-9][0-9]*)?$"},
                     "description": "sentence IDs or ranges, in the order they play"},
            "hook": {"type": "object", "additionalProperties": False, "required": ["title"],
                     "properties": {"title": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string"}},
                                    "emphasis": {"type": "string"}}},
            "beats": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["at"],
                "properties": {"at": sid, "word": {"type": "string"},
                               "device": {"enum": sorted(overlay_schema.COMPONENTS)}, "props": {"type": "object"},
                               "layer": {"enum": overlay_schema.LAYERS}, "object": {"type": "string"},
                               "camera": camera, "punch": {"type": "boolean"}, "until": sid,
                               "through": {"type": "string", "description": "the word the hold ends on, in `until`"}}}},
            "low": {"type": "object", "additionalProperties": False, "required": ["at", "words"],
                    "properties": {"at": sid, "words": {"type": "string"}}},
            "cta": {"type": "object", "additionalProperties": False, "required": ["at", "handle"],
                    "properties": {"at": sid, "word": {"type": "string"}, "handle": {"type": "string"},
                                   "kicker": {"type": "string"}}},
            "captions": {"type": "object", "additionalProperties": False, "required": ["fixes"],
                         "properties": {"fixes": {"type": "object", "additionalProperties": {"type": "string"},
                                                  "description": "a misheard word → what was said"}}},
            "assets": {"type": "object", "additionalProperties": {"type": "string"}},
        },
    }


def _ids(item: str, by_id: dict, where: str, errors: list[str]) -> list[str]:
    m = re.fullmatch(r"F([1-9][0-9]*)(?:-F([1-9][0-9]*))?", item) if isinstance(item, str) else None
    if not m:
        errors.append(f"{where}: {item!r} isn't a sentence ID (F4) or a range (F4-F7)")
        return []
    a, b = int(m[1]), int(m[2] or m[1])
    ids = [f"F{k}" for k in range(a, b + 1)]
    if b < a or any(i not in by_id for i in ids):
        errors.append(f"{where}: {item} isn't in the transcript (F1–F{len(by_id)})")
        return []
    return ids


def _find(words: dict, s: dict, word: str | None, start: int | None = None, stop: int | None = None) -> int | None:
    """Index in the take of the first word of `s` (from index `start`, up to `stop`) that reads like `word`."""
    ws = words[s["take"]]
    lo, hi = (s["a"] if start is None else start), (s["b"] if stop is None else stop)
    return next((i for i in range(lo, hi + 1) if norm(ws[i]["text"]) == norm(word)), None)


def _names_seconds(where: str, obj: Any, errors: list[str], skip: tuple = ()) -> None:
    for k, v in obj.items():
        if k in skip:
            continue
        if k in TIME_WORDS or (isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("amount",)):
            errors.append(f"{where}.{k}: plans don't use seconds; refer to a line by sentence ID and word "
                          f'(`"at": "F4", "word": "…"`)')


def validate_plan(plan: Any, sents: list[dict], words: dict) -> list[str]:
    """Every problem with a plan, each naming the field and the fix (empty = valid)."""
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan: must be a JSON object"]
    by_id = {s["id"]: s for s in sents}
    allowed = {"version", "brand", "keep", "hook", "beats", "low", "cta", "captions", "assets"}
    for k in sorted(set(plan) - allowed):
        hint = " (plans don't use seconds; use sentence IDs and words)" if k in TIME_WORDS | {"camera", "events", "segments"} else ""
        errors.append(f"plan.{k}: not a plan field{hint}; the fields are {', '.join(sorted(allowed))}")
    if plan.get("version", 1) != 1:
        errors.append("plan.version: must be 1")
    caps = plan.get("captions", {})
    fixes = caps.get("fixes") if isinstance(caps, dict) else None
    if "captions" in plan and (not isinstance(caps, dict) or set(caps) != {"fixes"} or not isinstance(fixes, dict)
                               or not all(isinstance(v, str) and v.strip() for v in fixes.values())):
        errors.append('plan.captions: must be {"fixes": {"heard": "said"}}, a misheard word and what was said')
    brand = plan.get("brand", "none")
    if not isinstance(brand, str) or (brand != "none" and not (REPO / "brands" / brand / "brand.json").exists()):
        errors.append(f"plan.brand: no brand kit brands/{brand}/; use \"none\" or a slug that exists")

    kept: list[str] = []
    keep = plan.get("keep")
    if not isinstance(keep, list) or not keep:
        errors.append("plan.keep: required: the sentence IDs that play, in order (F1, F3-F5, …)")
    else:
        for n, item in enumerate(keep):
            for sid in _ids(item, by_id, f"plan.keep[{n}]", errors):
                if sid in kept:
                    errors.append(f"plan.keep[{n}]: {sid} is kept twice; a line plays once")
                elif by_id[sid].get("restart_of"):
                    errors.append(f"plan.keep[{n}]: {sid} is a false start (said again in {by_id[sid]['restart_of']}): "
                                  f"keep {by_id[sid]['restart_of']} instead")
                else:
                    kept.append(sid)

    hook = plan.get("hook")
    if hook is not None:
        if not isinstance(hook, dict) or set(hook) - {"title", "emphasis"}:
            errors.append('plan.hook: must be {"title": ["line", …], "emphasis": "words in a line"}')
        elif not (isinstance(hook.get("title"), list) and hook["title"] and all(isinstance(t, str) for t in hook["title"])):
            errors.append("plan.hook.title: must be a list of text lines")
        elif hook.get("emphasis") and not any(hook["emphasis"] in t for t in hook["title"]):
            errors.append(f"plan.hook.emphasis: {hook['emphasis']!r} isn't in any title line")

    punches = 0
    for n, b in enumerate(plan.get("beats") or []):
        where = f"plan.beats[{n}]"
        if not isinstance(b, dict):
            errors.append(f"{where}: must be an object")
            continue
        _names_seconds(where, b, errors, skip=("props", "camera"))
        for k in sorted(set(b) - {"at", "word", "device", "props", "layer", "object", "camera", "punch", "until", "through"} - TIME_WORDS):
            errors.append(f"{where}.{k}: not a beat field; a beat has at, word, device, props, layer, object, camera, punch, until, through")
        sid = b.get("at")
        if sid not in by_id or sid not in kept:
            errors.append(f"{where}.at: {sid!r} " + ("isn't kept in plan.keep" if sid in by_id else "isn't a sentence ID"))
            continue
        until = b.get("until", sid)
        if until not in kept or int(until[1:]) < int(sid[1:]):
            errors.append(f"{where}.until: {until!r} must be a kept sentence at or after {sid}")
        if b.get("word") is not None and _find(words, by_id[sid], b["word"]) is None:
            errors.append(f"{where}.word: {b['word']!r} isn't in {sid} (\"{by_id[sid]['text']}\")")
        if b.get("through") is not None and until in by_id and _find(words, by_id[until], b["through"]) is None:
            errors.append(f"{where}.through: {b['through']!r} isn't in {until} (\"{by_id[until]['text']}\")")
        cam = b.get("camera")
        if cam is not None and cam != "none" and (cam if isinstance(cam, str) else (cam or {}).get("kind")) not in CAMERA:
            errors.append(f"{where}.camera: must be one of {', '.join(CAMERA)} (split screen isn't available), or \"none\"")
        if isinstance(cam, dict) and cam.get("amount", 0) > 0.08:
            errors.append(f"{where}.camera.amount: a push goes at most 0.08")
        dev = b.get("device")
        if not (dev or cam not in (None, "none") or b.get("punch")):
            errors.append(f"{where}: a beat needs a device, a camera move or a punch-in")
        if b.get("punch"):
            punches += 1
        if dev is not None:
            if dev not in overlay_schema.COMPONENTS:
                errors.append(f"{where}.device: unknown component {dev!r}; `uv run tools/overlay_schema.py --export` lists them")
            elif b.get("layer") and b["layer"] not in overlay_schema.layers(dev):
                errors.append(f"{where}.layer: {dev} goes on {', '.join(overlay_schema.layers(dev))}, not {b['layer']!r}")
            props = b.get("props", {})
            if not isinstance(props, dict):
                errors.append(f"{where}.props: must be an object")
            else:
                for path, v, _, _ in overlay_schema.time_fields(dev, props):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        errors.append(f'{where}.props.{path}: {v:g} s is a time; plans use the word it lands on: '
                                      f'`{{"word": "…"}}` (or leave it out for the default)')
                    elif not (isinstance(v, dict) and isinstance(v.get("word"), str) and set(v) <= {"word"}):
                        errors.append(f'{where}.props.{path}: a time is `{{"word": "…"}}`, the word it lands on')
        elif b.get("props") or b.get("layer") or b.get("object"):
            errors.append(f"{where}: props, layer and object belong to a device; this beat has none")
    if punches > PUNCH_MAX:
        errors.append(f"plan.beats: {punches} punch-ins; punch-ins are used at most {PUNCH_MAX} times besides the hook's")

    low = plan.get("low")
    if isinstance(low, list):
        errors.append(f"plan.low: {len(low)} low moments; the low look is used at most once")
    elif low is not None:
        if not isinstance(low, dict) or set(low) != {"at", "words"} or low.get("at") not in kept or not isinstance(low.get("words"), str):
            errors.append('plan.low: must be {"at": "<kept sentence>", "words": "the words of the line"}')
        else:
            span = _span(words, by_id[low["at"]], low["words"])
            ws = words[by_id[low["at"]]["take"]]
            if span is None:
                errors.append(f"plan.low.words: {low['words']!r} isn't in {low['at']} (\"{by_id[low['at']]['text']}\")")
            elif ws[span[1]]["end"] - ws[span[0]]["start"] > LOW_MAX:
                errors.append(f"plan.low: the line lasts {ws[span[1]]['end'] - ws[span[0]]['start']:.1f} s; the low line is "
                              f"at most {LOW_MAX:g} s: pick fewer words")

    cta = plan.get("cta")
    if cta is not None:
        if not isinstance(cta, dict) or set(cta) - {"at", "word", "handle", "kicker"} or cta.get("at") not in kept \
                or not isinstance(cta.get("handle"), str):
            errors.append('plan.cta: must be {"at": "<kept sentence>", "word": "…", "handle": "…", "kicker": "…"}')
        elif cta.get("word") and _find(words, by_id[cta["at"]], cta["word"]) is None:
            errors.append(f"plan.cta.word: {cta['word']!r} isn't in {cta['at']}")
    assets = plan.get("assets", {})
    if not isinstance(assets, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in assets.items()):
        errors.append("plan.assets: must map a public name to a file in the project")
    return errors


def _span(words: dict, s: dict, text: str) -> tuple[int, int] | None:
    """Word indexes (first, last) of the words `text` in sentence `s`."""
    toks = [norm(t) for t in text.split() if norm(t)]
    ws = words[s["take"]]
    for i in range(s["a"], s["b"] - len(toks) + 2):
        if toks and [norm(ws[i + j]["text"]) for j in range(len(toks))] == toks:
            return i, i + len(toks) - 1
    return None


# ── brand sound bans ────────────────────────────────────────────────────────
def rejected_sfx(brand: str, repo: Path = REPO) -> set[str]:
    """Every effect the brand kit's notes reject: a "Rejected" line bans all it names except after "use"/"instead"
    (the replacement); "never" / "don't" clauses ban what follows them. A hard rule."""
    md = repo / "brands" / brand / "brand.md"
    if brand == "none" or not md.exists():
        return set()
    names = {p.stem for p in (repo / "assets" / "sfx" / "synth").glob("*.wav")}
    out: set[str] = set()
    for line in md.read_text().splitlines():
        whole = re.search(r"rejected", line, re.I)
        for clause in re.split(r"[.;]", line):
            if m := re.search(r"never|don't|nunca", clause, re.I):  # what follows, up to a replacement
                banned = re.split(r"\b(?:instead|en su lugar)\b", clause[m.end():], flags=re.I)[0]
            elif whole:
                banned = re.split(r"\b(?:use|usar|instead|en su lugar)\b", clause, flags=re.I)[0]
            else:
                continue
            out |= {n for n in names if re.search(rf"`{n}`|\b{n}\b", banned)}
    return out


# ── compile ─────────────────────────────────────────────────────────────────
def _anchor(take: str, w: dict) -> dict:
    return {"word": w["text"].strip(), "take": take, "after": round(max(0.0, w["start"] - 0.01), 2)}


def _src_anchor(w: dict) -> dict:
    return {"word": w["text"].strip(), "after": round(max(0.0, w["start"] - 0.01), 2)}


def _runs(story: list[dict]) -> list[dict]:
    runs: list[dict] = []
    for s in story:
        last = runs[-1] if runs else None
        if last and last["take"] == s["take"] and last["b"] + 1 == s["a"]:
            last["b"], last["ids"] = s["b"], last["ids"] + [s["id"]]
        else:
            runs.append({"take": s["take"], "a": s["a"], "b": s["b"], "ids": [s["id"]]})
    return runs


def _sources(root: Path, takes: list[str], errors: list[str]) -> dict:
    conform_f = root / "edit" / "conformed" / "conform.json"
    conform = json.loads(conform_f.read_text()) if conform_f.exists() else {}
    try:
        faces = json.loads((root / "edit" / "face.json").read_text())
    except (OSError, ValueError):
        faces = {}
    out = {}
    for take in takes:
        info = conform.get("takes", {}).get(take)
        f = info["output"] if info and info.get("as_is") else f"edit/conformed/{take}.mov"
        face = (faces.get(Path(f).stem) or faces.get(take) or {}).get("face")
        if not face:
            errors.append(f"sources: no face centre for {take}; run the `face` step first (edit/face.json)")
            continue
        out[take] = {"file": f, "face": [round(face[0]), round(face[1])]}
    return out


def _zoom_plan(segs: list[dict], punch_at: dict[int, dict], low_seg: int | None) -> None:
    """Jump cuts change the frame size (1.08 / 1.0 in turn); a long cut pushes in slowly; a punch-in lands on its word;
    the low line holds still."""
    prev = None  # the previous cut's static scale, None after any other zoom
    for k, g in enumerate(segs):
        scale = None
        if k == low_seg:
            g["zoom"], scale = {"kind": "static", "scale": 1.0}, 1.0
        elif k in punch_at:
            g["zoom"] = {"kind": "punch", "base": 1.0, "peak": PUNCH_PEAK, "at": punch_at[k]}
        elif g["_dur"] > 6.0 or (prev is not None and g["_dur"] > 4.0):
            g["zoom"] = {"kind": "push", "from": 1.0, "to": 1.06}
        else:
            scale = 1.0 if prev == 1.08 else 1.08
            g["zoom"] = {"kind": "static", "scale": scale}
        prev = scale


def build(root: Path, plan: Any, repo: Path = REPO, stills: bool = True, order: list[str] | None = None) -> dict:
    """Compile `plan` into `<root>/edit/short.json` and check it with --strict. Raises PlanError for a plan the
    compiler refuses. Returns {"spec", "errors", "warnings", "duration", "pacing", "timeline", "beats"}; the spec
    is written only when `check --strict` and, unless `stills` is false, `stills --strict` pass: the stills measure
    what `check` can't (text contrast on the real frame, text over the face, tiny text), and are left in edit/stills
    to read."""
    import short_spec as SS

    words, restarts = load_words(root, order)
    sents = sentences(words, restarts)
    if errs := validate_plan(plan, sents, words):
        raise PlanError(errs)
    by_id = {s["id"]: s for s in sents}
    kept = [i for item in plan["keep"] for i in _ids(item, by_id, "keep", [])]
    story = [by_id[i] for i in kept]
    errors: list[str] = []

    # segments: kept runs, the low line split out of its run
    low = plan.get("low")
    low_ids = None
    if low:
        ls = by_id[low["at"]]
        low_ids = _span(words, ls, low["words"])
    # a zoom belongs to a cut, so a punch-in's sentence is a cut of its own (the audio runs on through the join)
    breaks: dict[str, set[int]] = {}
    for b in plan.get("beats") or []:
        if b.get("punch"):
            s = by_id[b["at"]]
            breaks.setdefault(s["take"], set()).update({s["a"], s["b"] + 1})
    if low_ids:
        breaks.setdefault(by_id[low["at"]]["take"], set()).update({low_ids[0], low_ids[1] + 1})
    for take, xs in breaks.items():  # a cut made for the plan must fall in a pause
        ws = words[take]
        for x in sorted(xs):
            inside = any(r["take"] == take and r["a"] < x <= r["b"] for r in _runs(story))
            if inside and 0 < x < len(ws) and ws[x]["start"] - ws[x - 1]["end"] < BREAK_GAP:
                what = "the low line" if low_ids and x in (low_ids[0], low_ids[1] + 1) else "a punch-in"
                errors.append(f"{what} would cut between \"{ws[x - 1]['text'].strip()}\" and \"{ws[x]['text'].strip()}\", which run "
                              f"together ({ws[x]['start'] - ws[x - 1]['end']:.2f} s); a cut needs a pause of {BREAK_GAP:g} s: "
                              f"{'pick other words' if what == 'the low line' else 'punch in on a sentence that follows a pause'}")
    if errors:
        raise PlanError(errors)
    segs: list[dict] = []   # {take, a, b, low}
    for r in _runs(story):
        ws = words[r["take"]]
        cuts = sorted({r["a"], r["b"] + 1} | {x for x in breaks.get(r["take"], ()) if r["a"] < x <= r["b"]})
        for x in range(r["a"] + 1, r["b"] + 1):  # long pauses inside the run, when both sides stay long enough
            if ws[x]["start"] - ws[x - 1]["end"] >= SPLIT_GAP and x not in cuts:
                before = max((c for c in cuts if c < x), default=r["a"])
                after = min((c for c in cuts if c > x), default=r["b"] + 1)
                if ws[x - 1]["end"] - ws[before]["start"] >= MIN_PIECE and ws[after - 1]["end"] - ws[x]["start"] >= MIN_PIECE:
                    cuts = sorted(cuts + [x])
        for a, nxt in zip(cuts, cuts[1:]):
            is_low = bool(low_ids) and r["take"] == by_id[low["at"]]["take"] and (a, nxt - 1) == low_ids
            segs.append({"take": r["take"], "a": a, "b": nxt - 1, "low": is_low})
    spec_segs = []
    for g in segs:
        ws = words[g["take"]]
        spec_segs.append({"take": g["take"], "from": _src_anchor(ws[g["a"]]), "to": _src_anchor(ws[g["b"]]),
                          "note": f"{g['a']}-{g['b']}", **({"look": "low"} if g["low"] else {})})
    seg_of = lambda take, i: next(k for k, g in enumerate(segs) if g["take"] == take and g["a"] <= i <= g["b"])  # noqa: E731
    sources = _sources(root, sorted({g["take"] for g in segs}), errors)
    if errors:
        raise PlanError(errors)
    edit = root / "edit"

    def load(spec: dict, name: str, strict: bool = False):
        path = edit / name
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
        try:
            return SS.load(path, root, strict=strict)
        except SS.SpecError as e:
            raise PlanError([_cut_hint(m) for m in e.errors]) from None
        finally:
            path.unlink(missing_ok=True)

    # pass 1: the cut alone, to know when every word plays
    for g, s in zip(segs, spec_segs):
        g["_dur"] = 0.0
    base = {"version": 1, "brand": plan.get("brand", "none"), "sources": sources, "segments": spec_segs}
    p, _ = load(base, ".plan-cut.json")
    offs = p.offsets()
    total = offs[-1]

    def out_t(take: str, t: float) -> float:
        return p.at(take, t)

    # where each spec segment plays in the output (the engine may split one at its dead air into several pieces)
    pieces = list(p.pieces)
    bounds = [(offs[pieces.index(k)], offs[len(pieces) - pieces[::-1].index(k)]) for k in range(len(segs))]
    for g, (a, b) in zip(segs, bounds):
        g["_dur"] = b - a

    def first_in_seg(take: str, i: int) -> int | None:
        k = seg_of(take, i)
        return k if segs[k]["a"] == i else None

    # beats in the order they play
    beats = []
    for n, b in enumerate(plan.get("beats") or []):
        s = by_id[b["at"]]
        i = _find(words, s, b["word"]) if b.get("word") else s["a"]
        w = words[s["take"]][i]
        k0 = first_in_seg(s["take"], i)
        try:  # the first word of a cut is stamped early, in the silence before it: it plays where its segment starts
            st = bounds[k0][0] if k0 is not None else out_t(s["take"], w["start"])
        except ValueError:
            errors.append(f"plan.beats[{n}]: {b['at']} \"{w['text'].strip()}\" is cut out of the video")
            continue
        until = by_id[b.get("until", b["at"])]
        last = until["b"]
        if b.get("through"):  # the word the hold ends on, after the beat's own word when they share a sentence
            j = _find(words, until, b["through"], i if until is s else None)
            last = j if j is not None else last
        try:
            hold = out_t(until["take"], words[until["take"]][last]["end"])
        except ValueError:
            hold = st + HOLD_MIN
        beats.append({"n": n, "b": b, "s": s, "i": i, "w": w, "st": st, "hold": hold, "seg0": k0,
                      "label": f"beat {n} ({b['at']} \"{w['text'].strip()}\"" + (f", {b['device']}" if b.get("device") else "") + ")"})
    timed = sorted((x for x in beats if x["b"].get("device") or x["b"].get("camera") not in (None, "none")),
                   key=lambda x: x["st"])
    for x, y in zip(timed, timed[1:]):
        if y["st"] - x["st"] < 0.3:
            errors.append(f"{x['label']} and {y['label']} start within 0.3 s of each other; a beat needs its own moment: "
                          f"put them on different words")
    if errors:
        raise PlanError(errors)

    banned = rejected_sfx(plan.get("brand", "none"), repo) | ALWAYS_BANNED
    sfx: list[dict] = []

    def add_sfx(kind: str, at: Any) -> None:
        name, vol = SFX[kind]
        if name in banned:
            name = next((a for a in SFX_SUBSTITUTE.get(name, []) if a not in banned), None)
        if name:
            sfx.append({"name": name, "at": at, "gain_db": round(20 * math.log10(vol), 1)})

    events: list[dict] = []
    camera: list[dict] = []
    event_beat: dict[int, int] = {}
    cue_words: dict[int, dict] = {}

    cta_st = None  # the CTA's card takes over the space: a graphic before it ends in time
    if plan.get("cta"):
        cs = by_id[plan["cta"]["at"]]
        ci = _find(words, cs, plan["cta"]["word"]) if plan["cta"].get("word") else cs["a"]
        ck = first_in_seg(cs["take"], ci)
        cta_st = bounds[ck][0] if ck is not None else out_t(cs["take"], words[cs["take"]][ci]["start"])

    for j, x in enumerate(timed):
        b, s, w, st = x["b"], x["s"], x["w"], x["st"]
        take = s["take"]
        dev = b.get("device")
        nxt = timed[j + 1]["st"] - NEXT_GAP if j + 1 < len(timed) else total
        if cta_st is not None and cta_st > st:
            nxt = min(nxt, cta_st - NEXT_GAP)
        limit = min(nxt, total, st + HOLD_MAX)
        dur = HOLD_FIXED[dev] if dev in HOLD_FIXED else min(max(x["hold"] - st, HOLD_MIN), HOLD_MAX)
        dur = min(dur, nxt - st)
        layer = b.get("layer")
        cam = b.get("camera")
        props: dict = {}
        if dev:
            props = json.loads(json.dumps(b.get("props", {})))
            mode = props.get("mode")
            if dev == "PhonePanel" and mode in PHONE_PANEL:
                layer = layer or PHONE_PANEL[mode][0]
                cam = PHONE_PANEL[mode][1] if cam is None else cam
            layer = layer or DEFAULT_LAYER.get(dev, "front")
            if cam is None:
                cam = DEFAULT_CAMERA.get(dev)
            # time props: the word each lands on, in the beat's own words, from its word on
            until_s = by_id[b.get("until", b["at"])]
            stop = until_s["b"] if until_s["take"] == take else s["b"]
            for path, v, parent, key in overlay_schema.time_fields(dev, props):
                i = _find(words, s, v["word"], x["i"], stop)
                if i is None:
                    errors.append(f"{x['label']}.props.{path}: the word {v['word']!r} isn't between "
                                  f"\"{w['text'].strip()}\" and the end of the hold")
                    continue
                parent[key] = _anchor(take, words[take][i])
        kind = cam if isinstance(cam, str) else (cam or {}).get("kind")
        if dev:
            events.append({"type": dev, "start": _anchor(take, w) if x["seg0"] is None else {"seg": x["seg0"], "edge": "start"},
                           "duration": 0.0, "props": props, "layer": layer, "name": f"beat {x['n']}",
                           **({"object": b["object"]} if b.get("object") else {})})
            event_beat[len(events) - 1] = x["n"]
        if dev:
            _fill_array_cues(dev, props, max(dur, HOLD_MIN))
        # entrances must have finished before the beat ends: make the hold long enough, or say what doesn't fit
        need = 0.0
        if dev:
            numeric = json.loads(json.dumps(props))
            for path, v, parent, key in overlay_schema.time_fields(dev, numeric):
                try:
                    parent[key] = max(0.0, out_t(take, _word_at(words[take], v["after"], v["word"]) ) - st)
                except (ValueError, TypeError, StopIteration):
                    parent[key] = 0.0
            ends = [e for _, _, e in overlay_schema.cue_finish(dev, numeric, FPS, max(dur, HOLD_MAX))]
            need = max(ends, default=0.0) + CUE_MARGIN
        if need > dur:
            dur = min(need, limit - st)
        if dev and need - CUE_MARGIN + CUE_MIN > dur + 0.03:  # the margin yields to the room there is; the entrances don't
            errors.append(f"{x['label']}: its entrances need {need - CUE_MARGIN:.2f} s, but only {dur:.2f} s fit before "
                          f"{'the next beat' if limit == nxt else 'the end of the video'}; start this beat on an earlier "
                          f"word, use fewer items, or move the next beat")
        if dur < min(0.5, HOLD_FIXED.get(dev, 0.5)):
            errors.append(f"{x['label']}: only {dur:.1f} s fit before the next beat or the end of the video")
        dur = round(dur, 2)
        if dev:
            events[-1]["duration"] = dur
            if "Waitlist" == dev or dev in SFX_PROP:
                prop = SFX_PROP.get(dev)
                cue = _get_path(props, prop) if prop else None
                if dev == "Stickers" and not props.get("items"):
                    cue = None
                add_sfx("Waitlist" if dev == "Waitlist" else dev, cue if isinstance(cue, dict) else events[-1]["start"])
            elif dev in SFX:
                add_sfx(dev, events[-1]["start"])
        if kind and kind != "none":
            amount = (cam.get("amount") if isinstance(cam, dict) else None) or PUSH_DEFAULT
            camera.append({"kind": kind, "start": _anchor(take, w) if x["seg0"] is None else {"seg": x["seg0"], "edge": "start"},
                           "end": round(st + dur, 3), **({"amount": amount} if kind == "push" else {})})
            if kind in SFX:
                add_sfx(kind, camera[-1]["start"])
        x["dur"] = dur
    if errors:
        raise PlanError(errors)

    # hook, punch-ins, low
    punch_at: dict[int, dict] = {}
    for x in beats:
        if x["b"].get("punch"):
            k = seg_of(x["s"]["take"], x["i"])
            if k in punch_at:
                errors.append(f"{x['label']}: segment {k} already has a punch-in; one per cut")
            punch_at[k] = _src_anchor(x["w"])
    hook = plan.get("hook")
    if hook:
        mid = (segs[0]["a"] + segs[0]["b"]) // 2
        if 0 not in punch_at:
            punch_at[0] = _src_anchor(words[segs[0]["take"]][mid])
        lines = [{"text": t, **({"emphasis": hook["emphasis"]} if hook.get("emphasis") and hook["emphasis"] in t else {})}
                 for t in hook["title"]]
        # the hook gives way to the first graphic: two cards never share the space above the head
        first = min((x["st"] for x in beats if x["b"].get("device") and x["b"]["device"] not in HOLD_FIXED
                     and not x["b"].get("props", {}).get("full")), default=HOOK_MAX)
        events.insert(0, {"type": "HookTitle", "start": 0, "layer": "front", "name": "hook",
                          "duration": round(max(HOLD_MIN, min(HOOK_MAX, max(HOOK_MIN, segs[0]["_dur"]), first - NEXT_GAP)), 2),
                          "props": {"lines": lines}})
        event_beat = {i + 1: n for i, n in event_beat.items()}
        add_sfx("hook", 0.06)
    low_seg = next((k for k, g in enumerate(segs) if g["low"]), None)
    if low:
        ws = words[segs[low_seg]["take"]]
        t0 = out_t(segs[low_seg]["take"], ws[segs[low_seg]["a"]]["start"])
        if t0 < LOW_FROM:
            errors.append(f"plan.low: the line starts at {t0:.1f} s, over the hook; the low moment comes after the first "
                          f"{LOW_FROM:g} s")
        if low_seg + 1 < len(segs):
            add_sfx("turn", {"seg": low_seg + 1, "edge": "start"})
    cta = plan.get("cta")
    if cta:
        s = by_id[cta["at"]]
        i = _find(words, s, cta["word"]) if cta.get("word") else s["a"]
        k0 = first_in_seg(s["take"], i)
        start = _anchor(s["take"], words[s["take"]][i]) if k0 is None else {"seg": k0, "edge": "start"}
        later = [x["st"] for x in timed if x["b"].get("device") and x["b"]["device"] not in HOLD_FIXED and x["st"] > cta_st]
        until = {"duration": round(max(HOLD_MIN, min(later) - NEXT_GAP - cta_st), 2)} if later \
            else {"end": {"seg": len(spec_segs) - 1, "edge": "end"}}  # the next graphic takes over, or it holds to the end
        events.append({"type": "HandleCard", "start": start, **until,
                       "layer": "front", "name": "cta",
                       "props": {"handle": cta["handle"], **({"kicker": cta["kicker"]} if cta.get("kicker") else {})}})
        add_sfx("cta", start)
    if errors:
        raise PlanError(errors)
    _zoom_plan(segs, punch_at, low_seg)
    for g, sp in zip(segs, spec_segs):
        sp["zoom"] = g["zoom"]
        if g["low"]:
            sp["zoom"] = {"kind": "static", "scale": 1.0}

    spec = {**base, "events": events, "camera": camera, "sfx": sfx,
            "public_files": plan.get("assets", {}), **({"captions": plan["captions"]} if plan.get("captions") else {})}
    spec_path = edit / "short.json"
    tmp = edit / ".plan-short.json"
    tmp.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    try:
        res = SS.check(tmp, root, strict=True)
        res["errors"] = [_beat_name(e, event_beat, plan) for e in res["errors"]]
        pacing = {}
        if not res["errors"]:
            p2, rep = SS.load(tmp, root, strict=True)
            pacing = _pacing(p2, rep["duration"])
            if pacing.get("error"):
                res["errors"].append(pacing["error"])
            res["errors"] += _shared_screen(p2)
            if stills:
                found = list(rep["warnings"])
                p2.stills(None, preview=True, warnings=found)
                hard, _ = SS.strict_split(found)
                res["errors"] += [_beat_name(str(w), event_beat, plan) for w in hard]
            if not res["errors"]:
                tmp.replace(spec_path)
    finally:
        tmp.unlink(missing_ok=True)
    res["warnings"] = [str(w) for w in res["warnings"]]
    if pacing.get("warning"):
        res["warnings"].append(pacing["warning"])
    return {"spec": "edit/short.json" if not res["errors"] else None, "stills": "edit/stills" if stills and pacing else None, "errors": res["errors"], "warnings": res["warnings"],
            "duration": res["duration"], "pacing": pacing, "timeline": res["timeline"], "beats": len(beats)}


def _fill_array_cues(dev: str, props: dict, hold: float) -> None:
    """Entrances in a list (screens, items) the plan left without a time come one after another, evenly, in the first
    half of the hold: the plan names the words that matter, the compiler does not make the author count seconds."""
    for cue in overlay_schema.schema(dev).get("x-cues", []):
        arr, sep, field = cue["path"].partition("[]")
        field = field.lstrip(".")
        items = props.get(arr) if sep else None
        if not (isinstance(items, list) and field and "default" not in cue):
            continue
        step = min(1.2, max(0.3, hold * 0.5 / max(1, len(items))))
        for i, it in enumerate(items):
            if isinstance(it, dict) and field not in it:
                it[field] = round(i * step, 2)


def _word_at(ws: list[dict], after: float, text: str) -> float:
    return next(w["start"] for w in ws if w["start"] >= after - 0.01 and norm(w["text"]) == norm(text))


def _get_path(props: dict, path: str | None) -> Any:
    if not path:
        return None
    cur: Any = props
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        try:
            cur = cur[int(part[1:-1])] if part.startswith("[") else cur[part]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def _beat_name(msg: str, event_beat: dict[int, int], plan: dict) -> str:
    if "missing required field" in msg:
        msg += (' — name the word it lands on as `{"word": "…"}` if it is a time, or give the value'
                if re.search(r"(At|at)\b", msg.split(" (")[0]) else "")
    return re.sub(r"events\[(\d+)\]", lambda m: f"beat {event_beat[int(m[1])]}" if int(m[1]) in event_beat
                  else {"0": "events[0]"}.get(m[1], m[0]), msg)


def _cut_hint(msg: str) -> str:
    if "no pause" in msg or "run together" in msg:
        return msg + " (keep the neighbouring sentence too, or start/end at another sentence)"
    if "middle of sound" in msg and msg.startswith("segments["):
        return (msg + " (a cut made for the plan: the `low` line, a punch-in sentence or a kept run must begin and end at a "
                "pause; pick words that follow one, or keep the neighbouring sentence)")
    return msg


def _shared_screen(p: Any) -> list[str]:
    """Two graphics on screen at once, one over the other. A Flash is over at once; a full-screen scene covers the rest."""
    shown = sorted((e for e in p.events if e["type"] not in ("Captions", *HOLD_FIXED) and not e.get("props", {}).get("full")),
                   key=lambda e: e["start"])
    out = []
    for a, b in zip(shown, shown[1:]):
        over = a["start"] + a["duration"] - b["start"]
        if over > NEXT_GAP:
            out.append(f"{a['type']} and {b['type']} are both on screen for {over:.2f} s from {b['start']:.2f} s, one over the "
                       f"other; start the second on a later word, or end the first sooner with `through`")
    return out


def _pacing(p: Any, total: float) -> dict:
    """Visual aids on screen (an event or a camera move), not cuts: the longest stretch with none. Over `PACING_WARN`
    it is a warning, over `PACING_MAX` an error. Nothing is ever added to fill it: the author decides what the line
    needs."""
    spans = sorted([(e["start"], min(total, e["start"] + e["duration"])) for e in p.events if e["type"] != "Captions"]
                   + [(m["start"], m["end"]) for m in p.camera])
    gaps, t = [], 0.0
    for a, b in spans:
        if a > t:
            gaps.append((a - t, t))
        t = max(t, b)
    if total > t:
        gaps.append((total - t, t))
    gap, at = max(gaps, default=(0.0, 0.0))
    covered = total - sum(g for g, _ in gaps)
    out = {"longest_s": round(gap, 1), "from_s": round(at, 1), "covered": round(covered / total, 2) if total else 0.0,
           "warn_over_s": PACING_WARN, "max_s": PACING_MAX}
    msg = (f"pacing: no graphic or camera move on screen for {gap:.1f} s from {at:.1f} s; show what the line says there "
           f"(a device on one of its words), or cut tighter. Nothing was added")
    if gap > PACING_MAX:
        out["error"] = msg
    elif gap > PACING_WARN:
        out["warning"] = msg
    return out


# ── command line ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ids", "build"):
        sp = sub.add_parser(name)
        sp.add_argument("project", help="footage/<project>")
        if name == "build":
            sp.add_argument("plan", nargs="?", help="default: <project>/edit/plan.json")
            sp.add_argument("--no-stills", action="store_true", help="skip the strict stills (they need Remotion, ~1 min)")
    sub.add_parser("schema")
    a = ap.parse_args(argv)
    if a.cmd == "schema":
        print(json.dumps(plan_schema(), indent=1))
        return 0
    root = Path(a.project)
    try:
        if a.cmd == "ids":
            print_ids(root)
            return 0
        plan_file = Path(a.plan) if a.plan else root / "edit" / "plan.json"
        res = build(root, json.loads(plan_file.read_text()), stills=not a.no_stills)
    except PlanError as e:
        print("\n".join(f"ERROR {m}" for m in e.errors), file=sys.stderr)
        return 1
    print("\n".join(res["timeline"]))
    print("\n".join(f"WARN {w}" for w in res["warnings"]))
    print(f"pacing: longest stretch without a visual change {res['pacing'].get('longest_s')} s")
    if res["errors"]:
        print("\n".join(f"ERROR {m}" for m in res["errors"]), file=sys.stderr)
        return 1
    print(f"{res['spec']}: {res['duration']:.1f} s, {res['beats']} beats, passes check --strict"
          + ("" if a.no_stills else " and stills --strict (read edit/stills before rendering)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
