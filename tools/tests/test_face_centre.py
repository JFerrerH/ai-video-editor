"""face_centre.py: the face centre and head box from a person matte (a synthetic matte stands in for the backend).

    uv run python -m unittest tools.tests.test_face_centre
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import face_centre as F  # noqa: E402


def fake_matte(person: str | None):
    """make_matte stand-in: a white `person` drawbox (x:y:w:h, 270-wide work frame) on black, 5 frames."""
    def make(src, start, dur, out, fps=30, backend=None):
        draw = f",drawbox={person}:color=white:t=fill" if person else ""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=270x480:r=1:d=5",
                        "-vf", f"format=gray{draw}", "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", str(out)],
                       check=True)
        return out
    return make


class HeadBox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.src = self.tmp / "take.mov"  # 1080x1920: the matte's 270-wide frame × 4
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:r=30:d=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.src)], check=True)

    def test_seated_speaker(self):
        # a person from y 100 down to the bottom edge: the head band is the top 30 % of that height
        with mock.patch.object(F, "make_matte", fake_matte("x=90:y=100:w=90:h=380")):
            r = F.suggest(self.src)
        x0, y0, x1, y1 = r["head"]
        fx, fy = r["face"]
        self.assertTrue(x0 < fx < x1 and y0 < fy < y1, r)
        self.assertEqual((x0, y0, x1), (360, 400, 720))
        self.assertAlmostEqual(y1, 400 + 0.3 * 380 * 4, delta=8)
        with mock.patch.object(F, "make_matte", fake_matte("x=90:y=100:w=90:h=380")):
            self.assertEqual(F.suggest(self.src), r)  # deterministic

    def test_no_person(self):
        with mock.patch.object(F, "make_matte", fake_matte(None)):
            r = F.suggest(self.src)
        self.assertIsNone(r["face"])
        self.assertIsNone(r["head"])


if __name__ == "__main__":
    unittest.main()
