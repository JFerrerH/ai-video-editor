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


def widest(n: int, like: object = None) -> str:
    """n wide capitals (WIDE, cycled) in words of CHUNK letters. A field whose example has no letters (a year, an amount,
    a currency sign) gets its own kind of character: the widest digit, or the example's first symbol."""
    letters = WIDE
    if isinstance(like, str) and like.strip() and not any(c.isalpha() for c in like):
        letters = "8" if any(c.isdigit() for c in like) else like.strip()[0]
    out = []
    for i in range(n):
        out.append(" " if (i + 1) % (CHUNK + 1) == 0 and i < n - 1 else letters[i % len(letters)])
    return "".join(out)


def generate(type_: str) -> dict:
    """Props for `type_` at the limits of its schema: the first example, every text field at its maxLength, every list
    at its maxItems (items repeated from the example's, their entrance times spread over the first half)."""
    s = O.schemas()[type_]
    props = copy.deepcopy((s.get("examples") or [{}])[0])
    return _fill(s, props, top=True)


def _fill(node: dict, value, top: bool = False, text: bool = True):
    if node.get("x-text") and node.get("type") == "string" and "maxLength" in node:
        return widest(node["maxLength"], value) if text else value
    if node.get("type") == "array" and isinstance(value, list) and value:
        item = node.get("items", {})
        if node.get("x-text") and item.get("type") == "string":
            return [widest(item.get("maxLength", len(v)), v) if "maxLength" in item and text else v for v in value[:1]] * \
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
                value[key] = widest(sub["maxLength"])
        return value
    return value


def make_take(path: Path) -> None:
    expr = "+".join(f"0.5*between(t,{a},{a + 0.5})" for a in (0.3, 1.2, 2.1, 3.0, 3.9))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x888888:s=1080x1920:r=30:d=5",
                    "-f", "lavfi", "-i", f"aevalsrc='sin(2*PI*220*t)*({expr})':s=48000:d=5",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "pcm_s16le", str(path)], check=True)


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


def run(types: list[str], brands: list[str], framings: list[str], jobs: int = 1) -> tuple[list[dict], list[dict]]:
    """(findings, no room): every finding [{component, brand, framing, kind, message, props}], and apart from them the
    `face` findings of components whose own first example (lists at their maxItems, its own text) has them too in that
    framing: a floating card that size has
    no room above that head whatever its text, and a plan answers it as the finding says (`full`, a `corner` move).
    The work is split into brand x framing x slice-of-components units, about two per worker, so no single pair sets
    the wall time; `jobs` units run at once, each in its own project."""
    from concurrent.futures import ThreadPoolExecutor

    def one(brand: str, framing: str, names: list[str]) -> tuple[list[dict], list[dict]]:
        tmp = Path(tempfile.mkdtemp())
        try:
            root = project_root(tmp)
            here, _ = _measure(root, names, brand, framing, generate)
            faced = sorted({f["component"] for f in here if f["kind"] == "face"})
            base = {f["component"] for f in (_measure(root, faced, brand, framing, example)[0] if faced else [])
                    if f["kind"] == "face"}
            return ([f for f in here if not (f["kind"] == "face" and f["component"] in base)],
                    [f for f in here if f["kind"] == "face" and f["component"] in base])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    pairs = [(b, f) for b in brands for f in framings]
    slices = max(1, min(len(types), -(-2 * max(1, jobs) // len(pairs))))  # about two units per worker
    names = list(types)
    units = [(b, f, names[i::slices]) for b, f in pairs for i in range(slices) if names[i::slices]]
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
    a = ap.parse_args(argv)
    types = a.components or sorted(c for c in O.COMPONENTS if c in O.schemas())
    if unknown := [t for t in types if t not in O.schemas()]:
        sys.exit(f"no schema for: {', '.join(unknown)}")
    brands, framings = a.brand or list(BRANDS), a.framing or list(FRAMINGS)
    t0 = time.time()
    found, no_room = run(types, brands, framings, a.jobs)
    if a.json:
        Path(a.json).write_text(json.dumps(found, indent=1, ensure_ascii=False))
    for c, b, fr in sorted({(f["component"], f["brand"], f["framing"]) for f in no_room}):
        print(f"{c:<14} {b:<8} {fr:<9} no room   its own example doesn't fit above this head either (not a limit)")
    for f in found:
        print(f"{f['component']:<14} {f['brand']:<8} {f['framing']:<9} {f['kind']:<10} {f['message']}")
    n = len(types) * len(brands) * len(framings)
    print(f"{len(types)} components, {len(brands)} brands, {len(framings)} framings = {n} inputs, "
          f"{len(found)} findings, wall time {time.time() - t0:.0f} s ({a.jobs} jobs)", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
