"""gen/voice.py: backend choice, the cache key per backend and the install hint. No model needed.

    uv run python -m unittest tools.tests.test_voice
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

from gen import voice as V  # noqa: E402


def on(system: str, machine: str):
    return mock.patch.multiple(V, _apple_silicon=mock.Mock(return_value=(system, machine) == ("darwin", "arm64")))


class Backend(unittest.TestCase):
    def test_auto(self):
        with on("darwin", "arm64"):
            self.assertEqual(V.pick_backend(None), "mlx")
            self.assertEqual(V.pick_backend("auto"), "mlx")
        with on("linux", "x86_64"):
            self.assertEqual(V.pick_backend(None), "torch")
        with on("linux", "aarch64"):
            self.assertEqual(V.pick_backend("torch"), "torch")
        with self.assertRaises(SystemExit):
            V.pick_backend("onnx")

    def test_mlx_off_apple(self):
        with on("linux", "x86_64"):
            self.assertIn("Apple Silicon", V.backend_missing("mlx"))

    def test_install_hint(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        with on("linux", "x86_64"), mock.patch.object(V.importlib.util, "find_spec", return_value=None):
            with self.assertRaises(SystemExit) as e:
                V.synthesize_many([V.Job(tmp / "a.wav", "Hello there.", "en")])
        self.assertIn("uv sync --group gen", str(e.exception.code))
        self.assertFalse((tmp / "a.wav").exists())


class CacheKey(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.wav = self.tmp / "line.wav"
        self.wav.write_bytes(b"RIFF")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def job(self, backend=None):
        return V.Job(self.wav, "Every scene starts with one clear idea.", "en", backend=backend)

    def test_mlx_key_unchanged(self):
        """Exactly the pre-torch key, so Mac clips and the word times keyed on them stay cached."""
        with on("darwin", "arm64"):
            self.assertEqual(self.job().key(), {
                "text": "Every scene starts with one clear idea.", "lang": "en", "preset": "af_heart",
                "speed": 1.0, "model": V.MODEL_ID, "prosody": V.PROSODY, "phonemes": None})

    def test_torch_key(self):
        with on("linux", "x86_64"):
            k = self.job().key()
        self.assertEqual((k["model"], k["backend"]), (V.TORCH_MODEL_ID, "torch"))

    def write_sidecar(self, key: dict, **extra):
        V.sidecar_path(self.wav).write_text(json.dumps({**key, **extra, "duration": 2.1, "seconds": 0.4}))

    def test_mac_sidecar_fresh_on_mac(self):
        with on("darwin", "arm64"):
            self.write_sidecar(self.job().key())  # a sidecar written before the backend field existed
            self.assertTrue(V.is_fresh(self.job()))
            self.write_sidecar(self.job().key(), backend="mlx")  # and one written now
            self.assertTrue(V.is_fresh(self.job()))

    def test_mac_clip_redone_on_linux(self):
        with on("darwin", "arm64"):
            self.write_sidecar(self.job().key(), backend="mlx")
        with on("linux", "x86_64"):
            self.assertFalse(V.is_fresh(self.job()))
            self.write_sidecar(self.job().key(), backend="torch")
            self.assertTrue(V.is_fresh(self.job()))
        with on("darwin", "arm64"):
            self.assertFalse(V.is_fresh(self.job()))  # and back: the torch clip isn't reused by mlx

    def test_forced_backend_in_key(self):
        with on("darwin", "arm64"):
            self.assertEqual(self.job("torch").key()["backend"], "torch")


class Help(unittest.TestCase):
    def test_names_model_and_licence(self):
        with on("linux", "x86_64"):
            h = V._languages_help()
        self.assertIn(V.TORCH_MODEL_ID, h)
        self.assertIn("Apache-2.0", h)
        with on("darwin", "arm64"):
            self.assertIn(V.MODEL_ID, V._languages_help())


if __name__ == "__main__":
    unittest.main()
