"""Start a project: footage/<name>/edit/ + project.md header (brand, type, platforms, language).

    uv run tools/new_project.py acme-product-demo --brand acme --type tutorial --platforms youtube --language en
    uv run tools/new_project.py wedding-teaser --type montage --platforms reels,youtube --language es
    uv run tools/new_project.py ... --shortform     # also copy templates/shortform_build.py → edit/build.py

Without --brand the project is unbranded (neutral look; no brand's taste applies).
Raw takes go in footage/<name>/ (rename to plain ASCII first); never modify them.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TYPES = ["talking-head", "short-form", "tutorial", "interview", "podcast", "montage",
         "music-video", "motion-graphics", "captions-only", "reformat", "other"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="kebab-case, ideally <brand-or-client>-<what>, e.g. acme-launch-teaser")
    ap.add_argument("--brand", default="none", help="slug in brands/ (default: none)")
    ap.add_argument("--type", default="other", choices=TYPES)
    ap.add_argument("--platforms", default="tbd", help="comma list: youtube, reels, tiktok, shorts, linkedin, x, master")
    ap.add_argument("--language", default="tbd", help="spoken language code for transcription (es, en…)")
    ap.add_argument("--shortform", action="store_true", help="copy the short-form build.py template")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.name):
        sys.exit(f"name must be kebab-case ASCII: {a.name!r}")
    if a.brand != "none" and not (REPO / "brands" / a.brand / "brand.json").exists():
        sys.exit(f"no brand kit brands/{a.brand}/ — copy brands/_template/ and fill it in first")

    proj = REPO / "footage" / a.name
    edit = proj / "edit"
    md = edit / "project.md"
    if md.exists():
        sys.exit(f"{md} already exists — continue that project instead")
    edit.mkdir(parents=True, exist_ok=True)

    kit = f"`brands/{a.brand}/brand.md` (read before every edit)" if a.brand != "none" \
        else "none (neutral look; apply no brand's taste)"
    md.write_text((REPO / "templates" / "project.md").read_text().format(
        name=a.name, brand=a.brand, type=a.type, platforms=a.platforms, language=a.language,
        date=date.today().isoformat(), brand_kit=kit))
    if a.shortform:
        dst = edit / "build.py"
        shutil.copy2(REPO / "templates" / "shortform_build.py", dst)
        if a.brand != "none":
            dst.write_text(dst.read_text().replace("    brand=None,", f'    brand="{a.brand}",'))
    print(f"created {proj.relative_to(REPO)}/ → drop raw takes there; notes in {md.relative_to(REPO)}")


if __name__ == "__main__":
    main()
