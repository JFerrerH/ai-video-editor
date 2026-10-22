"""Narration timing: script words, alignment, phrases, cues.

    uv run python -m unittest discover -s tools/tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from narration import align, phrases, resolve_cue, script_words, spoken_tokens  # noqa: E402

LINE = "Ship it in *one day.*"
# what Whisper returns for the clip (s from the clip start); the first word is stamped early
RECOGNISED = [{"text": "Ship", "start": 0.0, "end": 0.3}, {"text": "it", "start": 0.32, "end": 0.42},
              {"text": "in", "start": 0.46, "end": 0.55}, {"text": "one", "start": 0.62, "end": 0.85},
              {"text": "day.", "start": 0.9, "end": 1.3}]


def timed(line, recognised, onset=0.04, end=1.4, pronounce=None):
    w = script_words(line)
    return phrases(align(w, spoken_tokens(w, pronounce), recognised, onset, end))


class ScriptWords(unittest.TestCase):
    def test_marks_stripped_punctuation_kept(self):
        w = script_words(LINE)
        self.assertEqual([x["text"] for x in w], ["Ship", "it", "in", "one", "day."])
        self.assertEqual([x["emph"] for x in w], [False, False, False, True, True])

    def test_closing_star_before_punctuation(self):
        w = script_words("in *one day*. Then | more")
        self.assertEqual([x["text"] for x in w], ["in", "one", "day.", "Then", "more"])
        self.assertEqual([x["emph"] for x in w], [False, True, True, False, False])
        self.assertTrue(w[3]["brk"])


class Align(unittest.TestCase):
    def check_times(self, w, end=1.4):
        ts = [x["t"] for x in w]
        self.assertTrue(all(b > a for a, b in zip(ts, ts[1:])), ts)
        self.assertTrue(0 <= ts[0] and ts[-1] < end, ts)

    def test_script_words_preserved(self):
        w = timed(LINE, RECOGNISED)
        self.assertEqual([x["text"] for x in w], ["Ship", "it", "in", "one", "day."])
        self.assertEqual([x["emph"] for x in w], [False, False, False, True, True])
        self.assertEqual(w[0]["t"], 0.04)  # clamped to the onset, not Whisper's 0.0
        self.assertEqual(w[3]["t"], 0.62)
        self.check_times(w)

    def test_recogniser_drops_a_word(self):
        rec = [r for r in RECOGNISED if r["text"] != "in"]
        w = timed(LINE, rec)
        self.assertEqual(len(w), 5)
        self.assertFalse(w[2]["aligned"])
        self.assertTrue(w[1]["t"] < w[2]["t"] < w[3]["t"])
        self.check_times(w)

    def test_recogniser_misspells_a_word(self):
        rec = [dict(r, text="won") if r["text"] == "one" else r for r in RECOGNISED]
        w = timed(LINE, rec)
        self.assertEqual([x["text"] for x in w][3], "one")
        self.assertTrue(w[2]["t"] < w[3]["t"] < w[4]["t"])
        self.check_times(w)

    def test_trailing_words_missing(self):
        w = timed(LINE, RECOGNISED[:2])
        self.assertEqual(len(w), 5)
        self.check_times(w)

    def test_pronounce_maps_to_spoken_tokens(self):
        rec = [{"text": "Our", "start": 0.0, "end": 0.2}, {"text": "sass", "start": 0.3, "end": 0.6},
               {"text": "grew", "start": 0.7, "end": 1.0}]
        w = timed("Our SaaS grew", rec, pronounce={"SaaS": "sass"})
        self.assertEqual(w[1]["text"], "SaaS")
        self.assertEqual(w[1]["t"], 0.3)
        self.assertTrue(w[1]["aligned"])


class Phrases(unittest.TestCase):
    def test_break_on_sentence_end(self):
        w = timed("Write the plan. Ship the work.", [])
        self.assertEqual([x["phrase"] for x in w], [0, 0, 0, 1, 1, 1])

    def test_break_on_bar_and_length(self):
        w = timed("one two | three four five six seven eight nine ten", [], end=5)
        self.assertEqual([x["phrase"] for x in w], [0, 0, 1, 1, 1, 1, 2, 2, 2, 2])

    def test_long_sentence_split_evenly(self):
        w = timed("We reached a thousand users in a week.", [], end=3)
        self.assertEqual([x["phrase"] for x in w], [0, 0, 0, 0, 1, 1, 1, 1])
        w = timed(" ".join(["w"] * 15) + ".", [], end=6)
        self.assertEqual(max(sum(1 for x in w if x["phrase"] == p) for p in range(3)), 5)


class Cues(unittest.TestCase):
    def test_cues(self):
        w = timed("Day one, then day two.", [], end=3)
        self.assertEqual(resolve_cue("@day", w), w[0]["t"])
        self.assertEqual(resolve_cue("@DAY#2", w), w[3]["t"])
        self.assertEqual(resolve_cue("@two+0.25", w), round(w[4]["t"] + 0.25, 3))
        self.assertEqual(resolve_cue("@one-0.1", w), round(w[1]["t"] - 0.1, 3))
        self.assertIsNone(resolve_cue("@revenue", w))
        self.assertIsNone(resolve_cue("@day#3", w))


if __name__ == "__main__":
    unittest.main()
