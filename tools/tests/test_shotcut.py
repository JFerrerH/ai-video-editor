"""Base-take cut on synthetic clips: timeline maths, too-short clips, end card, library shots. ffmpeg only.

    uv run python -m unittest discover -s tools/tests
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
sys.path.insert(0, str(TOOLS / "gen"))

import shotcut  # noqa: E402
import shotlist  # noqa: E402
from sheets import duration, size  # noqa: E402


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def clip(path: Path, secs: float, colour: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    ff("-f", "lavfi", "-i", f"color=c={colour}:s=768x1344:r=24:d={secs}", "-pix_fmt", "yuv420p", str(path))


def vo(path: Path, secs: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    ff("-f", "lavfi", "-i", f"sine=f=300:d={secs}", "-ac", "1", "-ar", "48000", str(path))
    path.with_suffix(".json").write_text(json.dumps({"duration": secs}))


class ShotCut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        e, lib = cls.dir / "edit", cls.dir / "lib"
        clip(e / "shots" / "a.mp4", 3.0, "red")
        clip(lib / "clips" / "lib_b.mp4", 3.0, "blue")
        (lib / "index.json").parent.mkdir(parents=True, exist_ok=True)
        (lib / "index.json").write_text(json.dumps([{"id": "lib_b", "file": "clips/lib_b.mp4"}]))
        vo(e / "audio" / "vo" / "a.wav", 2.40)
        vo(e / "audio" / "vo" / "b.wav", 1.00)  # short line → minimum shot length
        ff("-f", "lavfi", "-i", "color=c=green:s=1080x1920", "-frames:v", "1", str(e / "end.png"))
        (e / "shots.json").write_text(json.dumps({"library": str(lib), "shots": [
            {"id": "a", "line": "first", "cast": [], "motion": "m", "camera": "c"},
            {"id": "b", "line": "second", "library": "lib_b"}]}))
        cls.edit = e

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def sl(self):
        return shotlist.ShotList(self.edit / "shots.json")

    def test_timeline_matches_narration(self):
        tl = shotcut.timeline(self.sl(), self.edit, self.edit / "audio" / "vo")
        self.assertAlmostEqual(tl[0]["dur"], 2.80, delta=1 / 30)
        self.assertAlmostEqual(tl[0]["voice_start"] - tl[0]["start"], 0.15, places=3)
        self.assertEqual(tl[1]["dur"], 2.0)  # 1.0 + 0.4 < 2.0 minimum
        self.assertTrue(tl[1]["source"].startswith("library:"))
        self.assertAlmostEqual(tl[1]["start"], tl[0]["dur"], places=3)

    def test_too_short_clip(self):
        vo(self.edit / "audio" / "long" / "a.wav", 3.5)
        vo(self.edit / "audio" / "long" / "b.wav", 1.0)
        with self.assertRaises(SystemExit) as e:
            shotcut.timeline(self.sl(), self.edit, self.edit / "audio" / "long", need_clips=True)
        msg = str(e.exception)
        self.assertIn("shot a", msg)
        self.assertIn("3.90", msg)
        self.assertIn("3.00", msg)
        self.assertIn("--dur fit", msg)

    def test_render_with_end_card(self):
        tl = shotcut.timeline(self.sl(), self.edit, self.edit / "audio" / "vo", need_clips=True)
        out = self.edit / "base.mov"
        shotcut.render(tl, out, None, -20, self.edit / "end.png", 3.0)
        want = tl[-1]["start"] + tl[-1]["dur"] + 3.0
        self.assertAlmostEqual(duration(out), want, delta=1 / 30 + 0.01)
        self.assertEqual(size(out), (1080, 1920))
        last = subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-0.1", "-i", str(out), "-frames:v", "1", "-vf",
                               "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True,
                              check=True).stdout
        r, g, b = last[:3]
        self.assertTrue(g > 100 and r < 40 and b < 40, (r, g, b))  # the green end card

    def test_render_with_music(self):
        music = self.edit / "music.wav"
        ff("-f", "lavfi", "-i", "sine=f=100:d=1.5", "-ac", "2", str(music))  # shorter than the take: looped
        tl = shotcut.timeline(self.sl(), self.edit, self.edit / "audio" / "vo", need_clips=True)
        out = self.edit / "base_music.mov"
        shotcut.render(tl, out, music, -20, None, 3.0)
        self.assertAlmostEqual(duration(out), tl[-1]["start"] + tl[-1]["dur"], delta=1 / 30 + 0.01)


if __name__ == "__main__":
    unittest.main()
