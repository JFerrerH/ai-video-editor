"""plan_precheck.py: the checks that need only the plan and the transcript, and that `plan_build` agrees with them
(specs/edit-plans).

    uv run python -m unittest tools.tests.test_plan_precheck
"""

import json
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))

import edit_plan as E  # noqa: E402
import plan_precheck as PC  # noqa: E402
from plan_fixture import WORDS, PlanFixture  # noqa: E402


def transcript(words=WORDS) -> dict:
    return {"take1": {"words": [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in words]}}


class SameAsTheBuild(PlanFixture):
    """The precheck and `plan_build` give the same errors: the build raises the ones that don't depend on timing before
    it opens the audio, and finds the rest again from the audio with the same code."""

    def build_errors(self, plan: dict) -> list[str]:
        try:
            return E.build(self.root, plan, stills=False)["errors"]
        except E.PlanError as e:
            return e.errors

    def both(self, plan: dict) -> list[str]:
        pre = PC.check(plan, transcript())["errors"]
        self.assertTrue(pre)
        # the same findings in the same words; a measured time may differ by hundredths (the clock is word times here)
        mask = lambda errs: [re.sub(r"\d+\.\d+", "#", e) for e in errs]  # noqa: E731
        self.assertEqual(mask(self.build_errors(plan)), mask(pre))
        return pre

    def test_echo(self):
        errs = self.both({"keep": ["F1", "F3-F4", "F6"], "hook": {"title": ["Hola mundo hoy"]}})
        self.assertTrue(any(e.startswith("ECHO HookTitle") and "hola" in e and "mundo" in e for e in errs), errs)

    def test_entrance_that_does_not_fit(self):
        errs = self.both({"keep": ["F1", "F3-F4", "F6"], "beats": [
            {"at": "F4", "word": "Sin", "device": "ChatThread", "until": "F4",
             "props": {"messages": [{"from": "me", "at": {"word": "ahora"}}]}},
            {"at": "F4", "word": "ahora", "device": "Notice", "props": {"from": "A", "text": "B"}}]})
        self.assertTrue(any("its entrances need" in e and "beat 0" in e for e in errs), errs)

    def test_kept_false_start(self):
        errs = self.both({"keep": ["F1", "F2"]})
        self.assertTrue(any("F2 is a false start" in e and "keep F3" in e for e in errs), errs)

    def test_cut_with_no_pause(self):
        words = [(t, a, b) for t, a, b in WORDS]
        words[words.index(("ya", 10.6, 10.9))] = ("ya", 9.63, 9.9)  # F5 follows F4 by 0.03 s: a punch-in can't cut there
        d = transcript(words)
        plan = {"keep": ["F1", "F3-F5", "F6"], "beats": [{"at": "F5", "punch": True}]}
        errs = PC.check(plan, d)["errors"]
        self.assertTrue(any("a punch-in would cut between" in e and "run together" in e for e in errs), errs)
        # the build reads the same transcript and stops on the same errors, before it opens any audio
        f = self.root / "edit" / "transcripts" / "take1.json"
        original = f.read_text()
        f.write_text(json.dumps(d["take1"]))
        try:
            with self.assertRaises(E.PlanError) as cm:
                E.build(self.root, plan, stills=False)
        finally:
            f.write_text(original)
        self.assertEqual(cm.exception.errors, errs)

    def test_a_run_edge_with_no_gap_is_a_warning(self):
        # Whisper stamps a word over the pause beside it: the transcript alone can't call this cut wrong
        words = [(t, a, b) for t, a, b in WORDS]
        words[words.index(("ya", 10.6, 10.9))] = ("ya", 9.63, 9.9)
        res = PC.check({"keep": ["F4"]}, transcript(words))
        self.assertEqual(res["errors"], [], res)
        self.assertTrue(any("F4 ends where" in w for w in res["warnings"]), res)

    def test_two_punch_ins_in_one_cut(self):
        plan = {"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "punch": True},
                                                          {"at": "F4", "word": "nada", "punch": True}]}
        errs = self.both(plan)
        self.assertTrue(any("already has a punch-in" in e for e in errs), errs)

    def test_a_stretched_stamp_misleads_only_the_precheck(self):
        # "Hola" is stamped from 0.0 though its sound starts at 0.5: the word-time clock plays 0.5 s of silence
        # the audio cut drops, so the precheck's timing errors are listed apart and the build decides from the audio
        words = [(t, 0.0 if t == "Hola" else a, b) for t, a, b in WORDS]
        plan = {"keep": ["F1", "F3-F4", "F6"], "hook": {"title": ["Hola mundo hoy"]}}
        res = PC.check(plan, transcript(words))
        self.assertTrue(res["timed_errors"] and set(res["timed_errors"]) <= set(res["errors"]), res)
        f = self.root / "edit" / "transcripts" / "take1.json"
        original = f.read_text()
        f.write_text(json.dumps(transcript(words)["take1"]))
        try:
            self.assertEqual(self.build_errors({"keep": ["F1", "F3-F4", "F6"], "hook": {"title": ["Otro cartel"]}, "beats": [
                {"at": "F4", "word": "Sin", "device": "Notice", "props": {"from": "A", "text": "B"}, "through": "nada"},
                {"at": "F6", "word": "hoy", "device": "Notice", "props": {"from": "A", "text": "B"}}]}), [])
        finally:
            f.write_text(original)

    def test_a_short_pause_is_still_a_cut(self):
        self.assertEqual(PC.check({"keep": ["F6"]}, transcript())["errors"], [])  # "ahora," → "hoy": 0.1 s


