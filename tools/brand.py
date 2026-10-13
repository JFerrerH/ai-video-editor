"""Brand kits: `brands/<slug>/brand.json` (machine-readable) next to `brand.md` (taste + rules).

    from brand import load_brand
    kit = load_brand("acme")         # brands/acme/ ; None → neutral defaults
    kit.theme          # Remotion `brand` prop: {colors, fonts, fontFiles[{family, url, weight, style}]}
    kit.public_files   # {"fonts/<file>": Path} to stage into the Remotion public dir
    kit.caption_props  # brand caption overrides (size, emphSize, emphColor, top…)

brand.json:
    {"name", "colors": {bg, tint1, tint2, ink, muted, accent, success},
     "fonts": {serif, sans, mono}, "fontFiles": [{family, file, weight?, style?}],
     "captions": {size?, emphSize?, emphColor?, top?}}
Font `file`s live in `brands/<slug>/fonts/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRANDS = REPO / "brands"

# Mirrors `defaultBrand` in tools/motion/src/theme.ts: a plain look that belongs to no one.
NEUTRAL = {
    "colors": {"bg": "#F4F4F2", "tint1": "#E4E4E0", "tint2": "#D9DEE4", "ink": "#1A1A1A",
               "muted": "#6B6B6B", "accent": "#D64545", "success": "#2F7D5B"},
    "fonts": {"serif": "Georgia", "sans": "Helvetica Neue", "mono": "Menlo"},
}


@dataclass
class BrandKit:
    slug: str | None
    theme: dict
    public_files: dict[str, Path] = field(default_factory=dict)
    caption_props: dict = field(default_factory=dict)

    @property
    def guide(self) -> Path | None:
        """The brand's `brand.md` (taste rules Claude reads before editing)."""
        return BRANDS / self.slug / "brand.md" if self.slug else None


def load_brand(slug: str | None) -> BrandKit:
    if not slug or slug == "none":
        return BrandKit(None, {**NEUTRAL, "fontFiles": []})
    d = BRANDS / slug
    if not (d / "brand.json").exists():
        raise FileNotFoundError(f"no brand kit at {d}/brand.json (copy brands/_template/)")
    raw = json.loads((d / "brand.json").read_text())
    font_files, public = [], {}
    for f in raw.get("fontFiles", []):
        src = d / "fonts" / f["file"]
        if not src.exists():
            raise FileNotFoundError(f"brand font missing: {src}")
        name = f"fonts/{f['file']}"
        public[name] = src
        font_files.append({"family": f["family"], "url": name,
                           **{k: f[k] for k in ("weight", "style") if k in f}})
    theme = {"colors": {**NEUTRAL["colors"], **raw.get("colors", {})},
             "fonts": {**NEUTRAL["fonts"], **raw.get("fonts", {})},
             "fontFiles": font_files}
    return BrandKit(slug, theme, public, dict(raw.get("captions", {})))
