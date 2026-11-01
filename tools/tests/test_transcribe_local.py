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


def result(*words) -> dict:
    """A Whisper result (mlx-whisper's shape) holding (text, start, end[, probability]) words."""
    return {"segments": [{"words": [{"word": f" {w[0]}", "start": w[1], "end": w[2],
                                     "probability": w[3] if len(w) > 3 else 0.9} for w in words]}]}


def scribe(*words) -> list[dict]:
    return T.to_scribe_words(result(*words))


class Holes(unittest.TestCase):
    """Speech that no word covers is re-transcribed alone (a stubbed backend stands in for Whisper)."""

    def stub(self, words_by_window):
        calls = []

        def retranscribe(lo, hi):
            calls.append((lo, hi))
            return result(*[(t, a - lo, b - lo) for t, a, b in words_by_window if lo <= a <= hi])
        return retranscribe, calls

    def test_hole_filled(self):
        spoken = [(f"w{i}", i + 0.6, i + 0.9) for i in range(0, 40)]  # one word a second, speech 0.5–40
        first = scribe(*[w for w in spoken if w[1] >= 30])  # the backend dropped 0–30 s
        retranscribe, calls = self.stub(spoken)
        words, patched, untranscribed = T.fill_holes(first, [(0.5, 40.0)], retranscribe, 41.0)
        self.assertEqual(len(calls), 1)
        self.assertLess(calls[0][0], 0.6)
        got = [w for w in words if w["type"] == "word"]
        self.assertEqual([w["text"] for w in got], [w[0] for w in spoken])
        self.assertTrue(all(a["start"] <= b["start"] and a["end"] <= b["start"] for a, b in zip(got, got[1:])))
        gaps = [w for w in words if w["type"] == "spacing"]
        self.assertEqual(len(gaps), len(got) - 1)  # spacing rebuilt between every pair
        self.assertEqual(len(patched), 1)
        self.assertLessEqual(patched[0]["from"], 0.6)
        self.assertGreaterEqual(patched[0]["to"], 29.0)
        self.assertEqual(patched[0]["words"], 30)
        self.assertEqual(untranscribed, [])

    def test_stray_words_dont_hide_a_hole(self):
        spoken = [("a", 0.1, 0.3), ("b", 0.4, 0.6), ("c", 0.7, 30.0)] + [(f"w{i}", i + 0.2, i + 0.6) for i in range(1, 40)]
        first = scribe(spoken[0], spoken[1], spoken[2], *[w for w in spoken[3:] if w[1] >= 32])
        retranscribe, calls = self.stub([w for w in spoken[3:] if w[1] < 32])
        words, patched, _ = T.fill_holes(first, [(0.0, 40.0)], retranscribe, 40.0)
        self.assertEqual(len(patched), 1)
        self.assertLess(patched[0]["from"], 2.6)  # "c" covers only its first 1.5 s
        self.assertGreater(patched[0]["to"], 31.0)

    def test_unintelligible_run_reported(self):
        first = scribe(("hello", 0.5, 1.0), ("world", 10.0, 10.5))
        retranscribe, calls = self.stub([])  # Whisper hears nothing in 4–7 s, twice
        words, patched, untranscribed = T.fill_holes(first, [(0.4, 1.1), (4.0, 7.0), (9.9, 10.6)], retranscribe, 11.0)
        self.assertEqual(patched, [])
        self.assertEqual(untranscribed, [[4.0, 7.0]])
        self.assertEqual(len(calls), 1)

    def test_hallucination_dropped(self):
        first = scribe(("hello", 0.5, 1.0))
        retranscribe, _ = self.stub([("Subtítulos", 3.0, 3.5), ("por", 3.5, 3.7), ("Amara.org", 3.7, 4.2)])
        words, patched, untranscribed = T.fill_holes(first, [(0.4, 1.1), (2.5, 5.0)], retranscribe, 6.0)
        self.assertEqual(patched, [])
        self.assertEqual(untranscribed, [[2.5, 5.0]])
        self.assertEqual([w["text"] for w in words if w["type"] == "word"], ["hello"])

    def test_thank_you_over_music_dropped(self):
        first = scribe(("hello", 0.5, 1.0))
        retranscribe, _ = self.stub([("Thank", 9.0, 9.3), ("you.", 9.3, 9.6), ("I", 26.0, 26.2)])
        _, patched, untranscribed = T.fill_holes(first, [(0.4, 1.1), (8.6, 27.5)], retranscribe, 30.0)
        self.assertEqual(patched, [])
        self.assertEqual(untranscribed, [[8.6, 27.5]])

    def test_short_gaps_are_not_holes(self):
        first = scribe(("uno", 0.5, 0.9), ("dos", 2.0, 2.4))
        self.assertEqual(T.uncovered(first, [(0.5, 2.4)]), [])  # 0.9 → 2.0 is under MIN_HOLE once padded

    def test_no_prompt_for_other_languages(self):
        self.assertIsNone(T.prompt_for("mlx", "fr"))
        self.assertIsNone(T.prompt_for("mlx", None))


if __name__ == "__main__":
    unittest.main()
