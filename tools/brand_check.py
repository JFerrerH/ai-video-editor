"""Validate a brand kit's new files and its brand.json before any render uses them.

    uv run tools/brand_check.py brands/<slug>       # checks brands/<slug>/incoming/* and brand.json

Fonts move into fonts/ (WOFF/WOFF2 unwrapped), images and SVGs into logos/ as PNG; invalid files
are deleted. Prints the same JSON the `brand` job op returns (`files`, `errors`); exits 1 when
brand.json has errors. Rules: tools/brand_files.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brand_files import check_dir  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="the kit directory, e.g. brands/acme")
    a = ap.parse_args()
    if not a.dir.is_dir():
        sys.exit(f"not a directory: {a.dir}")
    res = check_dir(a.dir)
    for f in res["files"]:
        detail = f.get("stored") if f["status"] == "valid" else f.get("reason")
        print(f"  {f['status']:<8} {f['name']}: {detail}", file=sys.stderr)
    for e in res["errors"]:
        print(f"  ERROR    {e}", file=sys.stderr)
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
