"""Props schemas of the overlay components and scene primitives (`<Name>.schema.json` beside each
component in tools/motion/src/), plus the props the overlay layer reads on every event
(`tools/motion/src/event.schema.json`). Standard library only: `check` reads them without Node.

    uv run tools/overlay_schema.py --export        # every schema as one JSON object (key per component + "event")

    from overlay_schema import validate, time_fields, cue_finish, text_fields
    validate("StatScene", {"value": "400.000"})    # [("value", 'must be a number, got the string "400.000"')]

JSON Schema subset: `type` (or a list of types), `enum`, `minimum`/`maximum`, `maxLength`, `items`,
`properties`, `required`, `additionalProperties` (false unless given: true or a schema), `oneOf`,
`default` (documents the component's own default; cue `when` reads it). Engine annotations:

    x-time: "event"     number field: seconds from the event's start. In a short-form spec it also takes
                        a word or segment anchor, resolved before rendering (short_spec.load).
    x-time: "duration"  number field: a length in seconds (never resolved).
    x-time: "frames"    number field: a length in frames (never resolved).
    x-text: true        string field (or list of strings) shown to the viewer as text.
    x-layout            top level: "full" (a scene drawn across the safe area) or "float" (an element).
    x-cues              top level: entrances that start on a time and how long they take:
        {"path": "items[].at" | "stops[]" | "countEnd",   per item (its field, or the item itself) or one prop
         "when": {"style": ["rise", …]},              optional: only while these props hold these values
         "default": {"first": s, "step": s, "first_prop": p, "step_prop": p} | "even" | s,
                                                      cue time when the field is omitted (a *_prop wins when set)
         "entrance": {"frames": n, "seconds": s, "seconds_prop": p, "per_word": {"prop": "stagger", "default": n},
                      "per_char_s": s, "text": "text"}}
        A cue's entrance ends at cue + (frames + per_word × (words − 1)) / fps + seconds + per_char_s × characters,
        words and characters counted in the item's `text` field.
"""

from __future__ import annotations

import json
import math
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "tools" / "motion" / "src"
EVENT = "event"  # key of the shared event props in the export


def _registry(path: Path, block: str) -> set[str]:  # same parse as storyboard.py's
    m = re.search(block + r"[^{]*\{([^}]*)\}", path.read_text())
    return set(re.findall(r"\b([A-Z]\w+)\b", m.group(1))) if m else set()


# overlay components and scene primitives both render as events; captions come from the engine
COMPONENTS = (_registry(SRC / "Overlay.tsx", r"export const REGISTRY")
              | _registry(SRC / "scenes/index.ts", r"export const SCENES")) - {"Captions"}


@lru_cache(maxsize=None)
def schemas() -> dict[str, dict]:
    """name → schema for every `<Name>.schema.json` under tools/motion/src, plus "event"."""
    out = {p.name[:-len(".schema.json")]: json.loads(p.read_text()) for p in SRC.rglob("*.schema.json")}
    return out


def schema(type_: str) -> dict:
    """The component's schema with the shared event props merged into its properties."""
    s = schemas().get(type_)
    if s is None:
        raise KeyError(f"no schema for {type_} (tools/motion/src/**/{type_}.schema.json)")
    ev = schemas().get(EVENT, {}).get("properties", {})
    return {**s, "properties": {**ev, **s.get("properties", {})}}


def export() -> dict:
    """Every component's schema (as written, without the shared props) plus the shared props under "event"."""
    out = {k: schemas()[k] for k in sorted(COMPONENTS) if k in schemas()}
    out[EVENT] = schemas().get(EVENT, {})
    return out


# ── validation ────────────────────────────────────────────────────────────
TYPE_NAMES = {"number": "a number", "integer": "a whole number", "string": "a string", "boolean": "true or false",
              "array": "a list", "object": "an object", "null": "null"}


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is(v: Any, t: str) -> bool:
    return {"number": lambda: _num(v),
            "integer": lambda: _num(v) and float(v).is_integer(),
            "string": lambda: isinstance(v, str),
            "boolean": lambda: isinstance(v, bool),
            "array": lambda: isinstance(v, list),
            "object": lambda: isinstance(v, dict),
            "null": lambda: v is None}[t]()


