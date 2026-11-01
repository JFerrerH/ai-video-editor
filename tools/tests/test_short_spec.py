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
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import short_spec as S  # noqa: E402

# three tone bursts with silence between: "hello" 0.5–1.0, "launch" 1.5–2.0, "world" 2.5–3.0
WORDS = [("hello", 0.5, 1.0), ("launch", 1.5, 2.0), ("world", 2.5, 3.0)]


def make_take(path: Path, words=WORDS) -> None:
    expr = "+".join(f"between(t,{a},{b})" for _, a, b in words)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=108x192:r=30:d=3.5",
                    "-f", "lavfi", "-i", f"aevalsrc='0.5*sin(2*PI*220*t)*({expr})':s=48000:d=3.5",
                    "-shortest", "-c:v", "libx264", "-c:a", "pcm_s16le", str(path)], check=True)


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
        self.assertEqual(res["errors"], [])
        self.assertTrue(any(w.startswith('segments[0].in 1.20 is inside "empezar" (0.50–1.60): use 0.50 or 1.60')
                            for w in res["warnings"]), res["warnings"])

    def test_loud_head(self):
        res = S.check(self.write(self.segs(("take2", 2.2, 3.4), take2=True)), self.root)
        e = next(e for e in res["errors"] if e.startswith("segments[0].in"))
        self.assertIn("starts in the middle of sound", e)
        self.assertRegex(e, r"\+\d+\.\d dB over the room tone")
        self.assertFalse(any("<-- check" in m for m in res["errors"] + res["warnings"] + res["edges"]))

    def test_captions_fit_nowhere_warns(self):
        spec = self.segs(("take1", 0.45, 3.05))
        spec["events"] = [{"type": "StatScene", "start": 0, "duration": 2.0, "props": {"value": 1}}]
        p, _ = S.load(self.write(spec), self.root)
        boxes = self.root / "edit" / "overlay_boxes.json"
        self.addCleanup(boxes.unlink, missing_ok=True)
        boxes.write_text(json.dumps({p._box_key(p.events[0]): {"box": [100, 400, 980, 1500]}}))
        self.assertNotIn("avoid", p.caption_event()["props"])
        (w,) = p.caption_warnings()
        self.assertTrue(w.startswith("events[0] (StatScene): its content (400–1500 px) reaches the captions"), w)
        boxes.write_text(json.dumps({p._box_key(p.events[0]): {"box": [100, 700, 980, 1260]}}))
        self.assertEqual(p.caption_event()["props"]["avoid"], [[0.0, 2.0, 1320]])
        self.assertEqual(p.caption_warnings(), [])

    def test_check_warns_on_close_sfx(self):
        spec = self.mutate(lambda s: s["sfx"].append({"name": "pop", "at": {"word": "launch", "take": "take1",
                                                                             "offset": 0.2}}))
        res = S.check(self.write(spec), self.root)
        self.assertEqual(res["errors"], [])
        self.assertTrue(any("apart" in w for w in res["warnings"]), res["warnings"])


MOTION = TOOLS / "motion"


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
                "props": {"value": 42, "size": 440, "kicker": "Kicker", "label": "a label\nthat runs\nthree lines"}}
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


if __name__ == "__main__":
    unittest.main()
