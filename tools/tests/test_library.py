"""Clip library: index entries with measured durations, import from a project, lookup by tag. ffmpeg only.

    uv run python -m unittest discover -s tools/tests
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gen"))

import library  # noqa: E402
import shotlist  # noqa: E402
from sheets import duration  # noqa: E402


def clip(path: Path, secs: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=96x168:r=24:d={secs}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


class Library(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.lib = self.repo / "brands" / "acme" / "library"
        clip(self.lib / "clips" / "hero_idle.mp4", 2.5)
        (self.lib / "spec.json").write_text(json.dumps({"clips": [
            {"id": "hero_idle", "cast": ["hero"], "mood": "neutral", "use": "intro, any line",
             "motion": "breathes", "camera": "push in"},
            {"id": "hero_happy", "cast": ["hero"], "mood": "happy", "use": "payoff", "motion": "jumps",
             "camera": "crane up"}]}))
        edit = self.repo / "footage" / "acme-tips" / "edit"
        clip(edit / "shots" / "s05_reveal.mp4", 3.2)
        (edit / "shots.json").write_text(json.dumps({"shots": [
            {"id": "s05_reveal", "line": "x", "cast": ["hero", "guide"], "motion": "opens the door",
             "camera": "dolly in"}]}))
        self.patch = mock.patch.object(library, "REPO", self.repo)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.repo)

    def test_index_measures_and_skips_ungenerated(self):
        idx = library.index(self.lib, shotlist.ShotList(self.lib / "spec.json"))
        self.assertEqual([e["id"] for e in idx], ["hero_idle"])
        self.assertAlmostEqual(idx[0]["dur"], duration(self.lib / "clips" / "hero_idle.mp4"), delta=0.01)
        self.assertEqual(idx[0]["source"], "library")
        self.assertEqual(set(idx[0]), {"id", "file", "cast", "mood", "use", "action", "camera", "dur", "source"})

    def test_import_and_refuse_duplicate(self):
        e = library.import_shot(self.lib, "acme-tips", "s05_reveal", "reveal_doorway", mood="warm", use="reveal")
        self.assertTrue((self.lib / "clips" / "reveal_doorway.mp4").exists())
        self.assertEqual(e["source"], "acme-tips")
        self.assertEqual(e["cast"], ["hero", "guide"])
        self.assertIn("reveal_doorway", [x["id"] for x in library.read_index(self.lib)])
        with self.assertRaises(SystemExit):
            library.import_shot(self.lib, "acme-tips", "s05_reveal", "reveal_doorway", mood="warm", use="reveal")

    def cli(self, *args) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["library.py", "acme", *args]), redirect_stdout(buf), \
                mock.patch.object(library.fal, "client", side_effect=AssertionError("network")):
            library.main()
        return buf.getvalue()

    def test_incremental_add_one_request_per_step(self):
        (self.repo / "brands" / "acme" / "brand.json").write_text("{}")
        (self.lib / "hero.png").write_bytes(b"png")
        spec = json.loads((self.lib / "spec.json").read_text())
        spec["cast"] = {"hero": {"ref": "hero.png", "desc": "the hero"}}
        for c in spec["clips"]:
            c["frame"] = "HERO in the room."
        (self.lib / "spec.json").write_text(json.dumps(spec))
        (self.lib / "keyframes").mkdir(exist_ok=True)
        (self.lib / "keyframes" / "hero_idle.png").write_bytes(b"png")  # generated before; hero_happy is new
        self.assertIn("plan: 1 request ", self.cli("keyframes", "--dry-run"))
        (self.lib / "keyframes" / "hero_happy.png").write_bytes(b"png")
        out = self.cli("clips", "--dry-run")
        self.assertIn("kept: hero_idle.mp4", out)
        self.assertIn("hero_happy: 5s", out)
        self.assertIn("plan: 1 request ", out)

    def test_filter(self):
        rows = [{"cast": ["hero"], "mood": "happy", "use": "payoff"}, {"cast": ["hero"], "mood": "sad", "use": "x"},
                {"cast": ["guide"], "mood": "happy", "use": "payoff"}]
        self.assertEqual([r for r in rows if library.matches(r, "hero", "happy", None)], [rows[0]])
        self.assertEqual(len([r for r in rows if library.matches(r, None, None, "PAY")]), 2)


if __name__ == "__main__":
    unittest.main()