def _got(v: Any) -> str:
    if isinstance(v, str):
        return f"the string {json.dumps(v[:40] + ('…' if len(v) > 40 else ''), ensure_ascii=False)}"
    if isinstance(v, bool):
        return f"{str(v).lower()}"
    if _num(v):
        return f"the number {v}"
    return {list: "a list", dict: "an object", type(None): "null"}.get(type(v), type(v).__name__)


def _join(path: str, key: str | int) -> str:
    return f"{path}[{key}]" if isinstance(key, int) else (f"{path}.{key}" if path else key)


ANCHOR_HINT = 'seconds from the event\'s start, or an anchor ({"word": …, "take": …} or {"seg": …, "edge": …})'


def _check(s: dict, v: Any, path: str, anchors: bool, owner: str, out: list[tuple[str, str]]) -> None:
    if s.get("x-time") == "event":
        if anchors and isinstance(v, dict):
            return  # anchor: its shape is the spec's business (short_spec._check_time)
        if not _num(v):
            want = ANCHOR_HINT if anchors else "seconds from the event's start (a number)"
            out.append((path, f"must be {want}, got {_got(v)}"))
            return
    if "oneOf" in s:
        branches = []
        for b in s["oneOf"]:
            errs: list[tuple[str, str]] = []
            _check(b, v, path, anchors, owner, errs)
            if not errs:
                return
            branches.append((b, errs))
        typed = [e for b, e in branches if "type" not in b or any(_is(v, t) for t in _types(b))]
        out.extend(typed[0] if typed else [(path, f"must be {_want(s)}, got {_got(v)}")])
        return
    types = _types(s)
    if types and not any(_is(v, t) for t in types):
        out.append((path, f"must be {_want(s)}, got {_got(v)}"))
        return
    if _num(v) and not math.isfinite(v):
        out.append((path, "must be a finite number"))
        return
    if "enum" in s and v not in s["enum"]:
        out.append((path, f"must be one of {', '.join(json.dumps(x) for x in s['enum'])}; got {_got(v)}"))
        return
    if _num(v):
        lo, hi = s.get("minimum"), s.get("maximum")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            rng = f"between {lo} and {hi}" if lo is not None and hi is not None else \
                (f"at least {lo}" if lo is not None else f"at most {hi}")
            out.append((path, f"must be {rng}, got {v}"))
    if isinstance(v, str) and "maxLength" in s and len(v) > s["maxLength"]:
        out.append((path, f"must be at most {s['maxLength']} characters, got {len(v)}"))
    if isinstance(v, list) and "items" in s:
        for i, x in enumerate(v):
            _check(s["items"], x, _join(path, i), anchors, owner, out)
    if isinstance(v, dict) and ("properties" in s or "additionalProperties" in s):
        props = s.get("properties", {})
        extra = s.get("additionalProperties", False)
        for k in s.get("required", []):
            if k not in v:
                out.append((_join(path, k), "missing required field"))
        for k, x in v.items():
            if k in props:
                _check(props[k], x, _join(path, k), anchors, owner, out)
            elif extra is False:
                where = f"{owner} props" if not path else f"{owner} {path}"
                out.append((_join(path, k), f"unknown field; {where} are: {', '.join(sorted(props))}"))
            elif isinstance(extra, dict):
                _check(extra, x, _join(path, k), anchors, owner, out)


def _types(s: dict) -> list[str]:
    t = s.get("type")
    return [t] if isinstance(t, str) else list(t or [])


def _want(s: dict) -> str:
    if "oneOf" in s:
        return " or ".join(_want(b) for b in s["oneOf"])
    return " or ".join(TYPE_NAMES[t] for t in _types(s)) or "a valid value"


def validate(type_: str, props: Any, anchors: bool = False) -> list[tuple[str, str]]:
    """[(field path, message)] for every problem in an event's props (empty = valid).
    `anchors`: time fields may hold a word/segment anchor (short-form specs)."""
    out: list[tuple[str, str]] = []
    if not isinstance(props, dict):
        return [("", f"must be an object, got {_got(props)}")]
    _check(schema(type_), props, "", anchors, type_, out)
    return out


