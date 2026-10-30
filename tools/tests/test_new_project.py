"""new_project.py --characters / --shortform: branded starters, and the conflict between them.

    uv run python -m unittest discover -s tools/tests
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import new_project  # noqa: E402


class Characters(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        shutil.copytree(TOOLS.parent / "templates", self.repo / "templates")
        (self.repo / "brands" / "acme" / "library").mkdir(parents=True)
        (self.repo / "brands" / "acme" / "brand.json").write_text("{}")
        self.patch = mock.patch.object(new_project, "REPO", self.repo)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.repo)

    def run_cli(self, *args):
        with mock.patch.object(sys, "argv", ["new_project.py", *args]), redirect_stdout(io.StringIO()):
            new_project.main()

    def test_branded_character_project(self):
        self.run_cli("acme-tips", "--brand", "acme", "--type", "generated", "--characters", "--platforms", "reels")
        edit = self.repo / "footage" / "acme-tips" / "edit"
        for d in ("keyframes", "shots", "audio"):
            self.assertTrue((edit / d).is_dir(), d)
        self.assertIn('brand="acme"', (edit / "build.py").read_text())
        sl = json.loads((edit / "shots.json").read_text())
        self.assertEqual(sl["brand"], "acme")
        self.assertEqual(sl["library"], "brands/acme/library")
        self.assertFalse((edit / "storyboard.json").exists())

    def test_conflicting_starters(self):
        with self.assertRaises(SystemExit) as e:
            self.run_cli("acme-tips", "--brand", "acme", "--type", "generated", "--characters", "--shortform")
        self.assertIn("can't be combined", str(e.exception))
        self.assertFalse((self.repo / "footage" / "acme-tips").exists())


    def test_shortform_starters(self):
        for brand in ("acme", "none"):
            self.run_cli(f"{brand}-short", "--brand", brand, "--type", "talking-head", "--shortform")
            edit = self.repo / "footage" / f"{brand}-short" / "edit"
            spec = json.loads((edit / "short.json").read_text())
            self.assertEqual(spec["brand"], brand)
            build = (edit / "build.py").read_text()
            self.assertIn('brand="acme",' if brand == "acme" else "brand=None,", build)


if __name__ == "__main__":
    unittest.main()
