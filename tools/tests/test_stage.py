"""shortform.stage: copying public files (brand fonts, assets) into edit/motion_public.

    uv run python -m unittest tools.tests.test_stage
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

from shortform import stage  # noqa: E402


class Stage(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d)
        self.src, self.dst = self.d / "kit" / "Brand.ttf", self.d / "public" / "fonts" / "Brand.ttf"
        self.src.parent.mkdir()
        self.src.write_bytes(b"kit font")

    def test_copies_then_skips_unchanged(self):
        stage(self.src, self.dst)
        self.assertEqual(self.dst.read_bytes(), b"kit font")
        ino = self.dst.stat().st_ino
        stage(self.src, self.dst)
        self.assertEqual(self.dst.stat().st_ino, ino)  # not copied again

    def test_newer_different_file_is_replaced(self):
        """Another kit's font staged under the same name, more recently than this kit's file."""
        self.dst.parent.mkdir(parents=True)
        self.dst.write_bytes(b"other kit's font, newer")
        later = time.time() + 60
        os.utime(self.dst, (later, later))
        stage(self.src, self.dst)
        self.assertEqual(self.dst.read_bytes(), b"kit font")

    def test_changed_source_is_restaged(self):
        stage(self.src, self.dst)
        self.src.write_bytes(b"kit font v2")
        stage(self.src, self.dst)
        self.assertEqual(self.dst.read_bytes(), b"kit font v2")


if __name__ == "__main__":
    unittest.main()
