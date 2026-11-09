"""Layout matrix: every overlay component drawn with the worst input its schema allows.

Each component gets props generated from its schema: every text field at its `maxLength` in wide capitals
(M W O Q D H N U), every list at its `maxItems`, on three brand fixtures (neutral, dark, pale accent) and two framings of the
speaker (close-up, medium shot). They go through `Project.measure_events`, the same code a real build runs, so
the matrix and a build cannot disagree. Every finding of the layout kinds (outside, small_text, contrast, face,
no_text, hidden) is reported with the component, the fixture, the framing and the props; the exit code is 1 when
there is any. A component either fits every input its schema allows or its schema stops allowing it: lower the
limit (or make the component fit its content) until it exits 0. It is a release gate. One finding is not the schema's:
a floating card whose own example (with its lists at their limits) can't sit above a close-up's head has no room
there whatever its text (a plan
answers with `"full": true` or a `corner` move, as the finding says); it is listed as `no room` and doesn't fail.

    uv run tools/layout_matrix.py                         # all components, 3 brands x 2 framings
    uv run tools/layout_matrix.py AgeBars Receipt         # some components
    uv run tools/layout_matrix.py --brand dark --framing close-up --json out.json
"""

from __future__ import annotations

import argparse
import os
import copy
import re
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import overlay_schema as O  # noqa: E402
from brand import ink_on_light  # noqa: E402
import short_spec as S  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures"
KINDS = {"outside", "small_text", "contrast", "face", "no_text", "hidden"}
REFUSAL = "fits above the speaker's head only at"  # shortform.measure_events' refusal with its fix
DURATION = 4.0
# wide capitals, cycled: about 0.75 em a letter against ~0.5 em for ordinary text, so a component that fits them fits
# any real text of that length with room to spare (all "W", ~0.95 em, would refuse what renders fine today)
WIDE = "MWOQDHNU"
CHUNK = 8  # letters before a space: a long string breaks into words, as text does, and a word is never longer than this

# brand fixtures: neutral, a dark kit (cream ink on a near-black background) and a pale-accent kit; the dark and the
# pale kit ship real font files (tools/tests/fixtures/fonts), each with the weights a kit ships (variable faces: a kit
# with one light weight draws its bold text as hairlines, which no component can make readable)
BRANDS = {
    "neutral": {"colors": {"bg": "#F4F4F2", "tint1": "#E4E4E0", "tint2": "#D9DEE4", "ink": "#1A1A1A", "muted": "#6B6B6B",
                           "accent": "#D64545", "success": "#2F7D5B"},
                "fonts": {"serif": 'Georgia, "Noto Serif", serif', "sans": '"Helvetica Neue", "Noto Sans", sans-serif',
                          "mono": 'Menlo, "Noto Sans Mono", monospace'}, "fontFiles": []},
    "dark": {"colors": {"bg": "#111418", "tint1": "#1E252C", "tint2": "#27313A", "ink": "#F2EFE9", "muted": "#9AA4AD",
                        "accent": "#3FD0C9", "success": "#4CC38A"},
             "fonts": {"serif": "Outfit, Georgia, serif", "sans": "Outfit, sans-serif", "mono": '"Red Hat Mono", monospace'},
             "fontFiles": [{"family": "Outfit", "url": "Outfit-VF.ttf", "weight": "100 900"},
                           {"family": "Red Hat Mono", "url": "RedHatMono-VF.ttf", "weight": "300 700"}]},
    "pale": {"colors": {"bg": "#F2F0E9", "tint1": "#E4E4E0", "tint2": "#D9DEE4", "ink": "#16150F", "muted": "#6B6B6B",
                        "accent": "#E8FD5A", "success": "#2F7D5B"},
             "fonts": {"serif": 'Georgia, "Noto Serif", serif', "sans": '"Helvetica Neue", "Noto Sans", sans-serif',
                       "mono": '"Red Hat Mono", monospace'},
             "fontFiles": [{"family": "Red Hat Mono", "url": "RedHatMono-VF.ttf", "weight": "300 700"}]},
}
FONT_FILES = {"Outfit-VF.ttf": "outfit/Outfit-VF.ttf", "RedHatMono-VF.ttf": "redhatmono/RedHatMono-VF.ttf"}
# the speaker's head in the 1080x1920 take (source px): a close-up fills the middle of the frame, a medium shot sits lower
FRAMINGS = {"close-up": [300, 520, 780, 1180], "medium": [400, 700, 680, 1040]}


