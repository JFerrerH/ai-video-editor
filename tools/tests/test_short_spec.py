"""short_spec.py: shape validation, confinement, limits and anchor resolution.

    uv run python -m unittest tools.tests.test_short_spec      (or: uv run --with pytest pytest tools/tests/test_short_spec.py)
"""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import short_spec as S  # noqa: E402
import shortform as SF  # noqa: E402

MOTION = TOOLS / "motion"

# three tone bursts with silence between: "hello" 0.5–1.0, "launch" 1.5–2.0, "world" 2.5–3.0
WORDS = [("hello", 0.5, 1.0), ("launch", 1.5, 2.0), ("world", 2.5, 3.0)]


def make_take(path: Path, words=WORDS, d: float = 3.5, color: str = "gray") -> None:
    """Tone bursts at (_, a, b) or (_, a, b, amplitude) (default 0.5) over digital silence, on a `color` frame."""
    expr = "+".join(f"{w[3] if len(w) > 3 else 0.5}*between(t,{w[1]},{w[2]})" for w in words)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=108x192:r=30:d={d}",
                    "-f", "lavfi", "-i", f"aevalsrc='sin(2*PI*220*t)*({expr})':s=48000:d={d}",
                    "-shortest", "-c:v", "libx264", "-c:a", "pcm_s16le", str(path)], check=True)


# extra takes: (sound bursts, transcript words, extra transcript fields)
TAKES = {
    # "plan" (0.60–0.74) runs straight into "goes": no pause between them
    "runon": ([("", 0.3, 1.5)], [("the", 0.30, 0.60), ("plan", 0.60, 0.74), ("goes", 0.74, 1.00), ("on.", 1.00, 1.50)], {}),
    # "plan" is stamped 0.60–1.00 but sounds only to its core (0.72); a 20 ms blip at 0.91 and a quiet breath
    # (0.96–1.11, far under the speech, far over digital silence) before "now"
    "breath": ([("", 0.30, 0.50), ("", 0.60, 0.72), ("", 0.91, 0.93), ("", 0.96, 1.11, 0.01), ("", 1.21, 1.50)],
               [("we", 0.30, 0.50), ("plan", 0.60, 1.00), ("now.", 1.21, 1.50)], {}),
    # a 0.62 s pause after "dos" and a 0.1 s one after "uno"
    "pause": ([("", 0.3, 0.7), ("", 0.8, 1.2), ("", 1.82, 2.3)],
              [("uno", 0.3, 0.7), ("dos", 0.8, 1.2), ("tres.", 1.82, 2.3)], {}),
    # loud from the very first sample
    "loud0": ([("", 0.0, 1.0)], [("go.", 0.0, 1.0)], {}),
    # take1's audio; "hello" (0.5–1.0) is a false start restarted at "launch" (1.5); 1.2–1.4 has no words
    "restart": (WORDS, WORDS, {"restarts": [{"abandoned": [0.5, 1.0], "again": 1.5, "words": "hello"}],
                               "untranscribed": [[1.2, 1.4]]}),
    # one sound with only words inside, between "a" and "b": music under speech
    "music": ([("", 0.3, 3.2)], [("a", 0.5, 1.0), ("b", 2.0, 2.5)], {}),
    # Whisper stamps "la" from 0.5, in the silence before its sound (0.8)
    "early": ([("", 0.8, 1.2), ("", 1.6, 2.0)], [("la", 0.5, 1.2), ("casa.", 1.6, 2.0)], {}),
    # a 20 ms click (far under the speech, far over digital silence) 0.08 s after "we"
    "click": ([("", 0.3, 0.6), ("", 0.68, 0.70, 0.05), ("", 1.3, 1.6)], [("we", 0.3, 0.6), ("go.", 1.3, 1.6)], {}),
    # take1's audio over a bright wall (luminance ≈ 0.72) and a white one
    "bright": (WORDS, WORDS, {}),
    "white": (WORDS, WORDS, {}),
}
COLORS = {"bright": "0xDDDDDD", "white": "white"}
# a head box on the 108x192 takes (source px): x 380–700, y 630–1000 at 1080x1920; grown by 6 %, it starts at 565
HEAD = [38, 63, 70, 100]


BASE = {
    "version": 1, "brand": "none",
    "sources": {"take1": {"file": "take1.mov", "face": [54, 96]}},
    "segments": [{"take": "take1", "in": 0.45, "out": 1.05},
                 {"take": "take1", "in": 1.45, "out": 3.05, "zoom": {"kind": "punch", "base": 1.0, "peak": 1.1,
                                                                    "at": {"word": "world"}}}],
    "events": [{"type": "HookTitle", "start": 0, "end": {"seg": 0, "edge": "end"}, "props": {"lines": [{"text": "Hi"}]}},
               {"type": "HookTitle", "start": {"word": "launch", "take": "take1"}, "duration": 0.5,
                "props": {"lines": [{"text": "Go"}]}}],
    "sfx": [{"name": "click", "at": {"word": "launch", "take": "take1", "offset": 0.05}, "gain_db": -15}],
}


from errors import ToolError  # noqa: E402


