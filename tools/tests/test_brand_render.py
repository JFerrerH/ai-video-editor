"""Brand fonts through a real Remotion still (EndCard via Overlay), with the fixture fonts.

    uv run python -m unittest tools.tests.test_brand_render

Skipped when tools/motion has no node_modules. About 5 s per still. On Linux it also checks that the
unbranded still uses Noto, not the browser's default serif.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import brand as B  # noqa: E402

MOTION = TOOLS / "motion"
FIXTURE_FONTS = TOOLS / "tests" / "fixtures" / "fonts"
KIT = {"fonts": {"sans": "Outfit", "mono": "Red Hat Mono"},  # no serif: the headline falls back to sans
       "fontFiles": [{"family": "Outfit", "file": "Outfit-VF.ttf", "weight": 400},
                     {"family": "Barlow", "file": "Barlow-Light.ttf", "weight": 300},
                     {"family": "Red Hat Mono", "file": "RedHatMono-VF.ttf", "weight": 400}]}


@unittest.skipUnless((MOTION / "node_modules").is_dir() and shutil.which("npx"), "Remotion not installed")
class BrandStill(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        saved = B.BRANDS
        B.BRANDS = self.tmp / "brands"
        self.addCleanup(setattr, B, "BRANDS", saved)
        fonts = B.BRANDS / "kit" / "fonts"
        fonts.mkdir(parents=True)
        for f in ("outfit/Outfit-VF.ttf", "barlow/Barlow-Light.ttf", "redhatmono/RedHatMono-VF.ttf"):
            shutil.copy(FIXTURE_FONTS / f, fonts)
        (fonts.parent / "brand.json").write_text(json.dumps(KIT))

    def still(self, slug: str, name: str, fonts: dict | None = None) -> subprocess.CompletedProcess:
        kit = B.load_brand(slug)
        theme = {**kit.theme, **({"fonts": fonts} if fonts else {})}
        pub = self.tmp / f"public_{name}"
        for rel, src in kit.public_files.items():
            (pub / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, pub / rel)
        pub.mkdir(exist_ok=True)
        props = pub / "props.json"
        props.write_text(json.dumps({"durationInSeconds": 4, "brand": theme, "events": [
            {"type": "EndCard", "start": 0, "duration": 4,
             "props": {"full": True, "title": "Hamburg 0123", "tagline": "Tagline Rgafy", "url": "example.com/abc"}}]}))
        return subprocess.run(["npx", "remotion", "still", "Overlay", str(self.tmp / f"{name}.png"), f"--props={props}",
                               f"--public-dir={pub}", "--frame=90", "--scale=0.25", "--log=error"],
                              cwd=MOTION, capture_output=True, text=True)

    def test_numeric_weights_render(self):
        r = self.still("kit", "kit")
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertEqual([f.get("weight") for f in B.load_brand("kit").theme["fontFiles"]], ["400", "300", "400"])

    def test_unloadable_font_names_the_entry(self):
        (B.BRANDS / "kit" / "fonts" / "Outfit-VF.ttf").write_bytes(bytes(range(256)) * 400)
        r = self.still("kit", "broken")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Font did not load: normal 400 "Outfit" (Outfit-VF.ttf)', r.stdout + r.stderr)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Noto is the Linux image's face")
    def test_unbranded_linux_uses_noto(self):
        for name, fonts in (("none", None),
                            ("noto", {"serif": "Noto Serif", "sans": "Noto Sans", "mono": "Noto Sans Mono"}),
                            ("lib", dict.fromkeys(("serif", "sans", "mono"), "Liberation Serif"))):
            r = self.still("none", name, fonts)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        png = lambda n: (self.tmp / f"{n}.png").read_bytes()  # noqa: E731
        self.assertEqual(png("none"), png("noto"))
        self.assertNotEqual(png("none"), png("lib"))


if __name__ == "__main__":
    unittest.main()