# ── walking annotated fields ──────────────────────────────────────────────
def _walk(s: dict, v: Any, path: str, parent: Any, key: Any) -> Iterator[tuple[str, dict, Any, Any, Any]]:
    """(path, field schema, value, parent container, key) for every value present in props."""
    yield path, s, v, parent, key
    if "oneOf" in s:
        for b in s["oneOf"]:
            if "type" not in b or any(_is(v, t) for t in _types(b)):
                yield from ((p, bs, bv, bp, bk) for p, bs, bv, bp, bk in _walk(b, v, path, parent, key) if p != path)
                break
    if isinstance(v, list) and "items" in s:
        for i, x in enumerate(v):
            yield from _walk(s["items"], x, _join(path, i), v, i)
    if isinstance(v, dict):
        props = s.get("properties", {})
        for k, x in v.items():
            if k in props:
                yield from _walk(props[k], x, _join(path, k), v, k)


def time_fields(type_: str, props: dict) -> list[tuple[str, Any, Any, Any]]:
    """[(path, value, parent, key)] for every event-relative time present in props, so a caller can
    replace an anchor with seconds (`parent[key] = t`)."""
    return [(p, v, par, k) for p, s, v, par, k in _walk(schema(type_), props, "", None, None)
            if s.get("x-time") == "event"]


def text_fields(type_: str, props: dict) -> list[tuple[str, Any, Any, Any]]:
    """[(path, value, parent, key)] for every string shown to the viewer (`x-text`)."""
    out = []
    for p, s, v, par, k in _walk(schema(type_), props, "", None, None):
        if s.get("x-text") and isinstance(v, str):
            out.append((p, v, par, k))
        elif s.get("x-text") and isinstance(v, list):
            out += [(_join(p, i), x, v, i) for i, x in enumerate(v) if isinstance(x, str)]
    return out


def layout(type_: str) -> str:
    return schemas().get(type_, {}).get("x-layout", "float")


def _prop(s: dict, props: dict, name: str) -> Any:
    return props[name] if name in props else s.get("properties", {}).get(name, {}).get("default")


def _words(text: Any) -> int:
    return len(str(text or "").split())


def cue_finish(type_: str, props: dict, fps: int, duration: float) -> list[tuple[str, float, float]]:
    """[(cue path, cue time, entrance finish)] in seconds from the event's start, from explicit or
    default cues. Time fields must already be numbers (anchors resolved)."""
    s = schema(type_)
    out = []
    for cue in s.get("x-cues", []):
        if any(_prop(s, props, k) not in vals for k, vals in cue.get("when", {}).items()):
            continue
        ent, dflt = cue.get("entrance", {}), cue.get("default")

        def finish(t: float, item: dict) -> float:
            words = _words(item.get(ent["text"])) if "text" in ent else 1
            pw = ent.get("per_word")
            per_word = _prop(s, props, pw["prop"]) if pw else 0
            per_word = per_word if _num(per_word) else (pw or {}).get("default", 0)
            chars = len(str(item.get(ent["text"], ""))) if "text" in ent else 0
            secs = _prop(s, props, ent["seconds_prop"]) if "seconds_prop" in ent else None
            secs = secs if _num(secs) else ent.get("seconds", 0)
            return (t + (ent.get("frames", 0) + per_word * max(0, words - 1)) / fps + secs
                    + ent.get("per_char_s", 0) * chars)

        if "[]" in cue["path"]:
            arr, _, field = cue["path"].partition("[]")
            field = field.lstrip(".")
            items = props.get(arr)
            if not isinstance(items, list):
                continue
            for i, it in enumerate(items):
                given = it if not field else (it.get(field) if isinstance(it, dict) else None)
                it = it if isinstance(it, dict) else {}
                if _num(given):
                    t = float(given)
                elif dflt == "even":
                    t = i * duration / len(items)
                elif isinstance(dflt, dict):
                    first = _prop(s, props, dflt["first_prop"]) if "first_prop" in dflt else None
                    step = _prop(s, props, dflt["step_prop"]) if "step_prop" in dflt else None
                    t = (first if _num(first) else dflt["first"]) + i * (step if _num(step) else dflt["step"])
                else:
                    continue
                out.append((f"{arr}[{i}]", round(t, 3), round(finish(t, it), 3)))
        else:
            v = props.get(cue["path"], dflt)
            if _num(v):
                out.append((cue["path"], round(float(v), 3), round(finish(float(v), props), 3)))
    return out


def main() -> None:
    if sys.argv[1:] != ["--export"]:
        sys.exit(__doc__)
    missing = sorted(COMPONENTS - set(schemas()))
    if missing:
        sys.exit(f"no schema for: {', '.join(missing)}")
    print(json.dumps(export(), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
