"""Start a project: footage/<name>/edit/ + project.md header (brand, type, platforms, language).

    uv run tools/new_project.py acme-product-demo --brand acme --type tutorial --platforms youtube --language en
    uv run tools/new_project.py wedding-teaser --type montage --platforms reels,youtube --language es
    uv run tools/new_project.py ... --shortform     # also copy templates/shortform_build.py → edit/build.py
    uv run tools/new_project.py acme-explainer --type generated --platforms reels --language en
        # from scratch, no footage: copies templates/storyboard.json → edit/storyboard.json
        # (aspect from the first platform, brand filled in); render with tools/storyboard.py
    uv run tools/new_project.py acme-explainer --type generated --explainer --platforms reels --language es
        # narrated explainer: copies templates/storyboard_explainer.json instead (voice block in
        # --language; BeatScenes with headline, figure and widgets); `storyboard.py <edit> voice` first
    uv run tools/new_project.py acme-tips --brand acme --type generated --characters --platforms reels --language en
        # brand characters animated by a paid image-to-video model: copies templates/shots.json →
        # edit/shots.json and templates/character_build.py → edit/build.py; skill: character-video

Without --brand the project is unbranded (neutral look; no brand's taste applies).
Raw takes go in footage/<name>/ (rename to plain ASCII first); never modify them.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from gen import voice  # standard library only: language/preset tables

REPO = Path(__file__).resolve().parent.parent
TYPES = ["talking-head", "short-form", "tutorial", "interview", "podcast", "montage",
         "music-video", "motion-graphics", "generated", "captions-only", "reformat", "other"]
STORYBOARD_TYPES = {"generated", "motion-graphics"}  # made from scratch → start from a storyboard
ASPECT_FOR = {"reels": "9:16", "tiktok": "9:16", "shorts": "9:16", "youtube": "16:9", "master": "16:9",
              "linkedin": "4:5", "x": "1:1"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="kebab-case, ideally <brand-or-client>-<what>, e.g. acme-launch-teaser")
    ap.add_argument("--brand", default="none", help="slug in brands/ (default: none)")
    ap.add_argument("--type", default="other", choices=TYPES)
    ap.add_argument("--platforms", default="tbd", help="comma list: youtube, reels, tiktok, shorts, linkedin, x, master")
    ap.add_argument("--language", default="tbd", help="spoken language code for transcription (es, en…)")
    ap.add_argument("--shortform", action="store_true", help="copy the short-form build.py template")
    ap.add_argument("--explainer", action="store_true",
                    help="with --type generated: start from the narrated-explainer storyboard")
    ap.add_argument("--characters", action="store_true",
                    help="character video: copy the shot list and character build templates")
    a = ap.parse_args()
    if a.characters and a.shortform:
        sys.exit("--characters and --shortform can't be combined: both write edit/build.py")

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
    if a.characters:
        characters(edit, a)
    elif a.type in STORYBOARD_TYPES:
        tpl = "storyboard_explainer.json" if a.explainer else "storyboard.json"
        sb = json.loads((REPO / "templates" / tpl).read_text())
        sb["brand"] = a.brand
        sb["aspect"] = ASPECT_FOR.get(a.platforms.split(",")[0].strip(), "9:16")
        if a.explainer:
            lang = a.language.lower()
            if err := voice.validate(lang, None):
                sys.exit(f"--explainer: {err}")
            sb["voice"] = {**sb["voice"], "lang": lang, "preset": voice.default_preset(lang)}
        (edit / "storyboard.json").write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
        (edit / "images").mkdir(exist_ok=True)
        print(f"storyboard: {(edit / 'storyboard.json').relative_to(REPO)} ({sb['aspect']}); "
              f"uv run tools/storyboard.py {edit.relative_to(REPO)} {'voice' if a.explainer else 'check'}")
        if not a.explainer:
            print("  narrated explainer (voice, headline, figure, widgets)? start from "
                  "templates/storyboard_explainer.json instead: add --explainer")
    what = "shot-list driven, no footage needed" if a.characters else \
        "storyboard-driven, no footage needed" if a.type in STORYBOARD_TYPES else "drop raw takes there"
    print(f"created {proj.relative_to(REPO)}/ → {what}; notes in {md.relative_to(REPO)}")


def characters(edit: Path, a: argparse.Namespace) -> None:
    """edit/shots.json + edit/build.py from the character templates, brand and library filled in."""
    sl = json.loads((REPO / "templates" / "shots.json").read_text())
    sl["brand"] = a.brand
    sl["aspect"] = ASPECT_FOR.get(a.platforms.split(",")[0].strip(), "9:16")
    lib = REPO / "brands" / a.brand / "library"
    sl["library"] = str(lib.relative_to(REPO)) if a.brand != "none" and lib.is_dir() else None
    if a.language != "tbd":
        sl["voice"] = {"lang": a.language.lower()}
    (edit / "shots.json").write_text(json.dumps(sl, indent=2, ensure_ascii=False) + "\n")
    build = edit / "build.py"
    build.write_text((REPO / "templates" / "character_build.py").read_text().replace(
        "    brand=None,", f'    brand="{a.brand}",' if a.brand != "none" else "    brand=None,"))
    for d in ("keyframes", "shots", "audio", "images"):
        (edit / d).mkdir(exist_ok=True)
    rel = edit.relative_to(REPO)
    print(f"shots: {rel / 'shots.json'} ({sl['aspect']}); library: {sl['library'] or 'none'}")
    print(f"  next: write the lines, narrate into {rel}/audio/vo/, then uv run tools/shotcut.py {rel} --plan "
          "(skill: .claude/skills/character-video/SKILL.md)")


if __name__ == "__main__":
    main()
