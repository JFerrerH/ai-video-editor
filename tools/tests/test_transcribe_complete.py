"""Transcription completeness on synthetic takes with a known script (tools/tests/synthetic_takes.py).

Runs the platform's default backend (mlx on Apple Silicon, faster-whisper in the container). Skipped
when the local voice tool (`uv sync --group gen`) or the backend is missing.

    uv run python -m unittest tools.tests.test_transcribe_complete
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))

import synthetic_takes as ST  # noqa: E402
import transcribe_local as T  # noqa: E402

BACKEND = T.pick_backend(None)
READY = T.backend_missing(BACKEND) is None and ST.available()


@unittest.skipUnless(READY, "needs the local voice tool (uv sync --group gen) and a transcription backend")
class Complete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def transcribe(self, lang: str, language: str | None, name: str) -> dict:
        wav, _ = ST.build(lang)
        src = self.tmp / f"{name}.wav"
        shutil.copy(wav, src)
        out = T.transcribe_one(src, self.tmp / "edit", None, language, 0, BACKEND)
        return json.loads(out.read_text())

    def check_complete(self, lang: str):
        res = self.transcribe(lang, lang, f"{lang}_complete")
        s = ST.score(res["words"], ST.SCRIPTS[lang][0] + ST.SCRIPTS[lang][1])
        self.assertGreaterEqual(s["recall"], 0.95, s)
        self.assertEqual(s["ends"], s["sentences"], s)
        self.assertEqual(res["untranscribed"], [])
        return res

    def test_english_take(self):
        self.check_complete("en")

    def test_spanish_take(self):
        self.check_complete("es")

    def test_spanish_detected(self):
        res = self.transcribe("es", None, "es_detect")
        self.assertEqual(res["language_detected"], "es")
        self.assertEqual(res["language_code"], "es")
        first = next(w for w in res["words"] if w["type"] == "word")
        self.assertLessEqual(abs(first["start"] - ST.LEAD), 1.0, first)

    def test_explicit_language_skips_detection(self):
        res = self.transcribe("es", "es", "es_explicit")
        self.assertNotIn("language_detected", res)


if __name__ == "__main__":
    unittest.main()
