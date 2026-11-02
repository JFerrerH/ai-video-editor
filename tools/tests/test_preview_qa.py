"""preview_qa.py: the words and cuts of a rendered preview against the edit (specs/preview-qa).

The heard words are given to the checker (no Whisper here), and the preview's clips are cut from a synthetic take.

    uv run python -m unittest tools.tests.test_preview_qa      (or: uv run --with pytest pytest tools/tests/test_preview_qa.py)
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))

import edit_plan as E  # noqa: E402
import preview_qa as Q  # noqa: E402
import run_job as R  # noqa: E402
import short_spec as SS  # noqa: E402
from plan_fixture import PlanFixture  # noqa: E402


def build(root, plan):
    return E.build(root, plan, stills=False)


PLAN = {"keep": ["F1", "F3-F4", "F6"], "beats": [  # a graphic now and then: a plan with nothing on screen for 8 s is refused
    {"at": "F3", "word": "tesis", "device": "Notice", "props": {"from": "A", "text": "B"}, "until": "F4"},
    {"at": "F6", "word": "sígueme", "device": "Notice", "props": {"from": "C", "text": "D"}}]}


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


class Preview(PlanFixture):
    """The compiled plan, its clips cut from the take at the engine's own edges, and the base they make."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        res = build(cls.root, PLAN)
        assert not res["errors"], res
        cls.p, _ = SS.load(cls.root / "edit" / "short.json", cls.root)
        cls.render(cls.p.segments)

    @classmethod
    def render(cls, segs) -> None:
        d = cls.root / "edit" / "clips_preview"
        d.mkdir(exist_ok=True)
        for old in d.glob("seg_*.mov"):
            old.unlink()
        for k, s in enumerate(segs):
            n = round((s.t_out - s.t_in) * 30) / 30  # whole frames: audio and video of a clip end together
            ffmpeg("-ss", f"{s.t_in:.3f}", "-t", f"{n:.4f}", "-i", str(cls.root / "edit" / "conformed" / "take1.mov"),
                   "-c:v", "libx264", "-c:a", "pcm_s16le", str(d / f"seg_{k:02d}.mov"))
        (cls.root / "edit" / "concat.txt").write_text("".join(f"file 'clips_preview/seg_{k:02d}.mov'\n" for k in range(len(segs))))
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(cls.root / "edit" / "concat.txt"), "-c", "copy",
               str(cls.root / "edit" / "base_preview.mov"))
        (cls.root / "edit" / "preview.mp4").write_bytes(b"x")

    def heard(self, extra=None, drop=()) -> list[dict]:
        """What Whisper would hear from the preview if it plays exactly the edit's words."""
        exp, _ = Q.expected(self.p, self.root)
        words = [{"text": x["w"], "start": x["t"], "end": x["t"] + 0.3} for k, x in enumerate(exp) if k not in drop]
        for text, t in extra or []:
            words.append({"text": text, "start": t, "end": t + 0.5})
        return sorted(words, key=lambda w: w["start"])

    def qa(self, heard) -> dict:
        return Q.preview_qa(self.root, heard=heard)


class Words(Preview):
    def test_good_edit_passes(self):
        res = self.qa(self.heard())
        self.assertTrue(res["ok"], res["errors"])
        self.assertEqual(res["stats"]["expected_words"], res["stats"]["heard_words"])

    def test_stumble_the_transcript_hid(self):
        res = self.qa(self.heard(extra=[("conversemos", 5.4)]))
        self.assertFalse(res["ok"])
        f = next(f for f in res["errors"] if f["kind"] == "unexpected_speech")
        self.assertEqual(f["t"], 5.4)
        self.assertIsNotNone(f["segment"])
        self.assertIn("5.40 s", f["message"])
        self.assertIn("conversemos", f["message"])
        self.assertIn("segment", f["fix"])

    def test_short_function_words_are_not_unexpected_speech(self):
        res = self.qa(self.heard(extra=[("y", 3.0), ("el", 3.4), ("la", 3.8)]))
        self.assertTrue(res["ok"], res["errors"])

    def test_a_split_word_is_not_a_stumble(self):
        exp, _ = Q.expected(self.p, self.root)
        k = next(i for i, x in enumerate(exp) if x["w"] == "estudiar")
        heard = self.heard(drop={k})
        heard += [{"text": "estu", "start": exp[k]["t"], "end": exp[k]["t"] + 0.2}, {"text": "diar", "start": exp[k]["t"] + 0.2, "end": exp[k]["t"] + 0.5}]
        res = self.qa(sorted(heard, key=lambda w: w["start"]))
        self.assertFalse([f for f in res["errors"] if f["kind"] == "unexpected_speech"], res["errors"])

    def test_a_clipped_word(self):
        exp, cuts = Q.expected(self.p, self.root)
        k = cuts[0] - 1  # the last word before the first cut
        res = self.qa(self.heard(drop={k}))
        f = next(f for f in res["errors"] if f["kind"] == "clipped_word")
        self.assertIn(exp[k]["w"], f["message"])
        self.assertEqual(f["segment"], exp[k]["seg"])

    def test_a_line_that_plays_twice(self):
        again = [(x["w"], x["t"] + 12.0) for x in Q.expected(self.p, self.root)[0][5:9]]
        res = self.qa(self.heard(extra=again))
        self.assertTrue(any(f["kind"] == "repeat" and "plays 2×" in f["message"] for f in res["errors"]), res["errors"])

    def test_a_restart_is_heard(self):
        # the take says "en esa tesis" twice in different sentences only through the false start F2; the plan skips it
        heard = self.heard(extra=[("Ahora", 20.0), ("vamos", 20.4), ("Ahora", 21.9), ("vamos", 22.3), ("a", 22.6), ("ver", 22.8)])
        res = self.qa(heard)
        self.assertTrue(any(f["kind"] == "restart" for f in res["errors"]), res["errors"])

    def test_a_word_owned_by_the_segment_with_most_of_it(self):
        # "tesis" (4.8–5.3) is split by an edge at 5.0 in a stub: it counts once, in the segment covering 0.3 of it
        p = SimpleNamespace(segments=[SimpleNamespace(take="take1", t_in=0.4, t_out=5.0), SimpleNamespace(take="take1", t_in=5.0, t_out=6.6)],
                            offsets=lambda: [0.0, 4.6, 6.2])
        words, cuts = Q.expected(p, self.root)
        self.assertEqual([x["w"] for x in words].count("tesis"), 2)  # the false start's and the kept one, each once
        tesis = [x for x in words if x["w"] == "tesis"][-1]
        self.assertEqual(tesis["seg"], 1)  # 0.3 s of it is after the edge, 0.2 s before
        self.assertEqual(len(cuts), 1)


