"""edit_plan.py: numbered sentences, the plan's shape, and the compiler's rules (specs/edit-plans).

    uv run python -m unittest tools.tests.test_edit_plan      (or: uv run --with pytest pytest tools/tests/test_edit_plan.py)
"""

import copy
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))

import edit_plan as E  # noqa: E402
import short_spec as SS  # noqa: E402
from plan_fixture import PlanFixture  # noqa: E402

REPO = TOOLS.parent

def build(root, plan, **kw):  # the stills need Remotion; one test below runs them
    return E.build(root, plan, **{"stills": False, **kw})


BASE = {"keep": ["F1", "F3-F4", "F6"],
        "beats": [{"at": "F3", "word": "tesis", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}


class Sentences(PlanFixture):
    def test_restart_flagged(self):
        s = self.ids()
        self.assertEqual(s["F2"]["restart_of"], "F3")
        self.assertEqual(s["F2"]["text"], "En esa tesis")
        self.assertTrue(s["F3"]["text"].startswith("en esa tesis"))  # starts at the second "en"
        self.assertEqual(s["F3"]["start"], 4.1)
        self.assertNotIn("restart_of", s["F3"])

    def test_sentences_that_open_alike_are_not_flagged(self):
        ws = [{"text": t, "start": a, "end": a + 0.2} for t, a in
              (("Y", 0.0), ("en", 0.3), ("esa", 0.6), ("tesis", 0.9), ("Hablaba", 2.0), ("de", 2.3), ("ropa.", 2.6),
               ("Y", 4.0), ("en", 4.3), ("contra", 4.6), ("mía.", 4.9))]
        self.assertFalse([s for s in E.sentences({"t": ws}) if s.get("restart_of")])

    def line(self, text, t0, step=0.3):
        return [{"text": w, "start": round(t0 + step * i, 2), "end": round(t0 + step * i + 0.2, 2)}
                for i, w in enumerate(text.split())]

    def test_false_start_after_an_unpunctuated_line(self):
        a = self.line("I kept it in a drawer for years", 0.0)          # ends 2.3
        b = self.line("and then I told", 3.0)                           # starts 0.7 s after: under SENT_GAP
        c = self.line("and then I told my sister everything.", 6.0)
        ws = {"t": a + b + c}
        rs = {"t": [{"abandoned": [3.0, 3.9], "again": 6.0, "words": "and then I told"}]}
        self.assertEqual(len(E.sentences(ws, rs)), 2)  # without breaks the drawer line and the false start run together
        sents = E.sentences(ws, rs, {"t": [3.0, 6.0]})
        self.assertEqual([s["text"] for s in sents],
                         ["I kept it in a drawer for years", "and then I told", "and then I told my sister everything."])
        self.assertEqual([s.get("restart_of") for s in sents], [None, "F3", None])

    def test_transcript_without_breaks_keeps_its_ids(self):
        ws = {"t": self.line("one two three. four five", 0.0) + self.line("six seven", 5.0)}
        self.assertEqual(E.sentences(ws), E.sentences(ws, {}, {}))
        self.assertEqual(E.sentences(ws), E.sentences(ws, {}, {"t": []}))

    def test_take_order(self):
        import json
        import shutil
        other = self.root / "edit" / "transcripts" / "a-first-by-name.json"
        shutil.copy(self.root / "edit" / "transcripts" / "take1.json", other)
        try:
            self.assertEqual(E.plan_ids(self.root)[0]["take"], "a-first-by-name")
            self.assertEqual(E.plan_ids(self.root, ["take1"])[0]["take"], "take1")
            self.assertEqual(E.plan_ids(self.root, ["take1", "missing"])[-1]["take"], "a-first-by-name")
            self.assertTrue(json.loads(other.read_text()))
        finally:
            other.unlink()

    def test_ids_are_stable(self):
        self.assertEqual(E.plan_ids(self.root), E.plan_ids(self.root))
        self.assertEqual(list(self.ids()), [f"F{k}" for k in range(1, 8)])

    def test_sentence_shows_take_start_and_duration(self):
        s = self.ids()["F4"]
        self.assertEqual((s["take"], s["start"], s["dur"]), ("take1", 7.5, 2.1))

    def test_false_start_cannot_be_kept(self):
        with self.assertRaises(E.PlanError) as cm:
            build(self.root, {"keep": ["F1", "F2"]})
        self.assertTrue(any("F2 is a false start" in m and "keep F3" in m for m in cm.exception.errors), cm.exception.errors)


class NoAir(PlanFixture):
    """A kept sentence whose next sentence starts 0.1 s after it, in the middle of the video."""

    GAP_WORDS = [("Uno", 0.5, 0.9), ("dos.", 1.0, 1.5), ("Tres", 1.6, 2.0), ("cuatro.", 2.1, 2.6),
                 ("Cinco", 4.0, 4.4), ("seis.", 4.5, 5.0)]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from plan_fixture import make_take
        make_take(cls.root / "edit" / "conformed" / "take1.mov", cls.GAP_WORDS, d=6.0)
        (cls.root / "edit" / "transcripts" / "take1.json").write_text(json.dumps(
            {"language_code": "es", "words": [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in cls.GAP_WORDS]}))

    def test_names_the_sentence_before_any_still(self):
        res = E.build(self.root, {"keep": ["F1", "F3"]}, stills=True)  # F1 flows into F2 (0.1 s), F2 is left out
        (msg,) = [m for m in res["errors"] if "of air a cut needs" in m]
        self.assertIn("segments[0].out", msg)
        self.assertIn("ends F1", msg)
        self.assertIn("keep the sentence after it too", msg)
        self.assertIsNone(res["stills"])  # refused before the stills
        self.assertFalse((self.root / "edit" / "stills").exists())

    def test_a_real_pause_builds(self):
        res = E.build(self.root, {"keep": ["F1", "F2"]}, stills=False)  # one run; the pause after it is 1.4 s
        self.assertEqual(res["errors"], [])


class PlanShape(PlanFixture):
    def errors(self, plan: dict) -> list[str]:
        with self.assertRaises(E.PlanError) as cm:
            build(self.root, plan)
        return cm.exception.errors

    def mutate(self, fn) -> dict:
        p = copy.deepcopy(BASE)
        fn(p)
        return p

    def test_seconds_in_a_beat(self):
        errs = self.errors(self.mutate(lambda p: p["beats"][0].update(start=12.4)))
        self.assertTrue(any("plan.beats[0].start" in m and "sentence ID and word" in m for m in errs), errs)

    def test_seconds_in_a_time_prop(self):
        plan = self.mutate(lambda p: p["beats"].__setitem__(0, {"at": "F4", "word": "nada", "device": "Gauge", "props": {
            "label": "COSTO", "stamp": "FUERA", "slamAt": 1.2}}))
        errs = self.errors(plan)
        self.assertTrue(any("props.slamAt" in m and 'the word it lands on' in m for m in errs), errs)

    def test_no_seconds_anywhere_in_the_schema(self):
        beat = E.plan_schema()["properties"]["beats"]["items"]
        self.assertFalse({"start", "end", "duration", "time"} & set(beat["properties"]))
        self.assertIs(beat["additionalProperties"], False)

    def test_unknown_sentence_and_word(self):
        errs = self.errors(self.mutate(lambda p: p["beats"][0].update(at="F9")))
        self.assertTrue(any("plan.beats[0].at" in m for m in errs), errs)
        errs = self.errors(self.mutate(lambda p: p["beats"][0].update(word="nunca")))
        self.assertTrue(any("plan.beats[0].word" in m and "nunca" in m for m in errs), errs)

    def test_beat_on_a_sentence_that_is_not_kept(self):
        errs = self.errors(self.mutate(lambda p: p["beats"][0].update(at="F5", word="tarde.")))
        self.assertTrue(any("isn't kept" in m for m in errs), errs)

    def test_split_screen_asked_for(self):
        errs = self.errors(self.mutate(lambda p: p["beats"][0].update(camera="split")))
        self.assertTrue(any("split screen isn't available" in m for m in errs), errs)

    def test_a_beat_must_show_something(self):
        errs = self.errors(self.mutate(lambda p: p["beats"].append({"at": "F4"})))
        self.assertTrue(any("needs a device, a camera move or a punch-in" in m for m in errs), errs)

    def test_a_punch_in_needs_a_pause_to_cut_in(self):
        with mock.patch.object(E, "BREAK_GAP", 2.0):  # the fixture's pauses are about 1 s
            errs = self.errors(self.mutate(lambda p: p["beats"].append({"at": "F4", "word": "nada", "punch": True})))
        self.assertTrue(any("punch-in would cut between" in m and "pause of 2 s" in m for m in errs), errs)

    # ── restraint caps ────────────────────────────────────────────────────
    def test_two_low_moments(self):
        errs = self.errors(self.mutate(lambda p: p.update(
            low=[{"at": "F5", "words": "ya es tarde"}, {"at": "F4", "words": "nada"}])))
        self.assertTrue(any("low look is used at most once" in m for m in errs), errs)

    def test_three_punch_ins(self):
        def f(p):
            p["beats"] = [{"at": "F3", "word": w, "punch": True} for w in ("tesis", "hablaba", "mucho.")]
        errs = self.errors(self.mutate(f))
        self.assertTrue(any("at most 2 times besides the hook" in m for m in errs), errs)

    def test_low_in_the_hook(self):
        errs = self.errors(self.mutate(lambda p: p.update(low={"at": "F1", "words": "Hola mundo"})))
        self.assertTrue(any("plan.low" in m and "over the hook" in m for m in errs), errs)

    def test_low_line_too_long(self):
        with mock.patch.object(E, "LOW_MAX", 1.0):  # the fixture's sentences are all under 3 s
            errs = self.errors(self.mutate(lambda p: p.update(low={"at": "F6", "words": "sígueme ahora hoy mismo"})))
        self.assertTrue(any("plan.low" in m and "at most 1 s" in m for m in errs), errs)


class Compile(PlanFixture):
    def test_through_ends_a_hold_on_a_word(self):
        self.build({"keep": ["F1", "F3-F4", "F6"], "beats": [
            {"at": "F4", "word": "Sin", "device": "Notice", "props": {"from": "A", "text": "B"}, "through": "estudiar"}]})
        n = next(e for e in self.spec()["events"] if e["type"] == "Notice")
        self.assertLessEqual(n["duration"], 1.6)  # to the end of "estudiar" (1.1 s), at least the 1.5 s a card needs

    def test_flash_is_over_at_once(self):
        self.build({"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "device": "Flash"}]})
        self.assertEqual(next(e for e in self.spec()["events"] if e["type"] == "Flash")["duration"], 0.3)

    def test_a_punch_sentence_is_a_cut_of_its_own(self):
        self.build({"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "nada", "punch": True},
                    {"at": "F3", "word": "tesis", "device": "Notice", "props": {"from": "A", "text": "B"}, "until": "F4"}]})
        segs = self.spec()["segments"]
        punched = [g for g in segs if g["zoom"]["kind"] == "punch"]
        self.assertEqual(len(punched), 1)
        self.assertEqual((punched[0]["from"]["word"], punched[0]["zoom"]["at"]["word"]), ("Sin", "nada"))

    def build(self, plan: dict) -> dict:
        res = build(self.root, plan)
        self.assertEqual(res["errors"], [], res)
        return res

    def spec(self) -> dict:
        return json.loads((self.root / "edit" / "short.json").read_text())

    def test_segments_are_cut_by_word_and_pass_strict(self):
        res = self.build(BASE)
        self.assertEqual(res["spec"], "edit/short.json")
        segs = self.spec()["segments"]
        self.assertTrue(all("from" in g and "to" in g for g in segs))
        # F3 and F4 are one run, but the 1.1 s pause between them is a jump cut of its own with a new frame size
        self.assertEqual([g["from"]["word"] for g in segs], ["Hola", "en", "Sin", "sígueme"])
        self.assertNotEqual(segs[1]["zoom"], segs[2]["zoom"])
        self.assertFalse(any({"in", "out", "lock_in", "lock_out"} & set(g) for g in segs))  # words, not seconds, no locks
        self.assertEqual(segs[0]["from"]["word"], "Hola")
        self.assertEqual(segs[1]["from"]["word"], "en")  # the second "en": F2 was never kept

    def test_beat_lands_on_its_word(self):
        self.build(BASE)
        ev = next(e for e in self.spec()["events"] if e["type"] == "DocCard")
        self.assertEqual(ev["start"]["word"], "tesis")
        self.assertEqual(ev["start"]["after"], 4.79)
        self.assertLessEqual(ev["duration"], 6.0)
        self.assertEqual(ev["layer"], "front")

    def test_a_beat_holds_until_the_thought_ends_but_not_into_the_next_beat(self):
        plan = copy.deepcopy(BASE)
        plan["beats"] = [{"at": "F3", "word": "en", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Uno"}, "until": "F4"},
                         {"at": "F4", "word": "nada", "device": "Notice", "props": {"from": "Ana", "text": "Ya viste?"}}]
        self.build(plan)
        a, b = (e for e in self.spec()["events"] if e["type"] in ("DocCard", "Notice"))
        self.assertLessEqual(a["duration"], 6.0)
        self.assertEqual(b["start"]["word"], "nada")

    def test_time_prop_lands_on_its_word(self):
        plan = {"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "device": "Gauge", "until": "F4", "props": {
            "label": "COSTO", "stamp": "FUERA", "slamAt": {"word": "nada"}}}]}
        self.build(plan)
        spec = self.spec()
        g = next(e for e in spec["events"] if e["type"] == "Gauge")
        self.assertEqual(g["props"]["slamAt"]["word"], "nada")
        self.assertEqual(g["layer"], "behind")
        stamp = next(x for x in spec["sfx"] if x["name"] == "stamp")
        self.assertEqual(stamp["at"]["word"], "nada")  # the stamp sounds when the stamp lands

    def test_device_defaults_panel_and_camera(self):
        plan = {"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "device": "PhonePanel", "props": {
            "mode": "corner", "screens": [{"src": "site/a.png"}, {"src": "site/a.png"}]}}], "assets": {"site/a.png": "edit/conformed/a.png"}}
        (self.root / "edit" / "conformed" / "a.png").write_bytes(b"x")
        self.build(plan)
        spec = self.spec()
        self.assertEqual(spec["events"][0]["layer"], "panel")
        self.assertEqual([m["kind"] for m in spec["camera"]], ["corner"])
        self.assertIn("swipe", [x["name"] for x in spec["sfx"]])

    def test_no_quota(self):
        plan = {"keep": ["F1", "F3-F4", "F6"], "hook": {"title": ["Una idea", "de 2020"]},
                "beats": [{"at": "F3", "word": "tesis", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}},
                          {"at": "F4", "word": "Sin", "device": "Notice", "props": {"from": "Ana", "text": "Viste?"}},
                          {"at": "F4", "word": "nada", "device": "Stickers", "props": {"items": [{"text": "Big Data", "x": 150, "y": 230}]}},
                          {"at": "F6", "word": "sígueme", "device": "Notice", "props": {"from": "Leo", "text": "Listo"}}],
                "cta": {"at": "F6", "word": "mismo", "handle": "Link"}}
        res = self.build(plan)
        spec = self.spec()
        self.assertEqual(len(spec["events"]), 4 + 1 + 1)  # the four beats, the hook and the CTA, nothing else
        self.assertEqual(spec["camera"], [])
        self.assertTrue(all(g["zoom"]["kind"] != "punch" or k == 0 for k, g in enumerate(spec["segments"])))
        self.assertIn("longest_s", res["pacing"])

    def test_pacing_refuses_and_never_fills(self):
        res = E.build(self.root, {"keep": ["F1", "F3-F4", "F6", "F7"]}, stills=False)
        self.assertIsNone(res["spec"])
        self.assertTrue(any("no graphic or camera move on screen" in m and "Nothing was added" in m for m in res["errors"]), res)
        self.assertGreater(res["pacing"]["longest_s"], E.PACING_MAX)

    def test_pacing_warns_between_five_and_eight_seconds(self):
        # F3 + F4 + F6 play ~9 s; a beat covering the middle leaves stretches of 5–8 s on either side
        res = self.build({"keep": ["F1", "F3-F4", "F6"], "beats": [
            {"at": "F4", "word": "estudiar", "device": "Notice", "props": {"from": "A", "text": "B"}, "through": "nada"}]})
        self.assertLessEqual(res["pacing"]["longest_s"], E.PACING_MAX + 3)
        self.assertEqual(bool(res["pacing"].get("warning")), res["pacing"]["longest_s"] > E.PACING_WARN)

    def test_low_look_is_its_own_cut(self):
        res = self.build({"keep": ["F1", "F3-F5", "F6"], "low": {"at": "F5", "words": "ya es tarde"},
                          "beats": [{"at": "F6", "word": "sígueme", "device": "Notice", "props": {"from": "A", "text": "B"}}]})
        segs = self.spec()["segments"]
        low = [g for g in segs if g.get("look") == "low"]
        self.assertEqual(len(low), 1)
        self.assertEqual(low[0]["from"]["word"], "ya")
        self.assertEqual(low[0]["zoom"], {"kind": "static", "scale": 1.0})
        self.assertIn("whoosh", [x["name"] for x in self.spec()["sfx"]])  # the turn after the low look
        self.assertEqual(res["errors"], [])

    def test_text_on_the_frame_gets_a_colour_that_reads(self):
        """What `check` can't see: a big word in nearly the wall's colour takes one that reads there, for the render too."""
        plan = {"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "device": "BehindWord", "through": "ahora",
                "props": {"lead": "sin estudiar", "word": "nada", "riseAt": {"word": "nada"}, "color": "#8c8c8c", "size": 160}}]}
        res = E.build(self.root, plan, stills=True)
        self.assertEqual(res["errors"], [])
        placed = json.loads((self.root / "edit" / "overlay_placed.json").read_text())
        self.assertTrue(any(p.get("color") and p["color"] != "#8c8c8c" for p in placed.values()), placed)

    def test_behind_word_is_left_to_the_placement(self):
        self.build({"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "device": "BehindWord", "props": {"word": "tecnología"}}]})
        word = next(e for e in self.spec()["events"] if e["type"] == "BehindWord")
        self.assertNotIn("y", word["props"])  # the stills place it, against the head at that moment

    def test_hidden_text_is_a_strict_finding(self):
        import short_spec
        self.assertIn("hidden", short_spec.STRICT_KINDS)

    def test_check_errors_come_back_with_the_beat(self):
        res = build(self.root, {"keep": ["F1", "F3-F4", "F6"], "beats": [{"at": "F4", "word": "Sin", "device": "DocCard", "props": {
            "kicker": "A", "title": "B", "frame": {"y": 200}}}]})
        self.assertTrue(any("beat 0" in m and "frame" in m for m in res["errors"]), res["errors"])
        self.assertIsNone(res["spec"])

    def test_run_on_speech_cannot_be_cut(self):
        # "ahora," → "hoy" has a 0.1 s pause; cutting between them is a clean cut, so a plan may keep F6 alone
        res = self.build({"keep": ["F6"]})
        self.assertEqual(res["errors"], [])


class SoundBans(PlanFixture):
    NOTES = "# brand\n\n- Rejected before: pluck, ding (use click instead).\n- Never use whoosh under speech.\n"

    def test_parser_takes_words_before_use(self):
        kit = self.tmp / "repo" / "brands" / "acme"
        kit.mkdir(parents=True)
        (kit / "brand.md").write_text(self.NOTES)
        synth = self.tmp / "repo" / "assets" / "sfx" / "synth"
        synth.mkdir(parents=True)
        for n in ("pluck", "click", "whoosh", "pop"):
            (synth / f"{n}.wav").write_bytes(b"")
        self.assertEqual(E.rejected_sfx("acme", self.tmp / "repo"), {"pluck", "whoosh"})  # click is the replacement, not banned

    def test_brand_rejects_a_sound(self):
        kit = REPO / "brands" / "plantest-kit"
        shutil.copytree(REPO / "brands" / "_template", kit)
        try:
            (kit / "brand.md").write_text(self.NOTES)
            res = build(self.root, {**BASE, "brand": "plantest-kit", "cta": {"at": "F6", "word": "sígueme", "handle": "Link"}})
            self.assertEqual(res["errors"], [], res)
            names = {x["name"] for x in json.loads((self.root / "edit" / "short.json").read_text())["sfx"]}
            self.assertIn("click", names)
            self.assertFalse({"pluck", "ding", "whoosh"} & names, names)
        finally:
            shutil.rmtree(kit)

    def test_banned_sound_is_replaced_or_dropped(self):
        kit = REPO / "brands" / "plantest-kit"
        shutil.copytree(REPO / "brands" / "_template", kit)
        try:
            (kit / "brand.md").write_text("Rejected before: pop, tap, click, tick.\n")
            res = build(self.root, {**BASE, "brand": "plantest-kit", "hook": {"title": ["Una idea", "de 2020"]}})
            self.assertEqual(res["errors"], [], res)
            names = {x["name"] for x in json.loads((self.root / "edit" / "short.json").read_text())["sfx"]}
            self.assertFalse({"pop", "tap", "click", "tick", "pluck"} & names, names)
        finally:
            shutil.rmtree(kit)

    def test_pluck_is_never_used(self):
        self.assertIn("pluck", E.ALWAYS_BANNED)
        self.assertFalse(any(name == "pluck" for name, _ in E.SFX.values()))
        self.assertFalse(any("pluck" in alts for alts in E.SFX_SUBSTITUTE.values()))


class HoleHint(PlanFixture):
    """Kept speech with no words: the error names a fix a plan can apply."""

    def build_with(self, untranscribed, breaks, keep):
        f = self.root / "edit" / "transcripts" / "take1.json"
        original = f.read_text()
        d = json.loads(original)
        f.write_text(json.dumps({**d, "untranscribed": untranscribed, **({"breaks": breaks} if breaks is not None else {})}))
        try:
            return build(self.root, {"keep": keep})
        finally:
            f.write_text(original)

    def test_hole_between_two_sentences(self):
        # no words for 8.5–8.6, between "estudiar" and "nada": the transcript ends a sentence there (F4 | F5)
        res = self.build_with([[8.5, 8.6]], [8.6], ["F4", "F5"])
        (e,) = [e for e in res["errors"] if "8.50–8.60" in e]
        self.assertIn("between F4 and F5", e)
        self.assertIn("leave F4 or F5 out of `keep`", e)
        self.assertNotIn("listen", e)
        self.assertFalse(self.build_with([[8.5, 8.6]], [8.6], ["F4"])["errors"])

    def test_hole_inside_a_sentence_of_an_older_transcript(self):
        res = self.build_with([[8.5, 8.6]], None, ["F4"])  # inside "Sin estudiar nada ahora."
        (e,) = [e for e in res["errors"] if "8.50–8.60" in e]
        self.assertIn("F4", e)
        self.assertIn("prepare the footage again", e)


class Cli(PlanFixture):
    def test_ids_prints_flags(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(E.main(["ids", str(self.root)]), 0)
        out = buf.getvalue()
        self.assertIn("F2", out)
        self.assertIn("false start: said again in F3", out)


class SkillExamples(unittest.TestCase):
    """The worked plans in short-form-pro/SKILL.md stay in the plan's shape (fields, devices, no seconds)."""

    def plans(self):
        import re
        text = (REPO / ".claude" / "skills" / "short-form-pro" / "SKILL.md").read_text()
        section = text[text.index("## Edit by plan"):text.index("## Workflow")]
        return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", section, re.S)]

    def test_examples_are_plans(self):
        import overlay_schema
        plans = self.plans()
        self.assertEqual(len(plans), 2)
        beat_fields = set(E.plan_schema()["properties"]["beats"]["items"]["properties"])
        for plan in plans:
            self.assertLessEqual(set(plan), set(E.plan_schema()["properties"]))
            for b in plan["beats"]:
                self.assertLessEqual(set(b), beat_fields, b)
                self.assertIn(b.get("device", "Flash"), overlay_schema.COMPONENTS)
                for path, v, _, _ in overlay_schema.time_fields(b["device"], b["props"]) if b.get("device") else []:
                    self.assertIsInstance(v, dict, f"{b['device']}.{path} is a time: a word, not seconds")



class CaptionFixes(PlanFixture):
    def test_fixes_reach_the_spec(self):
        res = build(self.root, {**BASE, "captions": {"fixes": {"Hola": "Holaa"}}})
        self.assertEqual(res["errors"], [])
        spec = json.loads((self.root / "edit" / "short.json").read_text())
        self.assertEqual(spec["captions"], {"fixes": {"Hola": "Holaa"}})

    def test_only_fixes(self):
        with self.assertRaises(E.PlanError) as e:
            build(self.root, {**BASE, "captions": {"word_fixes": [{"at": 12.4, "text": "x"}]}})
        self.assertIn("plan.captions", e.exception.errors[0])



class SharedScreen(PlanFixture):
    def test_the_hook_gives_way_to_the_first_graphic(self):
        plan = {**BASE, "hook": {"title": ["Otro cartel"]}, "keep": ["F1", "F3-F4", "F6"],
                "beats": [{"at": "F3", "word": "hablaba", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}
        res = build(self.root, plan)
        self.assertEqual(res["errors"], [])
        p, _ = SS.load(self.root / "edit" / "short.json", self.root)
        hook, card = (next(e for e in p.events if e["type"] == t) for t in ("HookTitle", "DocCard"))
        self.assertLessEqual(hook["start"] + hook["duration"], card["start"] + 0.01)

    def test_a_graphic_too_early_for_the_hook_is_named(self):
        plan = {**BASE, "hook": {"title": ["Otro cartel"]}, "keep": ["F1", "F3-F4", "F6"],
                "beats": [{"at": "F3", "word": "en", "device": "DocCard", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}
        self.assertIn("HookTitle and DocCard", build(self.root, plan)["errors"][0])

    def test_a_graphic_gives_way_to_the_cta(self):
        plan = {**BASE, "cta": {"at": "F6", "handle": "Sigueme"},
                "beats": [{"at": "F4", "word": "Sin", "device": "DocCard", "until": "F6", "props": {"kicker": "PLAN", "title": "Un ropero"}}]}
        res = build(self.root, plan)
        self.assertEqual(res["errors"], [])
        p, _ = SS.load(self.root / "edit" / "short.json", self.root)
        card, cta = (next(e for e in p.events if e["type"] == t) for t in ("DocCard", "HandleCard"))
        self.assertLessEqual(card["start"] + card["duration"], cta["start"] + 0.01)

    def test_two_cards_at_once_are_named(self):
        class P:
            events = [{"type": "Receipt", "start": 1.0, "duration": 3.0}, {"type": "Flash", "start": 2.0, "duration": 0.3},
                      {"type": "DocCard", "start": 3.0, "duration": 2.0}, {"type": "Captions", "start": 0.0, "duration": 9.0}]
        self.assertIn("Receipt and DocCard", E._shared_screen(P)[0])

    def test_a_full_screen_scene_covers_what_is_under_it(self):
        class P:
            events = [{"type": "HookTitle", "start": 0.0, "duration": 2.0},
                      {"type": "PostPile", "start": 1.0, "duration": 2.0, "props": {"full": True}}]
        self.assertEqual(E._shared_screen(P), [])

    def test_one_after_the_other_is_fine(self):
        class P:
            events = [{"type": "Receipt", "start": 1.0, "duration": 2.0}, {"type": "DocCard", "start": 3.0, "duration": 2.0}]
        self.assertEqual(E._shared_screen(P), [])


if __name__ == "__main__":
    unittest.main()