class Fixture(unittest.TestCase):
    """A 3.5 s synthetic project (see make_take) and helpers to write and load specs for it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.root = cls.tmp / "demo"
        (cls.root / "edit" / "transcripts").mkdir(parents=True)
        make_take(cls.root / "take1.mov")
        words = [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in WORDS]
        (cls.root / "edit" / "transcripts" / "take1.json").write_text(json.dumps({"words": words}))
        # take2: one sound from 0.5 to 3.0 s with no silence in it; only "empezar," (0.5–1.6) is transcribed
        make_take(cls.root / "take2.mov", [("", 0.5, 3.0)])
        (cls.root / "edit" / "transcripts" / "take2.json").write_text(json.dumps(
            {"words": [{"type": "word", "text": "empezar,", "start": 0.5, "end": 1.6}]}))
        for take, (sound, said, extra) in TAKES.items():
            make_take(cls.root / f"{take}.mov", sound, color=COLORS.get(take, "gray"))
            words = [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in said]
            (cls.root / "edit" / "transcripts" / f"{take}.json").write_text(json.dumps({"words": words, **extra}))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def write(self, spec: dict) -> Path:
        p = self.root / "edit" / "short.json"
        p.write_text(json.dumps(spec))
        return p

    def errors(self, spec: dict) -> list[str]:
        return S.validate(spec, self.root, self.root / "edit")

    def mutate(self, fn) -> dict:
        s = copy.deepcopy(BASE)
        fn(s)
        return s

    def event(self, type_, props, start=0, duration=2.0):
        return self.mutate(lambda s: s["events"].append({"type": type_, "start": start, "duration": duration, "props": props}))

    def load_errors(self, spec) -> list[str]:
        with self.assertRaises(S.SpecError) as cm:
            S.load(self.write(spec), self.root)
        return cm.exception.errors

    def segs(self, *segs, take2=False) -> dict:
        spec = {"version": 1, "brand": "none", "sources": {"take1": BASE["sources"]["take1"]},
                "segments": [dict(zip(("take", "in", "out"), s[:3]), **(s[3] if len(s) > 3 else {})) for s in segs]}
        if take2:
            spec["sources"]["take2"] = {"file": "take2.mov", "face": [54, 96]}
        return spec

    def on(self, take: str, *segs: dict) -> dict:
        """A spec whose segments (dicts without `take`) all cut `take`."""
        return {"version": 1, "brand": "none", "sources": {take: {"file": f"{take}.mov", "face": [54, 96]}},
                "segments": [{"take": take, **s} for s in segs]}

    def check(self, spec: dict, strict: bool = False) -> dict:
        return S.check(self.write(spec), self.root, strict=strict)


class SpecTest(Fixture):
    # ── shape ─────────────────────────────────────────────────────────────
    def test_base_is_valid(self):
        self.assertEqual(self.errors(BASE), [])

    def test_unknown_field_names_segment(self):
        errs = self.errors(self.mutate(lambda s: s["segments"][1].update(filter="movie=/etc/passwd")))
        self.assertTrue(any("segments[1]" in e and "'filter'" in e for e in errs), errs)

    def test_outside_path(self):
        (self.tmp / "other.mov").write_bytes(b"x")
        errs = self.errors(self.mutate(lambda s: s["sources"]["take1"].update(file="../other.mov")))
        self.assertTrue(any("outside the project" in e for e in errs), errs)

    def test_absolute_path(self):
        errs = self.errors(self.mutate(lambda s: s["sources"]["take1"].update(file=str(self.tmp / "other.mov"))))
        self.assertTrue(any("outside the project" in e for e in errs), errs)

    def test_unknown_brand(self):
        errs = self.errors(self.mutate(lambda s: s.update(brand="does-not-exist")))
        self.assertTrue(any("no brand kit" in e for e in errs), errs)

    def test_unknown_overlay_and_sfx(self):
        def f(s):
            s["events"][0]["type"] = "Shell"
            s["sfx"][0]["name"] = "nope"
        errs = self.errors(self.mutate(f))
        self.assertTrue(any("events[0].type" in e for e in errs), errs)
        self.assertTrue(any("sfx[0].name" in e and "assets/sfx/synth" in e for e in errs), errs)

    def test_raw_grade_rejected(self):
        errs = self.errors(self.mutate(lambda s: s.update(grade="eq=contrast=2")))
        self.assertTrue(any(e.startswith("grade:") for e in errs), errs)

    def test_file_props_must_be_public_files(self):
        errs = self.errors(self.mutate(lambda s: s["events"][0]["props"].update(src="../../secret.png")))
        self.assertTrue(any(".src" in e and "not a public file" in e for e in errs), errs)
        errs = self.errors(self.mutate(lambda s: s["events"].append(
            {"type": "EndCard", "start": 0, "duration": 1, "props": {"logo": "/etc/logo.svg"}})))
        self.assertTrue(any(".logo" in e and "not a public file" in e for e in errs), errs)
        self.assertFalse(any("events[2].type" in e for e in errs), errs)  # scene primitives are valid events

    def test_duration_limit(self):
        errs = self.errors(self.mutate(lambda s: s.update(
            segments=[{"take": "take1", "in": 0, "out": 100}, {"take": "take1", "in": 0, "out": 140}])))
        self.assertTrue(any("limit is 180" in e for e in errs), errs)

    def test_segment_limit(self):
        errs = self.errors(self.mutate(lambda s: s.update(
            segments=[{"take": "take1", "in": 0, "out": 0.2}] * 121)))
        self.assertTrue(any("limit is 120" in e for e in errs), errs)

    def test_edges_settings(self):
        self.assertEqual(self.errors(self.mutate(lambda s: s.update(edges={"above_floor": 28}))), [])
        errs = self.errors(self.mutate(lambda s: s.update(edges={"above_floor": 99, "window": 1})))
        self.assertTrue(any("edges.above_floor" in e for e in errs) and any("'window'" in e for e in errs), errs)

    def test_end_and_duration_exclusive(self):
        errs = self.errors(self.mutate(lambda s: s["events"][1].update(end=2.0)))
        self.assertTrue(any("exactly one of" in e for e in errs), errs)

    # ── anchors ───────────────────────────────────────────────────────────
    def test_anchors_match_project_helpers(self):
        p, rep = S.load(self.write(BASE), self.root)
        offs = p.offsets()
        self.assertAlmostEqual(p.events[0]["duration"], round(offs[1], 3), places=3)  # seg 0 end
        self.assertAlmostEqual(p.events[1]["start"], round(p.word("take1", "launch"), 3), places=3)
        self.assertAlmostEqual(p.events[1]["duration"], 0.5, places=3)
        self.assertAlmostEqual(p.sfx[0][1], round(p.word("take1", "launch") + 0.05, 3), places=3)
        self.assertEqual(p.segments[1].zoom, ("punch", 1.0, 1.1, 2.5))  # word "world" in source time
        self.assertEqual(rep["duration"], round(offs[-1], 3))

    def test_anchor_cut_out(self):
        spec = self.mutate(lambda s: s["events"][1].update(start={"word": "world", "take": "take1", "after": 0},
                                                           ) or s.update(segments=s["segments"][:1]))
        spec["sfx"] = []
        spec["events"][0]["end"] = 1.0
        with self.assertRaises(S.SpecError) as cm:
            S.load(self.write(spec), self.root)
        self.assertTrue(any("events[1]" in e and "not in the cut" in e for e in cm.exception.errors), cm.exception.errors)

    def test_check_reports_without_video(self):
        before = {p.name for p in self.root.rglob("*")}
        res = S.check(self.write(BASE), self.root)
        self.assertEqual(res["errors"], [])
        self.assertGreater(res["duration"], 2.0)
        self.assertEqual(len(res["timeline"]), 3)
        new = {p.name for p in self.root.rglob("*")} - before
        self.assertFalse([n for n in new if n.endswith((".mp4", ".mov"))], new)

    # ── event props (schemas) ─────────────────────────────────────────────

    def test_number_as_string(self):
        errs = self.errors(self.event("StatScene", {"value": "400.000"}))
        self.assertIn('events[2].props.value (StatScene): must be a number, got the string "400.000"', errs)

    def test_unknown_prop(self):
        errs = self.errors(self.event("KineticType", {"lines": [{"text": "Hi"}], "colour": "red"}))
        self.assertTrue(any(e.startswith("events[2].props.colour (KineticType): unknown field") for e in errs), errs)

    def test_unit_in_a_string(self):
        errs = self.errors(self.event("KineticType", {"lines": [{"text": "Hi", "at": "0.5s"}]}))
        self.assertTrue(any("events[2].props.lines[0].at" in e and "must be seconds" in e and "or an anchor" in e
                            for e in errs), errs)

    def test_missing_required_prop(self):
        errs = self.errors(self.mutate(lambda s: s["events"].append({"type": "ListScene", "start": 0, "duration": 1})))
        self.assertIn("events[2].props.items (ListScene): missing required field", errs)

    def test_anchor_in_prop_is_checked(self):
        errs = self.errors(self.event("ListScene", {"items": [{"text": "a", "at": {"word": "x"}}]}))
        self.assertIn("events[2].props.items[0].at: missing field 'take'", errs)

    def test_output_time_given_as_event_time(self):
        errs = self.load_errors(self.event("KineticType", {"lines": [{"text": "Hi", "at": 18.2}]}, start=17.5, duration=3.0))
        e = next(e for e in errs if "events[2].props.lines[0].at" in e)
        for part in ("18.2 s", "3.0 s", "did you mean 0.7"):
            self.assertIn(part, e)
        self.assertEqual(len([e for e in errs if "lines[0]" in e]), 1, errs)  # no second "finishes late" for it

    def test_word_anchor_in_prop(self):
        spec = self.event("ListScene", {"items": [{"text": "a", "at": 0.1},
                                                  {"text": "b", "at": {"word": "launch", "take": "take1"}}]},
                          start=0.2, duration=2.0)
        p, _ = S.load(self.write(spec), self.root)
        ev = p.events[2]
        self.assertEqual(ev["props"]["items"][1]["at"], round(p.word("take1", "launch") - 0.2, 3))
        self.assertEqual(ev["index"], 2)
        self.assertEqual(spec["events"][2]["props"]["items"][1]["at"], {"word": "launch", "take": "take1"})  # spec untouched
        _, pj = p.stage_overlay()
        written = json.loads(pj.read_text())["events"][2]["props"]["items"][1]["at"]
        self.assertEqual(written, ev["props"]["items"][1]["at"])

    def test_late_last_item(self):
        errs = self.load_errors(self.event("ListScene", {"items": [{"text": t} for t in "abcd"]}, duration=2.0))
        e = next(e for e in errs if "items[3]" in e)
        self.assertIn("events[2].props.items[3] (ListScene)", e)
        self.assertIn("after the event ends", e)
        self.assertIn("2.30", e)

    # ── timeline integrity ────────────────────────────────────────────────

    def test_overlap_inside_original_ranges(self):
        errs = self.load_errors(self.segs(("take1", 0.45, 2.05), ("take1", 1.45, 3.05)))
        e = next(e for e in errs if "overlaps" in e)
        for part in ("segments[1]", "segments[0]", "0.60 s", '"launch"', '"repeat": true'):
            self.assertIn(part, e)
        self.assertFalse(e.startswith("after edge refinement"), e)

    def test_deliberate_repeat(self):
        p, rep = S.load(self.write(self.segs(("take1", 0.45, 2.05), ("take1", 1.45, 3.05, {"repeat": True}))), self.root)
        self.assertEqual(len(p.segments), 2)
        self.assertEqual(S.validate({**self.segs(("take1", 0, 1, {"repeat": "yes"}))}, self.root, self.root / "edit"),
                         ["segments[0].repeat: must be true or false"])

    def test_overlap_in_different_takes(self):
        p, _ = S.load(self.write(self.segs(("take1", 0.45, 2.05), ("take2", 0.3, 0.45), ("take1", 2.45, 3.05),
                                           take2=True)), self.root)
        self.assertEqual(len(p.segments), 3)
        S.load(self.write(self.segs(("take1", 0.45, 1.05), ("take2", 0.3, 0.45), take2=True)), self.root)

    def test_touching_segments_join(self):
        # speech ("launch") runs to 2.0; on their own the out would widen to ~2.12 past the next in (2.02)
        spec = self.segs(("take1", 0.45, 1.95), ("take1", 2.02, 3.05))
        p, rep = S.load(self.write(spec), self.root)
        a, b = p.segments
        self.assertLessEqual(a.t_out, b.t_in)
        self.assertTrue(2.0 <= a.t_out <= 2.07, a.t_out)  # quietest point: in the silence after the word
        self.assertIn("[joined]", rep["edges"][0])
        self.assertIn("[joined]", rep["edges"][1])
        # without the join the same edges overlap: that's what the refined-overlap check exists for
        q, _ = S.load(self.write(self.segs(("take1", 0.45, 1.95))), self.root)
        self.assertGreater(q.segments[0].t_out, 2.02)

    def test_trimmed_pause_kept(self):
        # 1.05 → 1.45 is a pause the editor cut out: refined on their own, the edges never cross
        p, rep = S.load(self.write(self.segs(("take1", 0.45, 1.05), ("take1", 1.45, 3.05))), self.root)
        a, b = p.segments
        self.assertFalse(any("joined" in ln for ln in rep["edges"]), rep["edges"])
        self.assertLess(a.t_out, b.t_in)
        self.assertGreater(b.t_in - a.t_out, 0.1)

    def test_no_joins_same_edges(self):
        from shortform import Project, Seg
        p = Project(self.root / "edit", {"take1": self.root / "take1.mov"}, {"take1": (54, 96)},
                    [Seg("take1", 0.45, 1.05), Seg("take1", 1.45, 3.05)], brand=None)
        q = Project(self.root / "edit", {"take1": self.root / "take1.mov"}, {"take1": (54, 96)},
                    [Seg("take1", 0.45, 1.05), Seg("take1", 1.45, 3.05)], brand=None)
        self.assertEqual(p.refine_edges(), q.refine_edges(joins=[], detail=True)[0])

    def test_in_point_inside_a_word(self):
        errs = self.load_errors(self.segs(("take2", 1.2, 3.4), take2=True))
        e = next(e for e in errs if e.startswith('segments[0].in 1.20 is inside "empezar" (0.50–1.60): use 0.50 or 1.60'))
        self.assertRegex(e, r"no pause, the nearest pause before it is at 0\.4\d")  # both boundaries are on sound
        self.assertFalse(any("middle of sound" in e and ".in" in e for e in errs), errs)  # one message per edge

    def test_locked_edge_inside_a_word(self):
        res = S.check(self.write(self.segs(("take2", 1.2, 3.4, {"lock_in": True}), take2=True)), self.root)
        self.assertTrue(any(e.startswith('segments[0].in 1.20 is inside "empezar" (0.50–1.60): use 0.50 or 1.60')
                            for e in res["errors"]), res)

    def test_locked_edge_between_words(self):
        res = self.check(self.on("music", {"in": 1.5, "out": 3.4, "lock_in": True}))
        self.assertEqual(res["errors"], [])
        self.assertTrue(any(w.startswith("segments[0].in 1.50") and "(locked)" in w for w in res["warnings"]), res)

    def test_loud_head(self):
        res = S.check(self.write(self.segs(("take2", 2.2, 3.4), take2=True)), self.root)
        e = next(e for e in res["errors"] if e.startswith("segments[0].in"))
        self.assertIn("starts in the middle of sound", e)
        self.assertRegex(e, r"\+\d+\.\d dB over the room tone")
        self.assertNotIn("lock", e)
        self.assertFalse(any("<-- check" in m for m in res["errors"] + res["warnings"] + res["edges"]))

    def test_locked_edge_in_an_early_stamp(self):
        # inside the stamp of "la" but in the silence before its sound: nothing is cut
        res = self.check(self.on("early", {"in": 0.65, "out": 2.3, "lock_in": True}))
        self.assertFalse(any("inside" in m for m in res["errors"] + res["warnings"]), res)

    def test_take_starts_mid_word(self):
        res = self.check(self.on("loud0", {"in": 0.0, "out": 1.3}))
        self.assertFalse(any(".in" in m for m in res["errors"] + res["warnings"]), res)

    def test_captions_fit_nowhere_warns(self):
        spec = self.segs(("take1", 0.45, 3.05))
        spec["events"] = [{"type": "StatScene", "start": 0, "duration": 2.0, "props": {"value": 1}}]
        p, _ = S.load(self.write(spec), self.root)
        boxes = self.root / "edit" / "overlay_boxes.json"
        self.addCleanup(boxes.unlink, missing_ok=True)
        boxes.write_text(json.dumps({p._box_key(p.events[0]): {"box": [100, 400, 980, 1500]}}))
        self.assertNotIn("avoid", p.caption_event()["props"])
        (w,) = p.caption_warnings()
        self.assertTrue(w.startswith("captions cover events[0] (StatScene) text at "), w)
        self.assertIn("its content (400–1500 px) reaches the captions", w)
        self.assertEqual(w.kind, "captions_on_text")
        boxes.write_text(json.dumps({p._box_key(p.events[0]): {"box": [100, 700, 980, 1260]}}))
        self.assertEqual(p.caption_event()["props"]["avoid"], [[0.0, 2.0, 1320]])
        self.assertEqual(p.caption_warnings(), [])

    def test_check_warns_on_close_sfx(self):
        spec = self.mutate(lambda s: s["sfx"].append({"name": "pop", "at": {"word": "launch", "take": "take1",
                                                                             "offset": 0.2}}))
        res = S.check(self.write(spec), self.root)
        self.assertEqual(res["errors"], [])
        self.assertTrue(any("apart" in w for w in res["warnings"]), res["warnings"])


DOC = {"kicker": "PLAN", "title": "Our", "italic": "thesis"}


class LiveStageSpecTest(Fixture):
    """camera, event layer and object, and the low look (openspec/changes/live-stage)."""

    def cam(self, *moves, **extra) -> dict:
        return self.mutate(lambda s: s.update(camera=list(moves), **extra))

    def doc(self, spec: dict, start, props=None, **ev) -> dict:
        spec["events"].append({"type": "DocCard", "start": start, "duration": 0.5, "props": props or dict(DOC), **ev})
        return spec

    def low(self, **seg) -> dict:
        return self.mutate(lambda s: s["segments"][1].update({"zoom": {"kind": "static", "scale": 1.0}, "look": "low", **seg}))

    # ── camera ────────────────────────────────────────────────────────────
    def test_camera_kinds_are_valid(self):
        for kind in ("push", "pull", "side", "corner"):
            self.assertEqual(self.errors(self.cam({"kind": kind, "start": 0.2, "end": 1.0})), [], kind)

    def test_split_asked_for(self):
        errs = self.errors(self.cam({"kind": "split", "start": 0.2, "end": 1.0}))
        self.assertTrue(any("split screen is not available" in e and "push, pull, side, corner" in e for e in errs), errs)

    def test_camera_shape(self):
        e = self.errors(self.cam({"kind": "pull", "start": 0.2}, {"kind": "pull", "start": 0.2, "end": 1.0, "zoom": 2}))
        self.assertTrue(any("camera[0]" in x and "'end'" in x for x in e), e)
        self.assertTrue(any("camera[1]" in x and "unknown field" in x for x in e), e)

    def test_push_amount_limit(self):
        self.assertEqual(self.errors(self.cam({"kind": "push", "start": 0.2, "end": 1.0, "amount": 0.08})), [])
        e = self.errors(self.cam({"kind": "push", "start": 0.2, "end": 1.0, "amount": 0.09}))
        self.assertTrue(any("camera[0].amount" in x for x in e), e)

    def test_amount_only_on_push(self):
        e = self.errors(self.cam({"kind": "pull", "start": 0.2, "end": 1.0, "amount": 0.05}))
        self.assertTrue(any("camera[0]" in x and "amount" in x for x in e), e)

    def test_overlapping_moves(self):
        e = self.load_errors(self.cam({"kind": "side", "start": 0.2, "end": 1.2}, {"kind": "push", "start": 1.0, "end": 1.8}))
        self.assertTrue(any("camera[0]" in x and "camera[1]" in x and "overlap" in x for x in e), e)

    def test_touching_moves_are_fine(self):
        spec = self.cam({"kind": "side", "start": 0.2, "end": 1.0}, {"kind": "push", "start": 1.0, "end": 1.8})
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual([m["kind"] for m in p.camera], ["side", "push"])

    def test_word_anchored_moves_resolve_to_output_seconds(self):
        spec = self.cam({"kind": "pull", "start": {"word": "launch", "take": "take1"},
                         "end": {"word": "world", "take": "take1", "edge": "end"}})
        p, _ = S.load(self.write(spec), self.root)
        m = p.camera[0]
        self.assertAlmostEqual(m["start"], p.word("take1", "launch"), places=2)
        self.assertAlmostEqual(m["end"], p.word("take1", "world", end=True), places=2)

    def test_move_must_end_after_it_starts_and_inside_the_video(self):
        e = self.load_errors(self.cam({"kind": "pull", "start": 1.0, "end": 0.5}))
        self.assertTrue(any("camera[0]" in x and "after it starts" in x for x in e), e)
        e = self.load_errors(self.cam({"kind": "pull", "start": 1.0, "end": 30.0}))
        self.assertTrue(any("camera[0]" in x and "runs past the end" in x for x in e), e)

    def test_no_camera_is_a_plain_spec(self):
        p, _ = S.load(self.write(BASE), self.root)
        self.assertEqual(p.camera, [])
        self.assertTrue(all(e["layer"] == "front" for e in p.events))

    # ── layers ────────────────────────────────────────────────────────────
    def test_layer_values(self):
        code = {"file": "a.md", "lines": ["x"]}
        for layer in ("front", "behind", "panel"):  # CodePanel may use all three
            spec = self.mutate(lambda s: s["events"].append({"type": "CodePanel", "start": 0, "duration": 1.0, "props": code, "layer": layer}))
            self.assertEqual(self.errors(spec), [], layer)
        e = self.errors(self.doc(self.mutate(lambda s: None), 0, layer="middle"))
        self.assertTrue(any("events[2].layer" in x for x in e), e)

    def test_layer_must_be_one_the_component_allows(self):
        spec = self.mutate(lambda s: s["events"].append({"type": "Notice", "start": 0, "duration": 0.5, "layer": "behind",
                                                          "props": {"from": "A", "text": "b"}}))
        e = self.errors(spec)
        self.assertTrue(any("events[2].layer" in x and "Notice" in x and "front" in x for x in e), e)

    def test_panel_without_corner(self):
        spec = self.mutate(lambda s: s["events"].append({"type": "PhonePanel", "start": 0.1, "duration": 0.5, "layer": "panel",
                                                          "props": {"mode": "corner", "screens": [{"src": "s.png", "at": 0}]},
                                                          }))
        spec["public_files"] = {"s.png": "take1.mov"}
        e = self.load_errors(spec)
        self.assertTrue(any("events[2]" in x and "needs a `corner` move" in x for x in e), e)

    def test_panel_inside_corner(self):
        spec = self.cam({"kind": "corner", "start": 0.05, "end": 0.9})
        spec["events"].append({"type": "PhonePanel", "start": 0.1, "duration": 0.5, "layer": "panel",
                               "props": {"mode": "corner", "screens": [{"src": "s.png", "at": 0}]}})
        spec["public_files"] = {"s.png": "take1.mov"}
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual(p.events[-1]["layer"], "panel")

    def test_props_behind_is_a_behind_layer(self):
        spec = self.mutate(lambda s: s["events"][0]["props"].update(behind=True))
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual(p.events[0]["layer"], "behind")

    def test_layer_and_props_behind_disagree(self):
        spec = self.mutate(lambda s: (s["events"][0].update(layer="front"), s["events"][0]["props"].update(behind=True)))
        e = self.errors(spec)
        self.assertTrue(any("events[0]" in x and "behind" in x for x in e), e)

    # ── recurring objects ─────────────────────────────────────────────────
    def test_thesis_card_comes_back(self):
        spec = self.mutate(lambda s: None)
        for t, fill in ((0.0, 0.1), (0.6, 0.4), (1.2, 0.9)):
            self.doc(spec, t, {**DOC, "fillTo": fill}, object="thesis")
        res = self.check(spec)
        self.assertEqual(res["errors"], [])
        row = next(r for r in res["timeline"] if "thesis" in r)
        self.assertIn("DocCard", row)
        for t in ("0.00", "0.60", "1.20"):
            self.assertIn(t, row)

    def test_object_identity_mismatch(self):
        spec = self.mutate(lambda s: None)
        self.doc(spec, 0.0, dict(DOC), object="thesis")
        self.doc(spec, 0.6, {**DOC, "title": "Their"}, object="thesis")
        e = self.load_errors(spec)
        self.assertTrue(any("thesis" in x and "events[2]" in x and "events[3]" in x and "title" in x for x in e), e)

    def test_object_shared_across_components(self):
        spec = self.mutate(lambda s: None)
        self.doc(spec, 0.0, dict(DOC), object="thesis")
        spec["events"].append({"type": "HookTitle", "start": 0.6, "duration": 0.5, "props": {"lines": [{"text": "x"}]}, "object": "thesis"})
        e = self.load_errors(spec)
        self.assertTrue(any("thesis" in x and "DocCard" in x and "HookTitle" in x for x in e), e)

    def test_object_id_shape(self):
        e = self.errors(self.doc(self.mutate(lambda s: None), 0, object="Not Valid!"))
        self.assertTrue(any("events[2].object" in x for x in e), e)

    def test_sticker_after_the_event_ends(self):
        spec = self.mutate(lambda s: s["events"].append({"type": "Stickers", "start": 0.2, "duration": 1.0, "props": {
            "items": [{"text": "ok", "at": 0.2, "x": 0, "y": 0}, {"text": "late", "at": 1.5, "x": 0, "y": 0}]}}))
        e = self.load_errors(spec)
        self.assertTrue(any("events[2].props.items[1].at (Stickers)" in x and "outside the event" in x for x in e), e)
        self.assertFalse(any("items[0]" in x for x in e), e)

    # ── the low look ──────────────────────────────────────────────────────
    def test_one_short_low_line(self):
        spec = self.low(freeze=0.4)
        self.assertEqual(self.errors(spec), [])
        p, _ = S.load(self.write(spec), self.root)
        s = p.segments[-1]
        self.assertEqual((s.look, s.freeze_after), ("low", 0.4))

    def test_two_low_segments(self):
        spec = self.mutate(lambda s: [g.update(look="low", zoom={"kind": "static", "scale": 1.0}) for g in s["segments"]])
        e = self.errors(spec)
        self.assertTrue(any("low look is used at most once" in x for x in e), e)

    def test_low_needs_a_static_zoom(self):
        spec = self.mutate(lambda s: s["segments"][1].update(look="low"))  # BASE's second segment has a punch
        e = self.errors(spec)
        self.assertTrue(any("segments[1].zoom" in x and "static" in x for x in e), e)

    def test_freeze_range_and_look(self):
        for bad in (0.2, 0.6):
            e = self.errors(self.low(freeze=bad))
            self.assertTrue(any("segments[1].freeze" in x for x in e), (bad, e))
        e = self.errors(self.mutate(lambda s: s["segments"][0].update(freeze=0.4)))
        self.assertTrue(any("segments[0].freeze" in x and "low" in x for x in e), e)

    def test_freeze_and_freeze_after(self):
        e = self.errors(self.low(freeze=0.4, freeze_after=0.4))
        self.assertTrue(any("segments[1]" in x and "freeze_after" in x for x in e), e)

    def test_low_segment_length(self):
        spec = self.low(**{"in": 1.45, "out": 1.95})  # 0.5 s
        e = self.load_errors(spec)
        self.assertTrue(any("segments[1]" in x and "1.0" in x and "3.0" in x for x in e), e)
        spec = self.low(**{"in": 1.45, "out": 3.05})  # 1.6 s: inside
        S.load(self.write(spec), self.root)

    # ── captions follow the camera ────────────────────────────────────────
    def caps(self, **extra) -> dict:
        spec = self.mutate(lambda s: s.update(emphasis=[{"take": "take1", "phrase": "launch"}], **extra))
        spec["events"] = []
        return spec

    def test_corner_move_puts_ink_captions_above_the_bubble(self):
        p, _ = S.load(self.write(self.caps(camera=[{"kind": "corner", "start": 0.3, "end": 1.9}])), self.root)
        props = p.caption_event()["props"]
        self.assertIn([0.3, 1.9], [list(r) for r in props["lightRanges"]])  # ink while the corner is on
        a, b, top = next(x for x in props["avoid"] if x[:2] == [0.3, 1.9])
        cap_h = round(2.65 * max(props.get("size", 58), props.get("emphSize", 68)))
        self.assertLessEqual(top + cap_h, 1316)  # the bubble's top edge: 1920 − 0.3 · 1920 … ends above it
        self.assertGreater(top, 290)  # and still inside the top safe zone

    def test_other_moves_leave_captions_alone(self):
        p, _ = S.load(self.write(self.caps(camera=[{"kind": "pull", "start": 0.3, "end": 1.9}])), self.root)
        props = p.caption_event()["props"]
        self.assertEqual(props["lightRanges"], [])
        self.assertNotIn("avoid", props)

    def emph(self, p) -> dict:
        ev = p.caption_event()
        return {w["text"]: w["emph"] for w in ev["props"]["words"]}

    def test_emphasis_stays_without_a_synced_device(self):
        p, _ = S.load(self.write(self.caps()), self.root)
        self.assertEqual(self.emph(p)["launch"], 1)

    def test_emphasis_dropped_under_stickers_and_behind_words(self):
        for type_, props, layer in (("Stickers", {"items": [{"text": "launch", "at": 0.1, "x": 100, "y": 900}]}, "front"),
                                    ("BehindWord", {"word": "launch", "riseAt": 0.1}, "behind")):
            spec = self.caps()
            spec["events"] = [{"type": type_, "start": 0, "duration": 2.0, "layer": layer, "props": props}]
            p, _ = S.load(self.write(spec), self.root)
            self.assertEqual(self.emph(p)["launch"], 0, type_)

    def test_emphasis_kept_when_the_device_shows_another_word(self):
        spec = self.caps()
        spec["events"] = [{"type": "Stickers", "start": 0, "duration": 2.0,
                           "props": {"items": [{"text": "hello", "at": 0.1, "x": 100, "y": 900}]}}]
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual(self.emph(p)["launch"], 1)

    def test_emphasis_kept_when_the_sticker_is_not_in_yet(self):
        spec = self.caps()
        spec["events"] = [{"type": "Stickers", "start": 0, "duration": 2.6,
                           "props": {"items": [{"text": "launch", "at": 2.0, "x": 100, "y": 900}]}}]
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual(self.emph(p)["launch"], 1)

    # ── the echo rule and word-synced devices ─────────────────────────────
    def echo(self, type_, props, **ev) -> list[str]:
        spec = self.on("take1", {"in": 0.45, "out": 3.05})
        spec["events"] = [{"type": type_, "start": 0.5, "duration": 1.5, "props": props, **ev}]
        p, _ = S.load(self.write(spec), self.root)
        return p.echo_check()

    def test_short_stickers_and_behind_words_are_emphasis_not_echo(self):
        self.assertEqual(self.echo("Stickers", {"items": [{"text": "launch", "at": 0.1, "x": 0, "y": 900}]}), [])
        self.assertEqual(self.echo("BehindWord", {"word": "launch"}, layer="behind"), [])

    def test_long_stickers_still_echo(self):
        out = self.echo("Stickers", {"items": [{"text": "hello launch world now", "at": 0.1, "x": 0, "y": 900}]})
        self.assertTrue(out and out[0].startswith("ECHO Stickers"), out)

    def test_a_notice_quoting_reported_speech_is_exempt(self):
        self.assertEqual(self.echo("Notice", {"from": "A", "text": "launch"}), [])

    def test_other_graphics_still_echo(self):
        self.assertTrue(self.echo("DocCard", {"kicker": "launch", "title": "launch"}))


@unittest.skipUnless(shutil.which("npx") and (MOTION / "node_modules" / "remotion").is_dir(), "needs tools/motion deps")
class StageRenderTest(Fixture):
    """The finished short is drawn on the stage: one video, camera and layers, the low look, no overlay files."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        words = [("uno", 0.3, 1.0), ("dos", 1.5, 2.1), ("tres", 2.6, 3.3)]
        make_take(cls.root / "red.mov", words, d=3.5, color="red")
        (cls.root / "edit" / "transcripts" / "red.json").write_text(json.dumps(
            {"words": [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in words]}))

    def spec(self, **extra) -> dict:
        return {"version": 1, "brand": "none", "sources": {"red": {"file": "red.mov", "face": [54, 96]}},
                "segments": [{"take": "red", "in": 0.2, "out": 1.25}, {"take": "red", "in": 1.3, "out": 3.4,
                                                                         "look": "low", "freeze": 0.4}], **extra}

    def probe(self, path: Path) -> dict:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=width,height,nb_read_frames,codec_name", "-show_entries", "format=duration",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
        d = json.loads(r)
        return {**d["streams"][0], "duration": float(d["format"]["duration"])}

    def frame_saturation(self, path: Path, t: float) -> float:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf",
                              "scale=24:42,format=rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        px = [raw[i:i + 3] for i in range(0, len(raw), 3)]
        return max(max(p) - min(p) for p in px)

    def test_preview_is_drawn_on_the_stage(self):
        spec = self.spec(camera=[{"kind": "pull", "start": 0.1, "end": 0.9}],
                         events=[{"type": "BehindWord", "start": 0.1, "duration": 0.9, "layer": "behind",
                                  "props": {"word": "Hola", "riseAt": 0.1}}])
        p, _ = S.load(self.write(spec), self.root)
        edit = self.root / "edit"
        out = p.build(preview=True)
        info = self.probe(out)
        self.assertEqual((info["width"], info["height"], info["codec_name"]), (720, 1280, "h264"))
        self.assertEqual(int(info["nb_read_frames"]), round(p.offsets()[-1] * 30))
        self.assertAlmostEqual(info["duration"], p.offsets()[-1], delta=0.1)
        # no overlay intermediates, and the cut-out is deleted after the render
        self.assertEqual(sorted(x.name for x in edit.glob("overlay*.mov")), [])
        self.assertEqual(sorted(x.name for x in (edit / "motion_public").glob("person_*")), [])
        self.assertEqual(sorted(x.name for x in (edit / "motion_public").glob("base_*")), [])
        # the pull: the footage shrinks, so the frame edge shows the dark backdrop instead of the red wall
        pulled = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(out), "-frames:v", "1", "-vf",
                                 "crop=4:4:0:600,scale=1:1,format=rgb24", "-f", "rawvideo", "-"],
                                capture_output=True, check=True).stdout
        self.assertLess(max(pulled), 60)

    def test_the_low_look_is_grey_and_holds(self):
        p, _ = S.load(self.write(self.spec()), self.root)
        out = p.build(preview=True)
        t_low = p.offsets()[1]
        self.assertGreater(self.frame_saturation(out, 0.3), 100)  # red before
        self.assertLess(self.frame_saturation(out, t_low + 0.5), 8)  # grey in the low segment
        end = p.offsets()[-1]
        self.assertLess(self.frame_saturation(out, end - 0.1), 8)  # and in its freeze
        self.assertAlmostEqual(p.segments[1].freeze_after, 0.4)
        self.assertEqual(p.low_span(), (p.offsets()[1], p.offsets()[2]))
        self.assertAlmostEqual(self.probe(out)["duration"], end, delta=0.1)

    def test_plain_spec_has_no_camera_and_no_cutout(self):
        p, _ = S.load(self.write(self.spec(segments=[{"take": "red", "in": 0.2, "out": 1.25}])), self.root)
        self.assertEqual(p.person_windows(), [])
        out = p.build(preview=True)
        self.assertEqual(self.probe(out)["width"], 720)
        self.assertGreater(self.frame_saturation(out, 0.3), 100)

    def test_final_is_1080_with_the_delivery_encode(self):
        p, _ = S.load(self.write(self.spec(segments=[{"take": "red", "in": 0.2, "out": 1.25}],
                                           camera=[{"kind": "push", "start": 0.1, "end": 0.9, "amount": 0.05}])), self.root)
        out = p.build(preview=False)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                          "stream=width,height,profile,r_frame_rate,color_space,nb_frames", "-of", "json",
                                          str(out)], capture_output=True, text=True, check=True).stdout)["streams"][0]
        self.assertEqual((info["width"], info["height"], info["profile"], info["r_frame_rate"]), (1080, 1920, "High", "30/1"))
        self.assertEqual(info["color_space"], "bt709")
        loud, _ = SF.loudness(out)
        self.assertAlmostEqual(loud, -14.0, delta=1.0)

    def test_low_voice_graph_is_in_the_mix(self):
        p, _ = S.load(self.write(self.spec()), self.root)
        self.assertEqual(p.low_span(), (p.offsets()[1], p.offsets()[2]))
        self.assertIn("lowpass=f=2400", SF.LOW_VOICE)
        self.assertIn("highpass=f=220", SF.LOW_VOICE)
        self.assertNotIn("1100", SF.LOW_VOICE)  # the rejected two-low-pass version


