"""Every overlay and scene, drawn with its schema example under two extreme fixture brands, through the
legibility probe: a pale accent (#E8FD5A) on a light backdrop and a dark accent (#1A1A40) on a dark one.
Fails naming each component and brand whose text contrast is under 3:1 (brand-theme "Every component
readable with extreme accents").

    uv run tools/tests/contrast_matrix.py [Component ...]     # or, in tools/motion: npm run test:contrast

Slow (two stills per component and brand, ~1–2 min), so it runs on demand and in the release check, not
with the unit tests. Needs tools/motion's node_modules.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import overlay_schema as O  # noqa: E402
from shortform import MOTION, PROBE_DELTA, Project, low_contrast, still_time  # noqa: E402

COLORS = {"bg": "#F7F5EF", "tint1": "#ECE9DF", "tint2": "#E3E6DC", "ink": "#16150F", "muted": "#5E5C55",
          "success": "#2F7D5B"}
FONTS = {"serif": 'Georgia, "Noto Serif", serif', "sans": '"Helvetica Neue", "Noto Sans", sans-serif',
         "mono": 'Menlo, "Noto Sans Mono", monospace'}
BRANDS = {  # name → (accent, dark backdrop)
    "pale-accent": ("#E8FD5A", False),
    "dark-accent": ("#1A1A40", True),
}
DURATION, FPS = 6.0, 30
# drawn over footage or the dark pull backdrop by design (light text), so a light backdrop isn't a fair test
DARK_ONLY = {"BehindWord"}


def dark_capable(name: str) -> bool:
    """A scene draws its own tone (`bg`); one without a dark tone on a dark backdrop is a mismatch check refuses
    in spirit (D15), so it isn't drawn that way here. Floating components sit on the backdrop either way."""
    return O.layout(name) != "full" or "bg" in O.schema(name).get("properties", {})


def event(name: str, dark: bool) -> dict:
    props = {**O.schema(name)["examples"][0], "full": True}
    if dark:
        props["dark"] = True
        if "bg" in O.schema(name).get("properties", {}):
            props["bg"] = "dark"
    return {"type": name, "start": 0, "duration": DURATION, "props": props, "index": 0}


def main(names: list[str]) -> int:
    from shortform import Project as P  # noqa: F401  (the probe's helpers live on Project)
    names = names or sorted(O.COMPONENTS)
    tmp = Path(tempfile.mkdtemp(prefix="contrast-matrix-"))
    pub = tmp / "public"
    pub.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "gradients=s=600x800:c0=0x3a6b8c:c1=0xd9c9a3",
                    "-frames:v", "1", str(pub / "sample.png")], check=True)
    jobs, keys = [], []
    for brand, (accent, dark) in BRANDS.items():
        theme = {"colors": {**COLORS, "accent": accent}, "fonts": FONTS, "fontFiles": []}
        for name in names:
            if (dark and not dark_capable(name)) or (not dark and name in DARK_ONLY):
                continue
            e = event(name, dark)
            frame = round(still_time(name, e["props"], DURATION, FPS) * FPS)
            for tag, extra in (("text", {"measure": True}), ("blank", {"hideText": True})):
                pj = tmp / f"{brand}_{name}_{tag}.json"
                pj.write_text(json.dumps({"durationInSeconds": DURATION, "brand": theme, "events": [e], **extra}))
                jobs.append({"props": str(pj), "frame": frame, "out": str(tmp / f"{brand}_{name}_{tag}.png"), "scale": 0.5})
            keys.append((brand, name, e))
    r = subprocess.run(["node", "scripts/stills.mjs"], input=json.dumps({"publicDir": str(pub), "jobs": jobs}),
                       capture_output=True, text=True, cwd=MOTION)
    res = {Path(x["out"]).stem: x for x in map(json.loads, r.stdout.splitlines()) if x}
    failed = 0
    for brand, name, e in keys:
        text, blank = res.get(f"{brand}_{name}_text"), res.get(f"{brand}_{name}_blank")
        if not text or not blank or "error" in text or "error" in blank:
            err = (text or blank or {}).get("error", "no result")
            print(f"FAIL {name:<14} {brand:<12} render failed: {err.splitlines()[0][:160]}")
            failed += 1
            continue
        a, b = (Project._rgba(Path(x["out"])).astype(float) for x in (text, blank))
        over = lambda x: x[:, :, :3] * (x[:, :, 3:] / 255)  # noqa: E731  (on black: the backdrop is opaque)
        comp, comp0 = over(a), over(b)
        diff = (abs(comp - comp0) > PROBE_DELTA).any(axis=2)
        texts = next((m["texts"] for m in text["measure"] or []), [])
        groups = Project._text_groups(e, texts)
        low = low_contrast(comp, comp0, diff, groups, need=3.0)
        if low:
            failed += 1
            print(f"FAIL {name:<14} {brand:<12} " + ", ".join(f"{fl} {rr:.2f}:1" for rr, _, fl in sorted(low)))
        else:
            print(f"ok   {name:<14} {brand:<12} {len(groups)} text group(s)")
    print(f"{len(keys) - failed}/{len(keys)} readable at 3:1")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