def widest(n: int, kind: object = True) -> str:
    """n wide capitals (WIDE, cycled) in words of CHUNK letters. The kind comes from the field's schema (`x-text`),
    never from its example: "number" gets the widest digit, "symbol" a wide currency sign, anything else letters."""
    letters = {"number": "8", "symbol": "€"}.get(kind, WIDE) if isinstance(kind, str) else WIDE
    out = []
    for i in range(n):
        out.append(" " if (i + 1) % (CHUNK + 1) == 0 and i < n - 1 and letters == WIDE else letters[i % len(letters)])
    return "".join(out)


def generate(type_: str) -> dict:
    """Props for `type_` at the limits of its schema: the first example, every text field at its maxLength, every list
    at its maxItems (items repeated from the example's, their entrance times spread over the first half)."""
    s = O.schemas()[type_]
    props = copy.deepcopy((s.get("examples") or [{}])[0])
    return _fill(s, props, top=True)


def _fill(node: dict, value, top: bool = False, text: bool = True):
    if node.get("x-text") and node.get("type") == "string" and "maxLength" in node:
        return widest(node["maxLength"], node.get("x-text")) if text else value
    if node.get("type") == "array" and isinstance(value, list) and value:
        item = node.get("items", {})
        if node.get("x-text") and item.get("type") == "string":
            return [widest(item.get("maxLength", len(v)), node.get("x-text")) if "maxLength" in item and text else v for v in value[:1]] * \
                node.get("maxItems", len(value))
        n = node.get("maxItems", len(value))
        out = [_fill(item, copy.deepcopy(value[i % len(value)]), text=text) for i in range(n)]
        if item.get("type") == "object":
            for key, sub in item.get("properties", {}).items():
                if sub.get("x-time") == "event" and all(isinstance(o, dict) and key in o for o in out):
                    for i, o in enumerate(out):
                        o[key] = round(i * min(0.5, DURATION / 2 / max(1, n)), 2)
        return out
    if isinstance(value, dict) and node.get("properties"):
        for key, sub in node["properties"].items():
            if key in value:
                value[key] = _fill(sub, value[key], text=text)
            elif sub.get("x-text") and sub.get("type") == "string" and "maxLength" in sub and top and text:
                value[key] = widest(sub["maxLength"], sub.get("x-text"))
        return value
    return value


def make_take(path: Path) -> None:
    expr = "+".join(f"0.5*between(t,{a},{a + 0.5})" for a in (0.3, 1.2, 2.1, 3.0, 3.9))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x888888:s=1080x1920:r=30:d=5",
                    "-f", "lavfi", "-i", f"aevalsrc='sin(2*PI*220*t)*({expr})':s=48000:d=5",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "pcm_s16le", str(path)], check=True)


def _hex(l: float, c: float, h: float) -> str:
    """An OKLCH colour as sRGB hex, clipped to the gamut."""
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_, m_, s_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3, (l - 0.1055613458 * a - 0.0638541728 * b) ** 3, \
        (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    enc = [12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in (min(1.0, max(0.0, x)) for x in rgb)]
    return "#" + "".join(f"{round(v * 255):02X}" for v in enc)


def random_brand(rng: random.Random) -> dict:
    """A kit a real brand could ship: a background anywhere from near black to near white, ink on the far side of it,
    and muted, accent, tints and success drawn freely, so nothing is picked to suit the components. Fonts from one of
    the fixed kits."""
    hue, light = rng.uniform(0, 360), rng.random() < 0.6
    bg_l = rng.uniform(0.86, 0.98) if light else rng.uniform(0.12, 0.3)
    ink_l = rng.uniform(0.12, 0.3) if light else rng.uniform(0.88, 0.98)
    colors = {"bg": _hex(bg_l, rng.uniform(0, 0.04), hue), "ink": _hex(ink_l, rng.uniform(0, 0.03), hue),
              "tint1": _hex(bg_l + (-0.06 if light else 0.06), rng.uniform(0, 0.06), hue),
              "tint2": _hex(bg_l + (-0.1 if light else 0.1), rng.uniform(0, 0.06), rng.uniform(0, 360)),
              "muted": _hex(rng.uniform(0.35, 0.75), rng.uniform(0, 0.05), hue),
              "accent": _hex(rng.uniform(0.45, 0.95), rng.uniform(0.05, 0.2), rng.uniform(0, 360)),
              "success": _hex(rng.uniform(0.45, 0.8), rng.uniform(0.08, 0.18), rng.uniform(120, 170))}
    base = BRANDS[rng.choice(["neutral", "dark", "pale"])]
    return {"colors": colors, "fonts": dict(base["fonts"]), "fontFiles": list(base["fontFiles"])}


def random_props(type_: str, rng: random.Random) -> dict:
    """The first example with every text field at a random length up to its maxLength (in the characters its kind
    allows) and every list at a random count up to its maxItems."""
    s = O.schemas()[type_]
    return _fill_random(s, copy.deepcopy((s.get("examples") or [{}])[0]), rng)


def _fill_random(node: dict, value, rng: random.Random):
    if node.get("x-text") and node.get("type") == "string" and "maxLength" in node:
        return widest(rng.randint(1, node["maxLength"]), node.get("x-text"))
    if node.get("type") == "array" and isinstance(value, list) and value:
        item = node.get("items", {})
        n = rng.randint(max(1, node.get("minItems", 1)), node.get("maxItems", len(value)))
        if node.get("x-text") and item.get("type") == "string" and "maxLength" in item:
            return [widest(rng.randint(1, item["maxLength"]), node.get("x-text")) for _ in range(n)]
        out = [_fill_random(item, copy.deepcopy(value[i % len(value)]), rng) for i in range(n)]
        if item.get("type") == "object":
            for key, sub in item.get("properties", {}).items():
                if sub.get("x-time") == "event" and all(isinstance(o, dict) and key in o for o in out):
                    for i, o in enumerate(out):
                        o[key] = round(i * min(0.5, DURATION / 2 / max(1, n)), 2)
        return out
    if isinstance(value, dict) and node.get("properties"):
        for key, sub in node["properties"].items():
            if key in value:
                value[key] = _fill_random(sub, value[key], rng)
        return value
    return value


def project_root(tmp: Path) -> Path:
    root = tmp / "matrix"
    (root / "edit" / "transcripts").mkdir(parents=True)
    make_take(root / "take.mov")
    words = [{"type": "word", "text": w, "start": a, "end": a + 0.5}
             for w, a in zip("one two three four five".split(), (0.3, 1.2, 2.1, 3.0, 3.9))]
    (root / "edit" / "transcripts" / "take.json").write_text(json.dumps({"words": words}))
    for name, src in FONT_FILES.items():
        shutil.copy(FIXTURES / "fonts" / src, root / name)
    # the image components' examples name `sample.png`: a photo-like gradient stands in for it
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "gradients=s=1080x1350:c0=0x6a8caf:c1=0xd9b38c",
                    "-frames:v", "1", str(root / "sample.png")], check=True)
    return root