class WordEdgesTest(Fixture):
    """Segments cut by word anchors (`from` / `to`), resolved into pauses measured against the speech."""

    def test_out_after_a_word(self):
        res = self.check(self.on("take1", {"from": {"word": "launch"}, "to": {"word": "world"}}))
        self.assertEqual(res["errors"], [])
        p, _ = S.load(self.write(self.on("take1", {"from": {"word": "launch"}, "to": {"word": "world"}})), self.root)
        first, last = p.segments[0], p.segments[-1]  # the 0.5 s pause before "world" is dead air: two pieces
        self.assertTrue(1.0 < first.t_in < 1.5, first.t_in)
        self.assertTrue(3.0 <= last.t_out < 3.5, last.t_out)
        self.assertIn(f"{last.t_out:7.2f}", res["timeline"][-1])  # resolved seconds in the timeline

    def test_after(self):
        spec = self.on("take1", {"from": {"word": "hello"}, "to": {"word": "launch", "after": 1.2}})
        p, _ = S.load(self.write(spec), self.root)
        self.assertTrue(2.0 <= p.segments[-1].t_out < 2.5, p.segments[-1].t_out)

    def test_run_on_words(self):
        # one continuous tone: the out is loud (that error stays), but never reported inside a word
        res = self.check(self.on("runon", {"from": {"word": "the"}, "to": {"word": "plan"}}))
        self.assertFalse(any("inside" in m for m in res["errors"] + res["warnings"]), res)
        p, _ = S.load(self.write(self.on("runon", {"in": 0.25, "out": 1.55})), self.root)
        out = S.word_edge(p, "runon", {"word": "plan"}, "out", 9.0)
        self.assertTrue(0.70 <= out <= 0.78, out)

    def test_both_forms(self):
        errs = self.errors(self.on("take1", {"in": 0.4, "from": {"word": "hello"}, "out": 1.1}))
        self.assertTrue(any(e.startswith("segments[0]") and "`in`" in e and "`from`" in e and "one of" in e
                            for e in errs), errs)
        errs = self.errors(self.on("take1", {"in": 0.4}))
        self.assertTrue(any(e.startswith("segments[0]") and "'out'" in e for e in errs), errs)
        errs = self.errors(self.on("take1", {"from": {"word": "hello", "edge": "end"}, "out": 1.1}))
        self.assertTrue(any("segments[0].from" in e and "'edge'" in e for e in errs), errs)

    def test_word_not_in_take(self):
        errs = self.load_errors(self.on("take1", {"from": {"word": "hello", "after": 2.0}, "out": 3.1}))
        self.assertTrue(any(e.startswith("segments[0].from") and "'hello'" in e and "take1" in e for e in errs), errs)

    def test_breath_after_a_word(self):
        p, _ = S.load(self.write(self.on("breath", {"from": {"word": "we"}, "to": {"word": "plan"}})), self.root)
        out = p.segments[0].t_out
        self.assertTrue(0.72 < out < 0.96, out)  # in the pause, before the breath

    def test_click_beside_the_cut(self):
        # the click is merged into the pause (noise flicker); the out moves past it, so it isn't played or loud
        spec = self.on("click", {"from": {"word": "we"}, "to": {"word": "we"}})
        res = self.check(spec)
        self.assertEqual(res["errors"], [])
        self.assertFalse(any("sound" in w for w in res["warnings"]), res)
        p, _ = S.load(self.write(spec), self.root)
        self.assertGreater(p.segments[0].t_out, 0.70 + 0.02)

    def test_dead_air_split(self):
        spec = self.on("pause", {"from": {"word": "uno"}, "to": {"word": "tres."}, "zoom": {"kind": "static", "scale": 1.1}})
        res = self.check(spec)
        self.assertEqual(res["errors"], [])
        p, _ = S.load(self.write(spec), self.root)
        a, b = p.segments
        self.assertEqual((a.zoom, b.zoom), (("static", 1.1), ("static", 1.1)))
        self.assertTrue(1.2 < a.t_out < 1.4 and 1.6 < b.t_in < 1.82, (a.t_out, b.t_in))
        self.assertLessEqual((a.t_out - 1.2) + (1.82 - b.t_in), 0.25)  # the silence the output keeps there
        self.assertEqual(len(res["timeline"]), 3)
        self.assertTrue(res["timeline"][1].lstrip().startswith("0.0") and res["timeline"][2].lstrip().startswith("0.1"),
                        res["timeline"])

    def test_pause_found_from_both_sides(self):
        # "y" is stamped over the whole pause after "dos": both gaps find it; it is cut once
        TAKE = self.root / "edit" / "transcripts" / "pause.json"
        orig = TAKE.read_text()
        self.addCleanup(TAKE.write_text, orig)
        data = json.loads(orig)
        data["words"][1:2] = [{"type": "word", "text": "dos", "start": 0.8, "end": 1.1},
                              {"type": "word", "text": "y", "start": 1.1, "end": 1.8}]
        TAKE.write_text(json.dumps(data))
        p, _ = S.load(self.write(self.on("pause", {"from": {"word": "uno"}, "to": {"word": "tres."}})), self.root)
        self.assertEqual(len(p.segments), 2)
        self.assertTrue(all(s.t_out - s.t_in >= 0.1 for s in p.segments), [(s.t_in, s.t_out) for s in p.segments])

    def test_seconds_segment_not_split(self):
        p, _ = S.load(self.write(self.on("pause", {"in": 0.25, "out": 2.4})), self.root)
        self.assertEqual(len(p.segments), 1)

    def test_seg_anchor_spans_pieces(self):
        spec = self.on("pause", {"from": {"word": "uno"}, "to": {"word": "tres."}})
        spec["events"] = [{"type": "HookTitle", "start": 0, "end": {"seg": 0, "edge": "end"},
                           "props": {"lines": [{"text": "Hi"}]}}]
        p, _ = S.load(self.write(spec), self.root)
        self.assertAlmostEqual(p.events[0]["duration"], round(p.offsets()[-1], 3), places=3)