class Cuts(Preview):
    def stub(self, *ranges) -> SimpleNamespace:
        return SimpleNamespace(segments=[SimpleNamespace(take="take1", t_in=a, t_out=b) for a, b in ranges])

    def render_stub(self, ranges) -> None:
        self.render(self.stub(*ranges).segments)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_cut_through_a_word_is_loud(self):
        stub = self.stub((7.5, 8.2), (10.7, 11.6))  # 8.2 is in the middle of "estudiar" (7.9–8.5)
        self.render_stub([(7.5, 8.2), (10.7, 11.6)])
        faults = Q.cut_energy(stub, self.root)
        self.assertTrue(faults, "a cut inside a tone should be loud")
        self.assertEqual(faults[0]["kind"], "cut_energy")
        self.assertIn("dB relative to speech", faults[0]["message"])
        self.assertAlmostEqual(faults[0]["t"], 0.7, delta=0.02)

    def test_cuts_in_pauses_are_quiet(self):
        stub = self.stub((0.4, 1.6), (4.0, 6.6))
        self.render_stub([(0.4, 1.6), (4.0, 6.6)])
        self.assertEqual(Q.cut_energy(stub, self.root), [])

    def test_a_cut_at_the_start_of_a_take_is_clean(self):
        stub = self.stub((0.4, 1.6), (0.0, 0.6))  # the second clip starts at the media start, where the first sample is sound
        self.render_stub([(0.4, 1.6), (0.0, 0.6)])
        starts = [f for f in Q.cut_energy(stub, self.root) if "start of" in f["message"]]
        self.assertEqual(starts, [])

    def test_real_clip_durations_are_used(self):
        # the clips are shorter than the segments say: the cut is where the clip ends, not at the nominal time
        stub = self.stub((7.5, 8.2), (10.7, 11.6))
        self.render_stub([(7.5, 8.2), (10.7, 11.6)])
        self.assertAlmostEqual(Q.clip_durations(self.root, 2)[0], 0.7, delta=0.05)

    def test_stale_preview(self):
        stub = self.stub((0.4, 1.6), (4.0, 6.6))
        self.render_stub([(0.4, 1.6), (4.0, 6.6)])
        ffmpeg("-i", str(self.root / "edit" / "base_preview.mov"), "-t", "1.0", "-c", "copy", str(self.root / "edit" / "short_base.mov"))
        (self.root / "edit" / "short_base.mov").replace(self.root / "edit" / "base_preview.mov")
        with self.assertRaises(SystemExit) as cm:
            Q.cut_energy(stub, self.root)
        self.assertIn("stale", str(cm.exception))


class Job(Preview):
    def test_report_names_time_and_fix(self):
        res = self.qa(self.heard(extra=[("conversemos", 5.4)]))
        self.assertTrue(all({"kind", "t", "segment", "message", "fix"} <= set(f) for f in res["errors"]))
        json.dumps(res)  # a job result is JSON

    def run_job(self, heard) -> dict:
        qa = self.root / "edit" / "qa" / "transcripts"
        qa.mkdir(parents=True, exist_ok=True)
        (qa / "preview.json").write_text(json.dumps({"words": [{"type": "word", **w} for w in heard]}))
        with mock.patch.object(R, "FOOTAGE", self.tmp):
            res, code = R.run({"op": "preview_qa", "project": "demo", "args": {"reuse": True}})
        return {**res, "code": code}

    def test_qa_through_a_job(self):
        exp, cuts = Q.expected(self.p, self.root)
        res = self.run_job(self.heard(drop={cuts[0] - 1}))  # a clipped word at the first cut
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], 1)
        f = next(f for f in res["errors"] if f["kind"] == "clipped_word")
        self.assertIn(" s: clipped word", f["message"])
        self.assertTrue(f["fix"])

    def test_good_preview_through_a_job(self):
        res = self.run_job(self.heard())
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["errors"], [])


if __name__ == "__main__":
    unittest.main()