def example(type_: str) -> dict:
    """The first example with its lists at their maxItems and its own text: what the component looks like at the
    counts the schema allows, in ordinary words."""
    s = O.schemas()[type_]
    return _fill(s, copy.deepcopy((s.get("examples") or [{}])[0]), top=True, text=False)


def spec_for(types: list[str], head: list[int], brand: str, props_of=generate) -> dict:
    events = []
    for t in types:
        layer, props = O.layers(t)[0], props_of(t)
        if O.layout(t) == "full":
            props["full"] = True  # a full-layout scene is a cutaway on the brand's backdrop, as a plan draws it
        events.append({"type": t, "start": 0.0, "duration": DURATION, "props": props, "layer": layer})
    return {"version": 1, "brand": "none",
            "sources": {"take": {"file": "take.mov", "face": [540, 960], "head": head}},
            "segments": [{"take": "take", "in": 0.2, "out": 4.8}], "events": events,
            "camera": [{"kind": "corner", "start": 0.0, "end": DURATION}] if any(e["layer"] == "panel" for e in events) else [],
            "public_files": {"sample.png": "sample.png",
                             **{n: n for n in FONT_FILES if any(f["url"] == n for f in BRANDS[brand]["fontFiles"])}}}


def _measure(root: Path, names: list[str], brand: str, framing: str, props_of) -> tuple[list[dict], list[dict]]:
    """(findings, the events measured) for `names` drawn with `props_of(type)`. A generated input the spec refuses is an
    `invalid` finding: that event is dropped and the rest measured."""
    found: list[dict] = []
    spec = spec_for(names, FRAMINGS[framing], brand, props_of)
    path = root / "edit" / "short.json"
    while True:
        path.write_text(json.dumps(spec))
        try:
            p, _ = S.load(path, root)
            break
        except S.SpecError as err:
            bad = {int(m) for e in err.errors for m in re.findall(r"events\[(\d+)\]", e)}
            if not bad:
                raise
            for i in sorted(bad):
                found.append({"component": names[i], "brand": brand, "framing": framing, "kind": "invalid",
                              "message": next(e for e in err.errors if f"events[{i}]" in e),
                              "props": spec["events"][i]["props"]})
            names = [n for i, n in enumerate(names) if i not in bad]
            spec["events"] = [e for i, e in enumerate(spec["events"]) if i not in bad]
    p.brand = {**BRANDS[brand], "colors": ink_on_light(BRANDS[brand]["colors"])}  # as brand.load_brand does
    warnings: list = []
    p.measure_events(scale=1, warnings=warnings)  # the scale a build's stills measure at, so the two can't disagree
    for w in warnings:
        kind = getattr(w, "kind", None)
        if kind in KINDS:
            idx = int(re.match(r"events\[(\d+)\]", w).group(1))
            found.append({"component": names[idx], "brand": brand, "framing": framing, "kind": kind,
                          "message": str(w), "props": spec["events"][idx]["props"]})
    return found, spec["events"]