class FaultsTest(Fixture):
    """Restarts and untranscribed speech kept, strict mode, and the scene/backdrop mismatch."""

    def test_false_start_inside_a_segment(self):
        res = self.check(self.on("restart", {"in": 0.0, "out": 3.1}))
        e = next(e for e in res["errors"] if "false start" in e)
        for part in ("segments[0]", '"hello"', "0.50–1.00", "1.50"):
            self.assertIn(part, e)

    def test_split_suggested_when_the_segment_starts_earlier(self):
        spec = self.on("restart", {"in": 0.0, "out": 3.1})
        TAKE = self.root / "edit" / "transcripts" / "restart.json"
        orig = TAKE.read_text()
        self.addCleanup(TAKE.write_text, orig)
        data = json.loads(orig)
        data["restarts"] = [{"abandoned": [1.5, 2.0], "again": 2.5, "words": "launch"}]
        TAKE.write_text(json.dumps(data))
        e = next(e for e in self.check(spec)["errors"] if "false start" in e)
        self.assertIn("end it at 1.50", e)
        self.assertIn("2.50", e)

    def test_only_the_restart_kept(self):
        res = self.check(self.on("restart", {"in": 1.45, "out": 3.1}))
        self.assertFalse(any("false start" in m for m in res["errors"] + res["warnings"]), res)

    def test_keep_restart(self):
        res = self.check(self.on("restart", {"in": 0.0, "out": 3.1, "keep_restart": True}))
        self.assertFalse(any("false start" in e for e in res["errors"]), res)
        self.assertTrue(any("false start" in w for w in res["warnings"]), res)
        res = self.check(self.on("restart", {"in": 0.0, "out": 3.1, "keep_restart": True}), strict=True)
        self.assertTrue(any("segments[0].keep_restart" in e for e in res["errors"]), res)
        self.assertTrue(any("false start" in e for e in res["errors"]), res)

    def test_untranscribed_kept(self):
        res = self.check(self.on("restart", {"in": 1.1, "out": 1.6}))
        w = next(w for w in res["warnings"] if "1.20–1.40" in w)
        self.assertIn("segments[0]", w)
        self.assertIn("no words", w)
        res = self.check(self.on("restart", {"in": 1.1, "out": 1.6}), strict=True)
        self.assertTrue(any("1.20–1.40" in e for e in res["errors"]), res)

    def test_lock_refused_in_strict(self):
        spec = self.on("take1", {"in": 0.45, "out": 1.05}, {"in": 1.45, "out": 3.05, "lock_out": True})
        res = self.check(spec, strict=True)
        e = next(e for e in res["errors"] if "segments[1].lock_out" in e)
        self.assertIn("locks aren't accepted", e)
        self.assertIn("pause or between words", e)
        res = self.check(spec)
        self.assertFalse(any("lock_out" in m for m in res["errors"]), res)

    def test_echo_blocks_in_strict(self):
        spec = self.on("take1", {"in": 0.45, "out": 3.05})
        spec["events"] = [{"type": "HookTitle", "start": 0.5, "duration": 1.0, "props": {"lines": [{"text": "launch"}]}}]
        self.assertTrue(any(w.startswith("ECHO") for w in self.check(spec)["warnings"]))
        self.assertTrue(any(e.startswith("ECHO") for e in self.check(spec, strict=True)["errors"]))

    def test_strict_load_raises(self):
        spec = self.on("take1", {"in": 0.45, "out": 3.05, "lock_in": True})
        S.load(self.write(spec), self.root)
        with self.assertRaises(S.SpecError) as cm:
            S.load(self.write(spec), self.root, strict=True)
        self.assertTrue(any("lock_in" in e for e in cm.exception.errors))

    def test_dark_scene_on_light_backdrop(self):
        spec = self.on("take1", {"in": 0.45, "out": 3.05})
        spec["events"] = [{"type": "StatScene", "start": 0, "duration": 1.0, "props": {"value": 3, "bg": "dark", "full": True}}]
        spec["events"][0]["duration"] = 2.5
        e = next(e for e in self.load_errors(spec) if e.startswith("events[0]"))
        self.assertIn('"dark": true', e)
        self.assertIn('"bg": "dark"', e)
        spec["events"][0]["props"]["dark"] = True
        S.load(self.write(spec), self.root)

    def test_never_list(self):
        self.assertEqual(len(S.NEVER_LIST), 10)
        r = subprocess.run([sys.executable, str(TOOLS / "shortform.py"), "check", "--never-list"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 10)
        for n, ln in enumerate(lines, 1):
            self.assertTrue(ln.lstrip().startswith(f"{n}."), ln)




@unittest.skipUnless(shutil.which("npx") and (MOTION / "node_modules" / "remotion").is_dir(), "needs tools/motion deps")
class StillsTest(Fixture):
    """Remotion-backed: per-event stills, failures that name the event, legibility probe, caption placement."""

    def one(self, *events, captions=None) -> dict:
        spec = self.segs(("take1", 0.45, 3.05))
        spec["events"] = list(events)
        if captions:
            spec["captions"] = {"props": captions}
        return spec

    def setUp(self):
        shutil.rmtree(self.root / "edit" / "stills", ignore_errors=True)
        (self.root / "edit" / "overlay_boxes.json").unlink(missing_ok=True)

    def test_event_stills_with_times(self):
        p, _ = S.load(self.write(self.one({"type": "KineticType", "start": 0.3, "duration": 1.5,
                                           "props": {"lines": [{"text": "Hello there"}]}})), self.root)
        out = p.stills([0.2, 2.0])
        names = sorted(st["path"].name for st in out)
        self.assertEqual(names, ["ev00_KineticType_001.20.png", "short_000.20.png", "short_002.00.png"])
        self.assertTrue(all(st["path"].is_file() for st in out))
        ev = next(st for st in out if "event" in st)
        self.assertEqual((ev["event"], ev["type"], ev["t"]), (0, "KineticType", 1.2))

    def test_event_still_after_late_cue(self):
        p, _ = S.load(self.write(self.one({"type": "ListScene", "start": 0.0, "duration": 2.5,
                                           "props": {"items": [{"text": t} for t in "abc"]}})), self.root)
        self.assertEqual(p._still_time(p.events[0]), round(1.7 + 14 / 30 + 1 / 30, 2))  # not 1.2: the last item is in

    def test_behind_word_is_covered_by_the_speaker(self):
        """A behind word overlapping the speaker: where the matte says "person" the still shows the footage."""
        from unittest import mock

        def left_half_person(base, out, fps=30, backend=None):  # the "speaker": the left half of the frame
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), "-vf",
                            "format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lt(X,W/2),255,0)'",
                            "-frames:v", "1", str(out)], check=True)
            return out

        word = {"type": "BehindWord", "start": 0.3, "duration": 1.5, "layer": "behind",
                "props": {"word": "HOLA", "riseAt": 0.0, "y": 640}}
        p, _ = S.load(self.write(self.one(word)), self.root)
        with mock.patch.object(SF, "cutout_still", left_half_person):
            out = p.stills([1.0])
        png = next(st["path"] for st in out if st.get("type") == "BehindWord")
        img = p._rgba(png)[:, :, :3]
        h, w = img.shape[:2]
        band = img[round(h * 0.34):round(h * 0.45)]  # the word's rows (y 640–860 of 1920)
        light = (band.min(axis=2) > 200)  # the word is near-white; the gray wall is not
        self.assertEqual(int(light[:, :w // 2].sum()), 0)  # under the speaker: hidden
        self.assertGreater(int(light[:, w // 2:].sum()), 200)  # beside the speaker: drawn

    def test_stills_show_the_camera(self):
        spec = self.one({"type": "HookTitle", "start": 0.3, "duration": 1.5, "props": {"lines": [{"text": "Hola"}]}})
        spec["camera"] = [{"kind": "pull", "start": 0.2, "end": 1.9}]
        p, _ = S.load(self.write(spec), self.root)
        out = p.stills([1.0])
        img = p._rgba(next(st["path"] for st in out if st["path"].name.startswith("short_")))[:, :, :3]
        h, w = img.shape[:2]
        self.assertLess(int(img[h // 2, 2].max()), 60)  # the footage is pulled back: the brand's ink shows at the edge
        self.assertGreater(int(img[h // 2, w // 2].min()), 100)  # and the gray wall is in the middle

    def test_failure_names_the_event(self):
        from errors import ToolError
        p, _ = S.load(self.write(self.one({"type": "ListScene", "start": 0.35, "duration": 2.0,
                                           "props": {"items": [{"text": "a", "at": 0.5}]}})), self.root)
        p.events[0]["props"]["items"][0]["at"] = "late"  # past validation: sec("late") is NaN inside Remotion
        with self.assertRaises(ToolError) as cm:
            p.stills([0.2])
        self.assertTrue(cm.exception.summary.startswith("events[0] (ListScene) failed at 1.55 s: "), cm.exception.summary)
        self.assertRegex(cm.exception.summary, r"finite|NaN")
        self.assertFalse(str(cm.exception.code).startswith("FAILED: npx remotion"))

    def test_probe_text_out_of_frame(self):
        lines = [{"text": "Read this title", "at": 0.2}]
        p, _ = S.load(self.write(self.one({"type": "KineticType", "start": 0, "duration": 2.0,
                                           "props": {"lines": lines, "frame": {"y": 1900}}})), self.root)
        warnings = []
        p.measure_events(warnings=warnings)
        self.assertTrue(any(w.startswith("events[0] (KineticType) shows almost no text") for w in warnings), warnings)
        p, _ = S.load(self.write(self.one({"type": "KineticType", "start": 0, "duration": 2.0,
                                           "props": {"lines": lines}})), self.root)
        warnings = []
        p.measure_events(warnings=warnings)
        self.assertEqual(warnings, [])

    def test_captions_clear_scene_text(self):
        stat = {"type": "StatScene", "start": 0, "duration": 2.4,
                "props": {"value": 42, "size": 440, "full": True, "label": "a label\nthat runs\nthree lines"}}
        p, _ = S.load(self.write(self.one(stat, captions={"top": 1250})), self.root)
        warnings = []
        out = p.stills([2.5], warnings=warnings)
        self.assertEqual(warnings, [])
        box = next(iter(json.loads((self.root / "edit" / "overlay_boxes.json").read_text()).values()))["box"]
        self.assertGreater(box[3], 1250 - 60)  # the label reaches the caption band
        caps = json.loads((self.root / "edit" / "overlay_props.json").read_text())["events"][-1]["props"]
        self.assertEqual(caps["avoid"], [[0.0, 2.4, box[3] + 60]])  # moved for the event only; 1250 elsewhere
        self.assertEqual(caps["top"], 1250)
        # captions alone at the event's still time: no caption pixel inside the label's box
        alone = {**p.caption_event()}
        pj = p._props_file([alone], self.root / "edit" / "caps.json")
        png = self.root / "edit" / "caps.png"
        p._still(pj, p._still_time(p.events[0]), png, 0.5, self.root / "edit" / "motion_public")
        img = p._rgba(png)
        k = img.shape[1] / 1080
        x0, y0, x1, y1 = (round(v * k) for v in box)
        self.assertEqual(int((img[y0:y1, x0:x1, 3] > 8).sum()), 0)
        self.assertGreater(int((img[:, :, 3] > 8).sum()), 0)  # the captions are on screen
        self.assertEqual({st["path"].name for st in out}, {"short_002.50.png", "ev00_StatScene_001.67.png"})  # after the label


@unittest.skipUnless(shutil.which("npx") and (MOTION / "node_modules" / "remotion").is_dir(), "needs tools/motion deps")
class ProbeTest(Fixture):
    """The legibility probe over the real frame, text over the face, text size, captions and placement."""

    def setUp(self):
        shutil.rmtree(self.root / "edit" / "stills", ignore_errors=True)
        (self.root / "edit" / "overlay_boxes.json").unlink(missing_ok=True)

    def probe(self, take: str, *events, head=None, captions=None):
        spec = self.on(take, {"in": 0.45, "out": 3.05})
        if head:
            spec["sources"][take]["head"] = head
        spec["events"] = list(events)
        if captions:
            spec["captions"] = {"props": captions}
        p, _ = S.load(self.write(spec), self.root)
        warnings = []
        p.measure_events(warnings=warnings)
        return p, warnings + p.caption_warnings()

    def kinds(self, warnings) -> dict:
        out = {}
        for w in warnings:
            out.setdefault(w.kind, []).append(w)
        return out

    def test_pale_text_on_white(self):
        _, ws = self.probe("white", {"type": "NameTitle", "start": 0, "duration": 2.4,
                                     "props": {"text": "Read me", "color": "#E8FD5A", "top": 300}})
        (w,) = self.kinds(ws)["contrast"]
        self.assertRegex(w, r"^events\[0\] \(NameTitle\) text contrast 1\.\d:1 at [\d.]+ s is under 3:1")

    def test_bare_number_on_bright_wall(self):
        stat = {"type": "StatScene", "start": 0, "duration": 2.4, "props": {"value": 500, "bg": "none"}}
        _, ws = self.probe("bright", stat)
        self.assertIn("contrast", self.kinds(ws), ws)
        _, ws = self.probe("take1", {**stat, "props": {"value": 500}})  # dark number on the grey wall reads
        self.assertNotIn("contrast", self.kinds(ws), ws)

    def test_floating_stat_across_the_face(self):
        stat = {"type": "StatScene", "start": 0, "duration": 2.4,
                "props": {"value": 500, "prefix": "$", "suffix": " mil", "kicker": "Kicker", "label": "a label",
                          "bg": "none", "frame": {"scale": 1, "y": 0}}}
        p, ws = self.probe("bright", stat, head=HEAD)
        k = self.kinds(ws)
        self.assertTrue(k["face"][0].startswith("events[0] (StatScene) text covers the speaker's face at "), k)
        self.assertIn("kicker", k["contrast"][0])
        errors, _ = S.strict_split(ws)
        self.assertTrue(any(e.kind == "face" for e in errors) and any(e.kind == "contrast" for e in errors))

    def test_tiny_kicker(self):
        stat = {"type": "StatScene", "start": 0, "duration": 2.4,
                "props": {"value": 5, "kicker": "Kicker", "full": True, "frame": {"scale": 0.5}}}
        _, ws = self.probe("take1", stat)
        (w,) = self.kinds(ws)["small_text"]
        self.assertTrue(w.startswith("events[0] (StatScene) kicker text is 15 px tall, under 28 px"), w)
        groups = json.loads((self.root / "edit" / "overlay_text.json").read_text())["0"]["texts"]
        self.assertEqual(next(g for g in groups if g["field"] == "kicker")["size"], 15)

    def test_placed_above_the_head(self):
        name = {"type": "NameTitle", "start": 0, "duration": 2.4, "props": {"text": "Alex"}}
        p, ws = self.probe("take1", name, head=HEAD)
        self.assertNotIn("face", self.kinds(ws), ws)
        frame = p.events[0]["props"]["frame"]
        self.assertLess(frame["y"], 0)  # moved up
        box = json.loads((self.root / "edit" / "overlay_boxes.json").read_text())[p._box_key(p.events[0])]["text"]
        self.assertLessEqual(box[3], HEAD[1] * 10 - SF.HEAD_GAP)  # just above the head
        self.assertGreaterEqual(box[1], SF.PLACE_TOP)
        # without a head box (no person) nothing moves
        p, _ = self.probe("take1", name)
        self.assertNotIn("frame", p.events[0]["props"])

    def test_a_behind_word_goes_above_the_head(self):
        word = {"type": "BehindWord", "start": 0, "duration": 2.4, "layer": "behind", "props": {"word": "Alex", "riseAt": 0.1, "size": 80, "y": 800}}
        p, ws = self.probe("take1", word, head=[HEAD[0], 50, HEAD[2], HEAD[3]])
        self.assertIn("frame", p.events[0]["props"])
        self.assertLess(p.events[0]["props"]["frame"]["y"], 0)

    def test_behind_text_over_the_head(self):
        # under the speaker's cut-out: the speaker covers it, so it isn't text over the face (and isn't moved)
        name = {"type": "NameTitle", "start": 0, "duration": 2.4, "props": {"text": "Alex", "behind": True}}
        p, ws = self.probe("take1", name, head=HEAD)
        self.assertNotIn("face", self.kinds(ws), ws)
        self.assertNotIn("frame", p.events[0]["props"])

    def test_does_not_fit_above_the_head(self):
        receipt = {"type": "Receipt", "start": 0, "duration": 2.4,
                   "props": {"title": "This month", "items": [{"text": "Rent", "at": 0.2}, {"text": "Food", "at": 0.4}],
                             "total": "$1,220"}}
        p, ws = self.probe("take1", receipt, head=[HEAD[0], 15, HEAD[2], HEAD[3]])  # no room at all above this head
        w = next(w for w in ws if w.kind == "face")
        self.assertIn("fits above the speaker's head only at", w)
        self.assertIn('"full": true', w)
        self.assertNotIn("frame", p.events[0]["props"])

    def test_pale_accent_receipt_reads(self):
        # brand-theme: the receipt's stamp in a pale accent is drawn in a darker shade that reads on the card
        spec = self.on("white", {"in": 0.45, "out": 3.05})
        spec["events"] = [{"type": "Receipt", "start": 0, "duration": 2.4,
                           "props": {"title": "This month", "items": [{"text": "Rent", "at": 0.1}], "total": "$900",
                                     "stamp": "PAID", "stampAt": 0.3}}]
        p, _ = S.load(self.write(spec), self.root)
        p.brand = {**p.brand, "colors": {**p.brand["colors"], "accent": "#E8FD5A", "ink": "#16150F"}}
        warnings = []
        p.measure_events(warnings=warnings)
        self.assertNotIn("contrast", self.kinds(warnings), warnings)
        texts = json.loads((self.root / "edit" / "overlay_text.json").read_text())["0"]["texts"]
        self.assertIn("stamp", [g["field"] for g in texts])

    def test_captions_on_overlay_text(self):
        tall = {"type": "NameTitle", "start": 0, "duration": 2.4,
                "props": {"lines": [{"text": t} for t in ("one", "two", "three", "four", "five")], "top": 400}}
        _, ws = self.probe("take1", tall, captions={"top": 830})
        (w,) = self.kinds(ws)["captions_on_text"]
        self.assertTrue(w.startswith("captions cover events[0] (NameTitle) text at "), w)


class ChunksTest(unittest.TestCase):
    """Caption phrases break where Whisper glued two sentences together without a full stop."""

    def project(self, transcript: str):
        from shortform import Project
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        (d / "transcripts").mkdir()
        words = [{"type": "word", "text": t, "start": i, "end": i + 0.5} for i, t in enumerate(transcript.split())]
        (d / "transcripts" / "t.json").write_text(json.dumps({"words": words}))
        return Project(d, {"t": d / "t.mov"}, {"t": (0, 0)}, [], brand=None)

    def phrases(self, p, cut: str) -> list[str]:
        words = [{"text": t, "start": i * 0.2, "end": i * 0.2 + 0.15, "seg": 0} for i, t in enumerate(cut.split())]
        return [" ".join(w["text"] for w in c) for c in p.chunks(words, max_words=6, max_chars=30)]

    def test_segment_join_breaks(self):
        p = self.project("y entonces vamos a ver nuestro dinero Entonces te voy a contar")
        self.assertEqual(self.phrases(p, "nuestro dinero Entonces te voy a"), ["nuestro dinero", "Entonces te voy a"])

    def test_proper_noun_kept(self):
        p = self.project("yo vivo en Lisboa desde hace años y Lisboa me encanta")
        self.assertEqual(self.phrases(p, "vivo en Lisboa desde"), ["vivo en Lisboa desde"])

    def test_english_i_kept(self):
        p = self.project("i mean and I think so and i know")
        self.assertEqual(self.phrases(p, "and I think so"), ["and I think so"])

    def test_more_punctuation_breaks(self):
        p = self.project("uno: dos; tres… cuatro")
        self.assertEqual(self.phrases(p, "uno: dos; tres… cuatro"), ["uno:", "dos;", "tres…", "cuatro"])



class AnyFrameRate(unittest.TestCase):
    """conform keeps 24 and 25 fps. A zoomed segment must last as long as its audio at any of them."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.root = cls.tmp / "demo"
        (cls.root / "edit" / "transcripts").mkdir(parents=True)
        for fps in (24, 25, 30):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=108x192:r={fps}:d=3.5",
                            "-f", "lavfi", "-i", "aevalsrc='sin(2*PI*220*t)':s=48000:d=3.5", "-shortest", "-c:v", "libx264",
                            "-c:a", "pcm_s16le", str(cls.root / f"t{fps}.mov")], check=True)
            (cls.root / "edit" / "transcripts" / f"t{fps}.json").write_text(json.dumps({"words": []}))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def project(self, fps: int):
        spec = {"version": 1, "brand": "none", "sources": {f"t{fps}": {"file": f"t{fps}.mov", "face": [54, 96]}},
                "segments": [{"take": f"t{fps}", "in": 0.5, "out": 3.0, "lock_in": True, "lock_out": True,
                              "zoom": {"kind": "punch", "base": 1.0, "peak": 1.12, "at": 1.0}}]}
        path = self.root / "edit" / "short.json"
        path.write_text(json.dumps(spec))
        return S.load(path, self.root)[0]

    def test_a_zoomed_segment_keeps_its_length(self):
        for fps in (24, 25, 30):
            p = self.project(fps)
            s = p.segments[0]
            out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s.t_in:.3f}", "-t", f"{s.dur:.3f}", "-i", str(p.sources[s.take]),
                                  "-vf", p._vf(s, 108, 192), "-f", "null", "-", "-progress", "pipe:1"],
                                 capture_output=True, text=True, check=True).stdout
            frames = int(out.split("frame=")[-1].split()[0])
            self.assertAlmostEqual(frames / 30, s.dur + s.freeze_after, delta=0.07, msg=f"{fps} fps")  # the last segment holds the end tail

    def test_a_still_near_the_end_of_a_zoomed_segment(self):
        p = self.project(24)
        dst = self.root / "edit" / "base.png"
        p._base_frame(p.offsets()[1] - 0.05, 108, 192, dst)
        self.assertTrue(dst.exists())

    def test_a_frame_that_cannot_be_made_is_named(self):
        p = self.project(30)
        with mock.patch.object(p, "_vf", return_value="trim=start=999,format=yuv420p"):
            with self.assertRaises(ToolError) as e:
                p._base_frame(1.0, 108, 192, self.root / "edit" / "none.png")
        self.assertIn("no frame at 1.00 s", str(e.exception.summary))



class HeadPerMoment(unittest.TestCase):
    """A graphic sits above the head as it is while the graphic is on screen, and keeps where it was placed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.root = cls.tmp / "demo"
        (cls.root / "edit" / "transcripts").mkdir(parents=True)
        make_take(cls.root / "t.mov", [("", 0.5, 3.0)])
        (cls.root / "edit" / "transcripts" / "t.json").write_text(json.dumps({"words": []}))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def project(self):
        spec = {"version": 1, "brand": "none", "sources": {"t": {"file": "t.mov", "face": [54, 96], "head": [30, 40, 80, 90]}},
                "segments": [{"take": "t", "in": 0.5, "out": 3.0, "lock_in": True, "lock_out": True}]}
        path = self.root / "edit" / "short.json"
        path.write_text(json.dumps(spec))
        return S.load(path, self.root)[0]

    def test_the_head_is_measured_while_the_event_is_on_screen(self):
        p = self.project()
        with mock.patch.object(p, "_head_tops", return_value=[50.0, 50.0, 20.0, 60.0]):
            early = p.head_box({"start": 0.0, "duration": 0.4})   # source 0.5–0.9 s
            late = p.head_box({"start": 1.6, "duration": 0.9})    # source 2.1–3.0 s
        self.assertEqual(early[1], 50 * 10 - SF.HEAD_GAP)
        self.assertEqual(late[1], 20 * 10 - SF.HEAD_GAP)

    def test_without_a_track_the_take_wide_box_applies(self):
        p = self.project()
        with mock.patch.object(p, "_head_tops", return_value=[]):
            self.assertEqual(p.head_box({"start": 0.0, "duration": 1.0})[1], 40 * 10 - SF.HEAD_GAP)

    def test_placement_uses_the_band_up_to_the_head(self):
        frame, s = SF.Project._place([240, 200, 840, 400], [100, 500, 980, 900], [40])
        self.assertEqual(s, 1.0)
        self.assertEqual(frame["y"], 500 - 200 - 200)  # its bottom just above the head, not up at the limit

    def test_a_card_rises_only_as_far_as_it_must(self):
        frame, s = SF.Project._place([240, 200, 840, 500], [100, 300, 980, 900], [60])
        self.assertLess(s, 1.0)
        self.assertEqual(frame["y"], round(SF.PLACE_TOP - s * 200))  # the whole band: at the limit, and scaled to fit

    def test_a_move_that_holds_goes_by_where_it_puts_the_head(self):
        p = self.project()
        p.camera = [{"kind": "side", "start": 0.0, "end": 10.0}]
        side = SF.CAMERA_MOVES["side"]
        moved = p._under_camera([100.0, 400.0, 500.0, 800.0], 1.0, 3.0)
        self.assertAlmostEqual(moved[1], side["origin"][1] + side["scale"] * (400 - side["origin"][1]))
        self.assertAlmostEqual(moved[0], side["origin"][0] + side["scale"] * (100 - side["origin"][0]) + side["tx"])

    def test_a_move_that_passes_through_counts_both(self):
        p = self.project()
        p.camera = [{"kind": "side", "start": 2.5, "end": 3.0}]
        moved = p._under_camera([100.0, 400.0, 500.0, 800.0], 1.0, 3.0)
        side = SF.CAMERA_MOVES["side"]
        self.assertAlmostEqual(moved[1], side["origin"][1] + side["scale"] * (400 - side["origin"][1]))  # the highest
        self.assertEqual(moved[3] >= 800.0, True)

    def test_a_placement_belongs_to_its_head(self):
        p = self.project()
        event = {"type": "NameTitle", "start": 0.0, "duration": 1.0, "props": {"text": "Alex"}}
        with mock.patch.object(p, "_head_tops", return_value=[50.0, 50.0]):
            near = p._placed_key(event)
        with mock.patch.object(p, "_head_tops", return_value=[20.0, 20.0]):
            self.assertNotEqual(near, p._placed_key(event))

    def test_the_camera_ts_uses_the_shared_values(self):
        ts = (TOOLS / "motion" / "src" / "stage" / "camera.ts").read_text()
        self.assertIn('from "./camera.json"', ts)
        self.assertNotRegex(ts, r"\b(1040|1880|170)\b")

    def test_text_on_the_frame_takes_the_colour_that_reads_there(self):
        import numpy as np
        p = self.project()
        p.brand = {"colors": {"ink": "#111111"}}
        small = [{"box": [100, 100, 500, 200], "size": 30}]
        light, dark, grey = (np.full((1920, 1080, 3), v, float) for v in (235.0, 15.0, 121.0))
        self.assertEqual(p._colour_that_reads(light, small), "#111111")
        self.assertEqual(p._colour_that_reads(dark, small), "#FFFFFF")
        self.assertEqual(p._colour_that_reads(grey, small), "#000000")  # neither the brand's dark nor white reaches 4.5:1

    def test_no_colour_reads_when_nothing_reaches_the_contrast(self):
        import numpy as np
        p = self.project()
        p.brand = {"colors": {"ink": "#777777"}}
        half = np.full((1920, 1080, 3), 255.0)
        half[:, 540:] = 0.0
        two = [{"box": [100, 100, 500, 200], "size": 30}, {"box": [600, 100, 1000, 200], "size": 30}]
        self.assertIsNone(p._colour_that_reads(half, two))

    def test_a_card_too_tall_to_read_is_refused(self):
        frame, s = SF.Project._place([240, 200, 840, 1200], [100, 500, 980, 900], [40])
        self.assertIsNone(frame)
        self.assertLess(s, 1.0)


if __name__ == "__main__":
    unittest.main()
