"""person_matte.py: backend choice per platform and the install hint when MediaPipe is missing.

    uv run python -m unittest tools.tests.test_person_matte
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import person_matte as PM  # noqa: E402


def platform_is(system: str, swift: bool):
    return [mock.patch.object(PM.sys, "platform", system),
            mock.patch.object(PM.shutil, "which", return_value="/usr/bin/swift" if swift else None)]


class Backend(unittest.TestCase):
    def under(self, system, swift, fn, *args):
        ps = platform_is(system, swift)
        for p in ps:
            p.start()
        try:
            return fn(*args)
        finally:
            for p in ps:
                p.stop()

    def test_auto(self):
        self.assertEqual(self.under("darwin", True, PM.pick_backend, None), "vision")
        self.assertEqual(self.under("darwin", True, PM.pick_backend, "auto"), "vision")
        self.assertEqual(self.under("darwin", False, PM.pick_backend, None), "mediapipe")
        self.assertEqual(self.under("linux", False, PM.pick_backend, None), "mediapipe")

    def test_forced(self):
        self.assertEqual(self.under("darwin", True, PM.pick_backend, "mediapipe"), "mediapipe")
        self.assertEqual(self.under("linux", False, PM.pick_backend, "vision"), "vision")
        with self.assertRaises(SystemExit):
            PM.pick_backend("rvm")

    def test_vision_off_macos(self):
        self.assertIn("needs macOS", self.under("linux", True, PM.backend_missing, "vision"))
        self.assertIn("swift not found", self.under("darwin", False, PM.backend_missing, "vision"))
        self.assertIsNone(self.under("darwin", True, PM.backend_missing, "vision"))

    def test_mediapipe_install_hint(self):
        with mock.patch.object(PM.importlib.util, "find_spec", return_value=None):
            self.assertIn("uv sync --group matte", PM.backend_missing("mediapipe"))
            ps = platform_is("linux", False)
            for p in ps:
                p.start()
            try:
                with self.assertRaises(SystemExit) as e:
                    PM.make_matte(Path("in.mov"), 0.0, 1.0, Path("out.mov"))
            finally:
                for p in ps:
                    p.stop()
        self.assertIn("uv sync --group matte", str(e.exception.code))

    def test_mediapipe_installed(self):
        with mock.patch.object(PM.importlib.util, "find_spec", return_value=object()):
            self.assertIsNone(PM.backend_missing("mediapipe"))


class Windows(unittest.TestCase):
    """matte_windows: output-second windows for the behind events, padded and merged."""

    def test_two_behind_events_close_together(self):
        w = PM.matte_windows([(22.25, 24.30), (24.35, 25.00)], total=60)
        self.assertEqual(len(w), 1)
        self.assertAlmostEqual(w[0][0], 22.15, delta=1 / 30)
        self.assertAlmostEqual(w[0][1], 25.10, delta=1 / 30)
        self.assertLessEqual(w[0][0], 22.15 + 1e-6)  # snapped outward to a frame: never shorter than asked
        self.assertGreaterEqual(w[0][1], 25.10 - 1e-6)

    def test_far_apart_stay_separate(self):
        w = PM.matte_windows([(2.0, 3.0), (10.0, 11.0)], total=60)
        self.assertEqual(len(w), 2)

    def test_unordered_and_overlapping(self):
        w = PM.matte_windows([(10.0, 12.0), (2.0, 3.0), (11.0, 13.0)], total=60)
        self.assertEqual(len(w), 2)
        self.assertLessEqual(w[1][0], 9.9 + 1e-6)
        self.assertGreaterEqual(w[1][1], 13.1 - 1e-6)

    def test_clamped_to_the_video(self):
        w = PM.matte_windows([(0.04, 0.5), (59.9, 60.0)], total=60)
        self.assertEqual(w[0][0], 0.0)
        self.assertEqual(w[-1][1], 60.0)

    def test_no_events_no_windows(self):
        self.assertEqual(PM.matte_windows([], total=10), [])


class Cutout(unittest.TestCase):
    """cutout: the base with the matte as alpha, ProRes 4444, for one window."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.base = self.tmp / "base.mov"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=108x192:r=30:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.base)], check=True)

    def fake_matte(self, src, start, dur, out, fps=30, **kw):
        """Left half white (the person), right half black, for `dur` s."""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=108x192:r={fps}:d={dur}",
                        "-vf", "format=gray,drawbox=x=0:y=0:w=54:h=192:color=white:t=fill", "-c:v", "libx264", "-crf", "0",
                        "-pix_fmt", "yuv420p", str(out)], check=True)
        return out

    def test_alpha_follows_the_matte(self):
        out = self.tmp / "cut.mov"
        with mock.patch.object(PM, "make_matte", self.fake_matte):
            PM.cutout(self.base, 1.0, 1.0, out, fps=30)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames", "-show_entries",
                                          "stream=codec_name,pix_fmt,nb_read_frames,width,height", "-of", "json", str(out)],
                                         capture_output=True, text=True).stdout)["streams"][0]
        self.assertEqual(info["codec_name"], "prores")
        self.assertTrue(info["pix_fmt"].startswith("yuva444"), info["pix_fmt"])  # 4444 with alpha (decoded as 10 or 12 bit)
        self.assertEqual((info["width"], info["height"], int(info["nb_read_frames"])), (108, 192, 30))
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-frames:v", "1", "-vf", "alphaextract,format=gray",
                              "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        row = raw[96 * 108:97 * 108]
        self.assertGreater(min(row[5:50]), 240)  # the person: opaque
        self.assertLess(max(row[60:105]), 15)  # the wall: transparent


if __name__ == "__main__":
    unittest.main()
