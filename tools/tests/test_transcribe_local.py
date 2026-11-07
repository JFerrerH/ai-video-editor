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
        # "c" (0.7–30 s over speech) is implausible: replaced, and the rest of the stretch is a hole
        self.assertEqual([p.get("replaced") for p in patched], ["c", None])
        self.assertLess(min(p["from"] for p in patched), 2.6)
        self.assertGreater(max(p["to"] for p in patched), 31.0)
        self.assertNotIn("c", [w["text"] for w in words if w["type"] == "word"])

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

    def test_real_sentence_with_listed_phrase_kept(self):
        first = scribe(("hello", 0.5, 1.0))
        said = "okay so thank you all for coming today".split()
        retranscribe, _ = self.stub([(t, 3.0 + 0.3 * i, 3.25 + 0.3 * i) for i, t in enumerate(said)])
        words, patched, untranscribed = T.fill_holes(first, [(0.4, 1.1), (2.8, 5.6)], retranscribe, 6.0)
        self.assertEqual(len(patched), 1)
        self.assertEqual(untranscribed, [])
        self.assertIn("thank", [w["text"] for w in words if w["type"] == "word"])

    def test_listed_phrases_match_whole_words(self):
        self.assertFalse(T._hallucination([{"text": "musical"}, {"text": "theatre"}]))
        self.assertFalse(T._hallucination([{"text": "I"}, {"text": "subscribed"}, {"text": "today"}]))
        self.assertTrue(T._hallucination([{"text": "Music"}, {"text": "music."}]))

    def test_short_gaps_are_not_holes(self):
        first = scribe(("uno", 0.5, 0.9), ("dos", 2.0, 2.4))
        self.assertEqual(T.uncovered(first, [(0.5, 2.4)]), [])  # 0.9 → 2.0 is under MIN_HOLE once padded

    def test_short_hole(self):
        # 0.8 s of speech (2.0–2.8) clear of both words' cover: re-transcribed; nothing back → untranscribed
        first = scribe(("uno", 0.5, 0.9), ("dos", 3.9, 4.3))
        retranscribe, calls = self.stub([])
        _, patched, untranscribed = T.fill_holes(first, [(0.5, 0.9), (2.0, 2.8), (3.9, 4.3)], retranscribe, 5.0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(patched, [])
        self.assertEqual(untranscribed, [[2.0, 2.8]])


class Implausible(unittest.TestCase):
    """A word Whisper stretched over speech it never transcribed is re-transcribed and replaced."""

    said = "the first would be to drop the fear of… the first would be".split()

    def stub(self, words):
        calls = []

        def retranscribe(lo, hi):
            calls.append((lo, hi))
            return result(*[(t, a - lo, b - lo) for t, a, b in words if lo <= a <= hi])
        return retranscribe, calls

    def test_folded_false_start(self):
        first = scribe(("so", 37.9, 38.3), ("remove", 38.68, 42.34), ("the", 42.6, 42.8), ("fear.", 42.8, 43.2))
        spoken = [(t, 38.70 + 0.28 * i, 38.70 + 0.28 * i + 0.22) for i, t in enumerate(self.said)]
        retranscribe, calls = self.stub([("so", 37.9, 38.3), *spoken, ("the", 42.6, 42.8)])
        words, patched, untranscribed = T.fill_holes(first, [(37.9, 43.2)], retranscribe, 50.0)
        got = [w for w in words if w["type"] == "word"]
        self.assertNotIn("remove", [w["text"] for w in got])
        inside = [w["text"] for w in got if 38.68 <= w["start"] and w["end"] <= 42.34]
        self.assertEqual(inside, self.said)
        self.assertEqual([w["text"] for w in got].count("so"), 1)  # the neighbours aren't duplicated
        self.assertTrue(all(a["start"] <= b["start"] and a["end"] <= b["start"] for a, b in zip(got, got[1:])))
        rep = [p for p in patched if p.get("replaced") == "remove"]
        self.assertEqual(len(rep), 1, patched)
        self.assertEqual((rep[0]["from"], rep[0]["to"], rep[0]["words"]), (38.68, 42.34, len(self.said)))
        self.assertEqual(untranscribed, [])

    def test_long_word_that_is_real(self):
        first = scribe(("wonderful", 1.0, 2.1))  # 9 letters: limit 1.48 s
        retranscribe, calls = self.stub([])
        words, patched, _ = T.fill_holes(first, [(1.0, 2.1)], retranscribe, 3.0)
        self.assertEqual(calls, [])
        self.assertEqual(patched, [])
        self.assertFalse(T.implausible({"text": "wonderful", "start": 1.0, "end": 2.1}, [(1.0, 2.1)]))

    def test_long_word_over_silence_is_not_implausible(self):
        # Whisper stretches a stamp over a pause: under 60 % speech, nothing to re-transcribe
        self.assertFalse(T.implausible({"text": "so", "start": 1.0, "end": 4.0}, [(1.0, 1.4)]))
        self.assertTrue(T.implausible({"text": "so", "start": 1.0, "end": 4.0}, [(1.0, 3.5)]))

    def test_retry_fails(self):
        first = scribe(("remove", 38.68, 42.34))
        retranscribe, _ = self.stub([])
        words, patched, untranscribed = T.fill_holes(first, [(38.6, 42.4)], retranscribe, 50.0)
        self.assertEqual(patched, [])
        self.assertTrue(any(a <= 38.7 and b >= 42.3 for a, b in untranscribed), untranscribed)


    def test_word_stretched_over_a_pause_and_a_retake(self):
        # 3 letters, 4.3 s: 2.3 s of silence, then 2 s of speech nobody transcribed (under 60 % of the word)
        runs = [(98.7, 100.78)]
        self.assertTrue(T.implausible({"text": "the", "start": 96.48, "end": 100.78}, runs))
        first = scribe(("so", 95.0, 95.4), ("the", 96.48, 100.78), ("end.", 101.2, 101.6))
        retranscribe, _ = self.stub([("I", 96.42, 98.9), ("wonder", 98.9, 99.6), ("why", 99.7, 100.6)])
        words, patched, untranscribed = T.fill_holes(first, runs + [(94.9, 95.5), (101.1, 101.7)], retranscribe, 105.0)
        got = [w for w in words if w["type"] == "word"]
        self.assertEqual([w["text"] for w in got], ["so", "I", "wonder", "why", "end."])
        self.assertEqual([p.get("replaced") for p in patched], ["the"])
        self.assertEqual(untranscribed, [])

    def test_recovered_word_stamped_in_the_pause(self):
        first = scribe(("ok", 50.0, 55.0))  # speech only from 52.3: the retry stamps its first word early
        retranscribe, _ = self.stub([("so", 50.0, 52.6), ("then", 52.7, 53.4), ("this", 53.5, 54.2)])
        words, patched, _ = T.fill_holes(first, [(52.3, 55.0)], retranscribe, 60.0)
        got = [w for w in words if w["type"] == "word"]
        self.assertEqual((got[0]["text"], got[0]["start"]), ("so", 52.3))
        self.assertEqual([w["start"] for w in got[1:]], [52.7, 53.5])  # the others stay as measured

    def test_recovered_word_stamped_in_the_tail_of_the_previous_run(self):
        first = scribe(("ok", 96.0, 100.8))  # speech to 96.65, a pause, then speech from 98.78
        retranscribe, _ = self.stub([("ser", 96.0, 96.48), ("igual", 96.48, 99.02), ("tengo", 99.02, 99.4)])
        words, _, _ = T.fill_holes(first, [(93.5, 96.65), (98.78, 105.0)], retranscribe, 106.0)
        got = {w["text"]: w["start"] for w in words if w["type"] == "word"}
        self.assertEqual((got["ser"], got["igual"], got["tengo"]), (96.0, 98.78, 99.02))

    def test_long_word_over_silence_hides_nothing(self):
        # 3 s word, speech only in its first 0.3 s: a word covers that, so nothing to re-transcribe
        self.assertFalse(T.implausible({"text": "so", "start": 1.0, "end": 4.0}, [(1.0, 1.3)]))


class Audible(unittest.TestCase):
    def test_quiet_stretch_is_not_speech(self):
        """Real levels: speech at -24 dB, a floor at -52 dB, a breath in a pause at -40 dB."""
        import numpy as np
        db = np.full(4000, -24.0)   # 20 s of speech at a 5 ms hop
        db[1000:1400] = -40.0       # 5.0–7.0 s: 16 dB under the speech
        db[2000:2400] = -30.0       # 10.0–12.0 s: quiet speech
        self.assertEqual(T.audible([[5.0, 7.0], [10.0, 12.0]], db), [[10.0, 12.0]])

    def test_a_hole_past_the_end_is_dropped(self):
        import numpy as np
        self.assertEqual(T.audible([[100.0, 101.0]], np.full(400, -24.0)), [])


class Restarts(unittest.TestCase):
    def words(self, text: str, gaps: dict[int, float] = {}):
        out, t = [], 10.0
        for i, w in enumerate(text.split()):
            out.append({"type": "word", "text": w, "start": round(t, 3), "end": round(t + 0.2, 3)})
            t += 0.25 + gaps.get(i, 0.0)
        return out

    def test_restart_detected(self):
        ws = self.words("the first would be to drop the fear of… the first would be to remove the fear")
        (r,) = T.mark_restarts(ws)
        self.assertEqual(r["abandoned"], [ws[0]["start"], ws[8]["end"]])
        self.assertEqual(r["again"], ws[9]["start"])
        self.assertEqual(r["words"], "the first would be to drop the fear of…")

    def test_pause_without_full_stop(self):
        ws = self.words("we start with the plan we start with the plan today.", gaps={4: 0.4})
        (r,) = T.mark_restarts(ws)
        self.assertEqual(r["again"], ws[5]["start"])
        self.assertEqual(r["words"], "we start with the plan")

    def test_pause_inside_the_abandoned_phrase(self):
        ws = self.words("anyway I wonder, have you ever been anyway I wonder, have you ever been the youngest here?",
                        gaps={2: 0.5, 6: 2.0})
        (r,) = T.mark_restarts(ws)
        self.assertEqual(r["abandoned"], [ws[0]["start"], ws[6]["end"]])
        self.assertEqual(r["again"], ws[7]["start"])

    def test_two_words_across_a_long_wait(self):
        """Real take: "Igual, tengo mucha curiosidad, ¿les ha tocado ser" … 2.3 s … "igual tengo curiosidad les ha…"."""
        ws = self.words("Igual, tengo mucha curiosidad, ¿les ha tocado ser igual tengo curiosidad les ha tocado ser los",
                        gaps={3: 0.5, 7: 2.0})
        (r,) = T.mark_restarts(ws)
        self.assertEqual((r["abandoned"], r["again"]), ([ws[0]["start"], ws[7]["end"]], ws[8]["start"]))

    def test_long_abandoned_phrase(self):
        """Real take: a 6 s phrase trailing off, then the same opening 2.6 s later."""
        ws = self.words("estas son las habilidades que más practico con líderes adoptando inteligencia artificial en su día "
                        "a día para sus... estas son las dos habilidades que más practico", gaps={18: 2.4})
        (r,) = T.mark_restarts(ws)
        self.assertEqual((r["abandoned"][0], r["again"]), (ws[0]["start"], ws[19]["start"]))

    def test_list_across_a_pause_is_not_a_restart(self):
        ws = self.words("I wrote about de mi casa, de mi calle y mi barrio.", gaps={5: 0.4})
        self.assertEqual(T.mark_restarts(ws), [])

    def test_deliberate_repetition(self):
        ws = self.words("I spend this much on food. I spend this much on rent.", gaps={5: 0.5})
        self.assertEqual(T.mark_restarts(ws), [])

    def test_filler_before_the_repeat(self):
        ws = self.words("the first would be… uh no the first would be to remove the fear")
        (r,) = T.mark_restarts(ws)
        self.assertEqual(r["again"], ws[6]["start"])

    def test_sentences_that_open_alike(self):
        """Real take: a pause after a comma, more words, then a sentence with the same first two words."""
        ws = self.words("Y en ese libro hablaba de mi casa, de mi calle y mi barrio. Y en contra de todo lo dejé.", gaps={7: 0.4})
        self.assertEqual(T.mark_restarts(ws), [])

    def test_too_far_apart(self):
        ws = self.words("the plan is… " + "x " * 30 + "the plan is simple")
        self.assertEqual(T.mark_restarts(ws), [])

    def test_shown_in_packed_words(self):
        ws = self.words("the first would be to drop the fear of… the first would be to remove the fear")
        out = T.with_restart_marks(T.with_spacing(ws), T.mark_restarts(ws))
        (ev,) = [w for w in out if w["type"] == "audio_event"]
        self.assertEqual(ev["start"], ws[9]["start"])
        self.assertIn("restart", ev["text"])
        self.assertEqual([w for w in out if w["type"] == "word"], ws)


class Breaks(unittest.TestCase):
    def words(self, *spec):
        return [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in spec]

    def test_around_a_false_start(self):
        ws = self.words(("a", 93.5, 94.0), ("b", 96.0, 96.5), ("a", 98.7, 99.0), ("b", 99.1, 99.5))
        rs = [{"abandoned": [93.5, 96.5], "again": 98.7, "words": "a b"}]
        self.assertEqual(T.sentence_breaks(ws, rs, []), [93.5, 98.7])

    def test_around_a_hole(self):
        ws = self.words(("x", 51.0, 51.9), ("y", 53.1, 53.5))
        self.assertEqual(T.sentence_breaks(ws, [], [[52.1, 53.0]]), [53.1])

    def test_a_stretched_word_that_failed_stands_alone(self):
        ws = self.words(("x", 37.0, 37.5), ("so", 38.68, 42.34), ("y", 43.0, 43.4))
        self.assertEqual(T.sentence_breaks(ws, [], [[38.68, 42.34]]), [38.68, 43.0])

    def test_nothing_to_break(self):
        self.assertEqual(T.sentence_breaks(self.words(("x", 1.0, 1.4)), [], []), [])


class NoPromptForOthers(unittest.TestCase):
    def test_no_prompt_for_other_languages(self):
        self.assertIsNone(T.prompt_for("mlx", "fr"))
        self.assertIsNone(T.prompt_for("mlx", None))


if __name__ == "__main__":
    unittest.main()