class Answers(PlanFixture):
    def test_a_good_plan_passes_with_a_duration(self):
        res = PC.check({"keep": ["F1", "F3-F4", "F6"], "beats": [
            {"at": "F3", "word": "tesis", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}, transcript())
        self.assertEqual(res["errors"], [], res)
        self.assertGreater(res["duration"], 5)

    def test_the_times_are_close_to_the_builds(self):
        plan = {"keep": ["F1", "F3-F4", "F6"], "beats": [
            {"at": "F3", "word": "tesis", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}
        res = E.build(self.root, plan, stills=False)
        self.assertAlmostEqual(PC.check(plan, transcript())["duration"], res["duration"], delta=0.5)

    def test_plan_shape_errors_come_back(self):
        errs = PC.check({"keep": ["F99"]}, transcript())["errors"]
        self.assertTrue(any("F99" in e for e in errs), errs)

    def test_unknown_brand(self):
        self.assertTrue(PC.check({"keep": ["F1"], "brand": "acme"}, transcript(), brands=set())["errors"])
        self.assertFalse(any("brand" in e for e in PC.check({"keep": ["F1"], "brand": "acme"}, transcript(), brands={"acme"})["errors"]))

    def test_echo_is_one_function(self):
        ev = [{"type": "DocCard", "start": 1.0, "duration": 2.0, "props": {"title": "launch plan"}}]
        words = [{"text": "launch", "start": 1.5}]
        self.assertEqual(len(PC.echo(ev, words)), 1)
        self.assertEqual(PC.echo(ev, [{"text": "launch", "start": 9.0}]), [])
        self.assertEqual(PC.echo([{**ev[0], "type": "Notice"}], words), [])

    def test_fast(self):
        plan = {"keep": ["F1", "F3-F4", "F6", "F7"], "beats": [
            {"at": "F3", "word": "tesis", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}
        t0 = time.perf_counter()
        PC.check(plan, transcript())
        self.assertLess(time.perf_counter() - t0, 0.5)


class StandardLibraryOnly(unittest.TestCase):
    def test_imports_without_numpy_or_the_engine(self):
        code = ("import sys; sys.modules['numpy'] = None; sys.path.insert(0, sys.argv[1]); import plan_precheck; "
                "bad = [m for m in ('short_spec', 'shortform', 'audio_env') if m in sys.modules]; assert not bad, bad")
        r = subprocess.run([sys.executable, "-I", "-c", code, str(TOOLS)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