def run(types: list[str], brands: list[str], framings: list[str], jobs: int = 1, samples: int = 0,
        seed: int = 0) -> tuple[list[dict], list[dict]]:
    """(findings, no room): every finding [{component, brand, framing, kind, message, props}], and apart from them the
    `face` findings of components whose own first example (lists at their maxItems, its own text) has them too in that
    framing: a floating card that size has
    no room above that head whatever its text, and a plan answers it as the finding says (`full`, a `corner` move).
    The work is split into brand x framing x slice-of-components units, about two per worker, so no single pair sets
    the wall time; `jobs` units run at once, each in its own project."""
    from concurrent.futures import ThreadPoolExecutor

    def one(brand: str, framing: str, names: list[str], props_of) -> tuple[list[dict], list[dict]]:
        tmp = Path(tempfile.mkdtemp())
        try:
            root = project_root(tmp)
            here, _ = _measure(root, names, brand, framing, props_of)
            faced = sorted({f["component"] for f in here if f["kind"] == "face"})
            base = {f["component"] for f in (_measure(root, faced, brand, framing, example)[0] if faced else [])
                    if f["kind"] == "face"}
            # the engine refusing a floating card with its fix (no room above this head at a readable size) is the rule
            # working, whatever the text: that refusal and the face finding that goes with it are listed apart
            refused = {f["component"] for f in here if f["kind"] == "face" and REFUSAL in f["message"]} | base
            return ([f for f in here if not (f["kind"] == "face" and f["component"] in refused)],
                    [f for f in here if f["kind"] == "face" and f["component"] in refused])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    pairs = [(b, f, generate) for b in brands for f in framings]
    for r in range(samples):  # random inputs: a brand, a framing and props per component, all from (seed, r)
        rng = random.Random(f"{seed}/{r}")
        name = f"random-{r}"
        BRANDS[name] = random_brand(rng)
        framing = rng.choice(sorted(FRAMINGS))
        pairs.append((name, framing, lambda t, r=r: random_props(t, random.Random(f"{seed}/{r}/{t}"))))
    slices = max(1, min(len(types), -(-2 * max(1, jobs) // len(pairs))))  # about two units per worker
    names = list(types)
    units = [(b, f, names[i::slices], g) for b, f, g in pairs for i in range(slices) if names[i::slices]]
    with ThreadPoolExecutor(max(1, jobs)) as pool:  # each unit renders in its own node process: threads are enough
        results = list(pool.map(lambda u: one(*u), units))
    return [f for r in results for f in r[0]], [f for r in results for f in r[1]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("components", nargs="*", help="default: every component with a schema")
    ap.add_argument("--brand", choices=list(BRANDS), action="append", help="default: all three")
    ap.add_argument("--framing", choices=list(FRAMINGS), action="append", help="default: both")
    ap.add_argument("--json", help="write every finding with its props to this file")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2),
                    help="units measured at once (default: cores minus two)")
    ap.add_argument("--random", type=int, default=2, help="random inputs per component: each a random brand, framing and props")
    ap.add_argument("--seed", type=int, help="reproduce a run (default: a new seed, printed)")
    a = ap.parse_args(argv)
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(10 ** 6)
    print(f"seed {seed} (reproduce: --seed {seed})", file=sys.stderr, flush=True)
    types = a.components or sorted(c for c in O.COMPONENTS if c in O.schemas())
    if unknown := [t for t in types if t not in O.schemas()]:
        sys.exit(f"no schema for: {', '.join(unknown)}")
    brands, framings = a.brand or list(BRANDS), a.framing or list(FRAMINGS)
    t0 = time.time()
    found, no_room = run(types, brands, framings, a.jobs, a.random, seed)
    if a.json:
        Path(a.json).write_text(json.dumps(found, indent=1, ensure_ascii=False))
    for c, b, fr in sorted({(f["component"], f["brand"], f["framing"]) for f in no_room}):
        print(f"{c:<14} {b:<8} {fr:<9} no room   refused with its fix: no room above this head at a readable size")
    for f in found:
        print(f"{f['component']:<14} {f['brand']:<8} {f['framing']:<9} {f['kind']:<10} {f['message']}")
    n = len(types) * (len(brands) * len(framings) + a.random)
    print(f"{len(types)} components x ({len(brands)} brands x {len(framings)} framings + {a.random} random) = {n} inputs, "
          f"{len(found)} findings, wall time {time.time() - t0:.0f} s ({a.jobs} jobs, seed {seed})", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
