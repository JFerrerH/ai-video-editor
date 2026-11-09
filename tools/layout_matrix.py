"""Layout matrix: every overlay component drawn with the worst input its schema allows.

Each component gets props generated from its schema: every text field at its `maxLength` in the widest letters
("W"), every list at its `maxItems`, on three brand fixtures (neutral, dark, pale accent) and two framings of the
speaker (close-up, medium shot). They go through `Project.measure_events`, the same code a real build runs, so
the matrix and a build cannot disagree. Every finding of the layout kinds (outside, small_text, contrast, face,
no_text, hidden) is reported with the component, the fixture, the framing and the props; the exit code is 1 when
there is any. A component either fits every input its schema allows or its schema stops allowing it: lower the
limit (or make the component fit its content) until it exits 0. It is a release gate.

    uv run tools/layout_matrix.py                         # all components, 3 brands x 2 framings
    uv run tools/layout_matrix.py AgeBars Receipt         # some components
    uv run tools/layout_matrix.py --brand dark --framing close-up --json out.json
"""

from __future__ import annotations

import argparse
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
WIDE = "W"  # the widest capital of the Latin faces; "Ñ" and accented capitals are no wider
CHUNK = 8  # letters before a space: a long string breaks into words, as text does, and a word is never longer than this

# brand fixtures: neutral, a dark kit (cream ink on a near-black background) and a pale-accent kit; the dark and the
# pale kit ship real font files (tools/tests/fixtures/fonts)
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
             "fonts": {"serif": 'Georgia, "Noto Serif", serif', "sans": "Barlow, sans-serif", "mono": 'Menlo, "Noto Sans Mono", monospace'},
             "fontFiles": [{"family": "Barlow", "url": "Barlow-Light.ttf", "weight": "300"}]},
}
FONT_FILES = {"Outfit-VF.ttf": "outfit/Outfit-VF.ttf", "RedHatMono-VF.ttf": "redhatmono/RedHatMono-VF.ttf",
              "Barlow-Light.ttf": "barlow/Barlow-Light.ttf"}
# the speaker's head in the 1080x1920 take (source px): a close-up fills the middle of the frame, a medium shot sits lower
FRAMINGS = {"close-up": [300, 520, 780, 1180], "medium": [400, 700, 680, 1040]}


def widest(n: int) -> str:
    """n letters of WIDE, in words of CHUNK letters."""
    out = " ".join(WIDE * CHUNK for _ in range(n // (CHUNK + 1) + 1))
    return out[:n].rstrip() + WIDE * (n - len(out[:n].rstrip()))


def generate(type_: str, examples: bool = False) -> dict:
    """Props for `type_` at the limits of its schema: the first example, every text field at its maxLength, every list
    at its maxItems (items repeated from the example's, their entrance times spread over the first half). With
    `examples`, the first example as it is: what the component draws with ordinary text."""
    s = O.schemas()[type_]
    props = copy.deepcopy((s.get("examples") or [{}])[0])
    return props if examples else _fill(s, props, top=True)


def _fill(node: dict, value, top: bool = False):
    if node.get("x-text") and node.get("type") == "string" and "maxLength" in node:
        return widest(node["maxLength"])
    if node.get("type") == "array" and isinstance(value, list) and value:
        item = node.get("items", {})
        if node.get("x-text") and item.get("type") == "string":
            return [widest(item.get("maxLength", len(v))) if "maxLength" in item else v for v in value[:1]] * \
                node.get("maxItems", len(value))
        n = node.get("maxItems", len(value))
        out = [_fill(item, copy.deepcopy(value[i % len(value)])) for i in range(n)]
        if item.get("type") == "object":
            for key, sub in item.get("properties", {}).items():
                if sub.get("x-time") == "event" and all(isinstance(o, dict) and key in o for o in out):
                    for i, o in enumerate(out):
                        o[key] = round(i * min(0.5, DURATION / 2 / max(1, n)), 2)
        return out
    if isinstance(value, dict) and node.get("properties"):
        for key, sub in node["properties"].items():
            if key in value:
                value[key] = _fill(sub, value[key])
            elif sub.get("x-text") and sub.get("type") == "string" and "maxLength" in sub and top:
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


def spec_for(types: list[str], head: list[int], brand: str, examples: bool = False) -> dict:
    events = []
    for t in types:
        layer, props = O.layers(t)[0], generate(t, examples)
        if O.layout(t) == "full":
            props["full"] = True  # a full-layout scene is a cutaway on the brand's backdrop, as a plan draws it
        events.append({"type": t, "start": 0.0, "duration": DURATION, "props": props, "layer": layer})
    return {"version": 1, "brand": "none",
            "sources": {"take": {"file": "take.mov", "face": [540, 960], "head": head}},
            "segments": [{"take": "take", "in": 0.2, "out": 4.8}], "events": events,
            "camera": [{"kind": "corner", "start": 0.0, "end": DURATION}] if any(e["layer"] == "panel" for e in events) else [],
            "public_files": {"sample.png": "sample.png",
                             **{n: n for n in FONT_FILES if any(f["url"] == n for f in BRANDS[brand]["fontFiles"])}}}


def run(types: list[str], brands: list[str], framings: list[str], examples: bool = False) -> list[dict]:
    """[{component, brand, framing, kind, message, props}] for every finding."""
    found: list[dict] = []
    tmp = Path(tempfile.mkdtemp())
    try:
        root = project_root(tmp)
        for brand in brands:
            for framing in framings:
                names = list(types)
                spec = spec_for(names, FRAMINGS[framing], brand, examples)
                path = root / "edit" / "short.json"
                while True:  # a generated input the spec refuses is a finding too: drop that event and go on
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
                p.measure_events(warnings=warnings)
                for w in warnings:
                    kind = getattr(w, "kind", None)
                    if kind not in KINDS:
                        continue
                    idx = int(re.match(r"events\[(\d+)\]", w).group(1))
                    found.append({"component": names[idx], "brand": brand, "framing": framing, "kind": kind,
                                  "message": str(w), "props": spec["events"][idx]["props"]})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("components", nargs="*", help="default: every component with a schema")
    ap.add_argument("--brand", choices=list(BRANDS), action="append", help="default: all three")
    ap.add_argument("--framing", choices=list(FRAMINGS), action="append", help="default: both")
    ap.add_argument("--json", help="write every finding with its props to this file")
    ap.add_argument("--examples", action="store_true", help="each schema's first example as it is, not at its limits")
    a = ap.parse_args(argv)
    types = a.components or sorted(c for c in O.COMPONENTS if c in O.schemas())
    if unknown := [t for t in types if t not in O.schemas()]:
        sys.exit(f"no schema for: {', '.join(unknown)}")
    brands, framings = a.brand or list(BRANDS), a.framing or list(FRAMINGS)
    t0 = time.time()
    found = run(types, brands, framings, a.examples)
    if a.json:
        Path(a.json).write_text(json.dumps(found, indent=1, ensure_ascii=False))
    for f in found:
        print(f"{f['component']:<14} {f['brand']:<8} {f['framing']:<9} {f['kind']:<10} {f['message']}")
    n = len(types) * len(brands) * len(framings)
    print(f"{len(types)} components, {len(brands)} brands, {len(framings)} framings = {n} inputs, "
          f"{len(found)} findings in {time.time() - t0:.0f} s", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
