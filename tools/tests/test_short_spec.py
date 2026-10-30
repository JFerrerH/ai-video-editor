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


def make_take(path: Path) -> None:
    expr = "+".join(f"between(t,{a},{b})" for _, a, b in WORDS)
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
               {"type": "HookTitle", "start": {"word": "launch", "take": "take1"}, "duration": 0.5}],
    "sfx": [{"name": "click", "at": {"word": "launch", "take": "take1", "offset": 0.05}, "gain_db": -15}],
}


class SpecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.root = cls.tmp / "demo"
        (cls.root / "edit" / "transcripts").mkdir(parents=True)
        make_take(cls.root / "take1.mov")
        words = [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in WORDS]
        (cls.root / "edit" / "transcripts" / "take1.json").write_text(json.dumps({"words": words}))

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

    def test_check_warns_on_close_sfx(self):
        spec = self.mutate(lambda s: s["sfx"].append({"name": "pop", "at": {"word": "launch", "take": "take1",
                                                                             "offset": 0.2}}))
        res = S.check(self.write(spec), self.root)
        self.assertEqual(res["errors"], [])
        self.assertTrue(any("apart" in w for w in res["warnings"]), res["warnings"])


if __name__ == "__main__":
    unittest.main()
