"""person_matte.py: backend choice per platform and the install hint when MediaPipe is missing.

    uv run python -m unittest tools.tests.test_person_matte
"""

import sys
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


if __name__ == "__main__":
    unittest.main()
