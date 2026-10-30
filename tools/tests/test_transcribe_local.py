"""transcribe_local.py: backend choice per platform and the faster-whisper → Scribe adapter.

    uv run python -m unittest tools.tests.test_transcribe_local
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import transcribe_local as T  # noqa: E402


def platform_is(system: str, machine: str):
    return [mock.patch.object(T.sys, "platform", system), mock.patch.object(T.platform, "machine", return_value=machine)]


class Backend(unittest.TestCase):
    def pick(self, system, machine, requested=None):
        ps = platform_is(system, machine)
        for p in ps:
            p.start()
        try:
            return T.pick_backend(requested)
        finally:
            for p in ps:
                p.stop()

    def test_auto(self):
        self.assertEqual(self.pick("darwin", "arm64"), "mlx")
        self.assertEqual(self.pick("darwin", "arm64", "auto"), "mlx")
        self.assertEqual(self.pick("linux", "x86_64"), "faster-whisper")
        self.assertEqual(self.pick("linux", "aarch64"), "faster-whisper")
        self.assertEqual(self.pick("darwin", "x86_64"), "faster-whisper")

    def test_forced(self):
        self.assertEqual(self.pick("darwin", "arm64", "faster-whisper"), "faster-whisper")
        self.assertEqual(self.pick("linux", "x86_64", "mlx"), "mlx")
        with self.assertRaises(SystemExit):
            self.pick("linux", "x86_64", "whisper.cpp")

    def test_mlx_on_linux_names_the_alternative(self):
        ps = platform_is("linux", "x86_64") + [mock.patch.object(T.importlib.util, "find_spec", return_value=object())]
        for p in ps:
            p.start()
        try:
            with self.assertRaises(SystemExit) as e:
                T.require_backend("mlx")
        finally:
            for p in ps:
                p.stop()
        self.assertIn("Apple Silicon", str(e.exception.code))
        self.assertIn("--backend faster-whisper", str(e.exception.code))

    def test_missing_install_hint(self):
        with mock.patch.object(T.importlib.util, "find_spec", return_value=None), \
             mock.patch.object(T, "_apple_silicon", return_value=False):
            with self.assertRaises(SystemExit) as e:
                T.require_backend("faster-whisper")
        self.assertIn("uv sync --group asr", str(e.exception.code))

    def test_model_for(self):
        self.assertEqual(T.model_for("mlx", None), T.DEFAULT_MODEL)
        self.assertEqual(T.model_for("faster-whisper", T.DEFAULT_MODEL), T.BACKENDS["faster-whisper"][0])
        self.assertEqual(T.model_for("faster-whisper", "small"), "small")


class Adapter(unittest.TestCase):
    def test_segments_to_scribe(self):
        w = lambda word, s, e, p=0.9: NS(word=word, start=s, end=e, probability=p)  # noqa: E731
        segs = [NS(text=" Hola, qué tal.", words=[w(" Hola,", 0.1, 0.5), w(" qué", 0.5, 0.7), w(" tal.", 0.9, 1.2)]),
                NS(text=" Bien.", words=[w(" ", 1.2, 1.2), w(" Bien.", 1.6, 2.0)])]
        res = T.faster_whisper_result(iter(segs), NS(language="es"))
        self.assertEqual(res["language"], "es")
        self.assertEqual(res["text"].strip(), "Hola, qué tal. Bien.")
        words = T.to_scribe_words(res)
        self.assertEqual([x["text"] for x in words], ["Hola,", "qué", " ", "tal.", " ", "Bien."])
        gap = words[2]
        self.assertEqual((gap["type"], gap["start"], gap["end"]), ("spacing", 0.7, 0.9))
        self.assertTrue(all(x["start"] <= x["end"] and x["speaker_id"] == "speaker_0" for x in words))
        self.assertEqual(words[0]["logprob"], 0.9)


if __name__ == "__main__":
    unittest.main()
