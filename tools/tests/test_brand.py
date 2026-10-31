"""brand.py: how a kit (or no brand) becomes the Remotion theme.

    uv run python -m unittest tools.tests.test_brand
"""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import brand as B  # noqa: E402


class LoadBrand(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        saved = B.BRANDS
        B.BRANDS = self.root
        self.addCleanup(setattr, B, "BRANDS", saved)

    def kit(self, data: dict, files=("A.ttf", "B.ttf")):
        d = self.root / "acme"
        (d / "fonts").mkdir(parents=True, exist_ok=True)
        for f in files:
            (d / "fonts" / f).write_bytes(b"x")
        (d / "brand.json").write_text(json.dumps(data))
        return B.load_brand("acme")

    def test_weights_become_strings(self):
        k = self.kit({"fontFiles": [{"family": "Brand Sans", "file": "A.ttf", "weight": 300},
                                    {"family": "Brand Sans", "file": "B.ttf", "style": "italic"}]})
        a, b = k.theme["fontFiles"]
        self.assertEqual(a["weight"], "300")
        self.assertNotIn("weight", b)
        self.assertEqual(b["style"], "italic")

    def test_range_and_string_weights_unchanged(self):
        k = self.kit({"fontFiles": [{"family": "V", "file": "A.ttf", "weight": "100 800"},
                                    {"family": "S", "file": "B.ttf", "weight": "400"}]})
        self.assertEqual([f["weight"] for f in k.theme["fontFiles"]], ["100 800", "400"])

    def test_missing_role_uses_kit_sans(self):
        k = self.kit({"fonts": {"sans": "Brand Sans", "mono": "Brand Mono"}})
        self.assertEqual(k.theme["fonts"], {"serif": "Brand Sans", "sans": "Brand Sans", "mono": "Brand Mono"})

    def test_font_files_only(self):
        k = self.kit({"fontFiles": [{"family": "Brand Sans", "file": "A.ttf"}]})
        self.assertEqual(k.theme["fonts"], {"serif": "Brand Sans", "sans": "Brand Sans", "mono": "Brand Sans"})

    def test_all_roles_set(self):
        roles = {"serif": "Brand Serif", "sans": "Brand Sans", "mono": "Brand Mono"}
        self.assertEqual(self.kit({"fonts": roles}).theme["fonts"], roles)

    def test_no_font_at_all_is_neutral(self):
        self.assertEqual(self.kit({"colors": {"accent": "#000000"}}).theme["fonts"], B.NEUTRAL["fonts"])

    def test_no_brand(self):
        k = B.load_brand("none")
        self.assertEqual((k.slug, k.theme["fonts"], k.theme["fontFiles"]), (None, B.NEUTRAL["fonts"], []))
        self.assertEqual(B.load_brand(None).theme, k.theme)


class Neutral(unittest.TestCase):
    def test_matches_default_brand(self):
        """NEUTRAL and `defaultBrand` in theme.ts stay the same look."""
        ts = (TOOLS / "motion" / "src" / "theme.ts").read_text()
        block = ts[ts.index("export const defaultBrand"):]
        block = block[:block.index("\n};")]
        for role, value in B.NEUTRAL["fonts"].items():
            self.assertIn(f"{role}: '{value}',", block, role)
        for role, value in B.NEUTRAL["colors"].items():
            self.assertRegex(block, rf'{role}: "{re.escape(value)}"', role)

    def test_neutral_lists_end_in_linux_faces(self):
        for role, noto in (("serif", "Noto Serif"), ("sans", "Noto Sans"), ("mono", "Noto Sans Mono")):
            parts = [p.strip().strip('"') for p in B.NEUTRAL["fonts"][role].split(",")]
            self.assertEqual(parts[1:], [noto, {"serif": "serif", "sans": "sans-serif", "mono": "monospace"}[role]])


if __name__ == "__main__":
    unittest.main()
