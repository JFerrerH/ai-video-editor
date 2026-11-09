"""Layout and cut invariants (openspec change layout-and-cut-invariants): graphics stay inside their card and the
frame, captions keep clear of the head, cuts have air, the video ends with a tail.

    uv run python -m unittest tools.tests.test_invariants
"""

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))

import shortform as SF  # noqa: E402
import short_spec as S  # noqa: E402
from test_short_spec import Fixture, make_take  # noqa: E402

MOTION = TOOLS / "motion"
REMOTION = shutil.which("npx") is not None and (MOTION / "node_modules" / "remotion").is_dir()


def bars(*labels, at=(0.2, 0.5, 0.8)):
    return {"type": "AgeBars", "start": 0, "duration": 2.4,
            "props": {"bars": [{"value": 60 - 10 * i, "label": w, "at": at[i]} for i, w in enumerate(labels)]}}


class Containment(Fixture):
    """`_outside` on boxes written by hand: the rule itself, with no component needed to be broken."""

    def check(self, *measured):
        spec = self.on("bright", {"in": 0.45, "out": 3.05})
        spec["events"] = [bars("You", "Managers", "Clients")]
        p, _ = S.load(self.write(spec), self.root)
        return p._outside(p.events[0], "events[0] (AgeBars)", list(measured))

    @staticmethod
    def text(box, card=(200, 300, 880, 700)):
        return {"text": "Extraordinary", "box": list(box), "size": 44, "card": list(card)}

    def test_text_past_its_card(self):
        out = self.check((1.5, [self.text((560, 320, 900, 380))], []))
        self.assertTrue(out and "card's right edge" in out[0] and "20 px" in out[0], out)

    def test_reported_at_the_first_time_it_shows(self):
        out = self.check((1.0, [self.text((300, 320, 600, 380))], []), (1.5, [self.text((560, 320, 900, 380))], []),
                         (2.0, [self.text((560, 320, 900, 380))], []))
        self.assertEqual(len(out), 1)
        self.assertIn("at 1.50 s", out[0])

    def test_text_below_the_safe_band(self):
        out = self.check((1.0, [self.text((300, 1500, 600, 1560), card=(200, 1400, 880, 1600))], []))
        self.assertTrue(out and "bottom limit" in out[0], out)

    def test_everything_inside(self):
        self.assertEqual(self.check((1.0, [self.text((300, 320, 600, 380))], [])), [])

    def test_strict_makes_it_an_error(self):
        errors, _ = S.strict_split(self.check((1.5, [self.text((560, 320, 900, 380))], [])))
        self.assertTrue(errors)


@unittest.skipUnless(REMOTION, "needs tools/motion deps")
class Geometry(Fixture):
    def findings(self, event: dict) -> list:
        spec = self.on("bright", {"in": 0.45, "out": 3.05})
        spec["events"] = [event]
        p, _ = S.load(self.write(spec), self.root)
        shutil.rmtree(self.root / "edit" / "stills", ignore_errors=True)
        warnings = []
        p.measure_events(warnings=warnings)
        return [w for w in warnings if getattr(w, "kind", None) == "outside"]

    def test_a_long_label_stays_inside(self):
        """The ratio-bars column grows with its label up to the safe width, then the label shrinks and wraps."""
        self.assertEqual(self.findings(bars("You", "Managers", "Extraordinary")), [])
        self.assertEqual(self.findings(bars("You", "Managers", "Extraordinarily long")), [])

    def test_late_items_are_measured_when_they_arrive(self):
        spec = self.on("bright", {"in": 0.45, "out": 3.05})
        spec["events"] = [bars("You", "Managers", "Clients", at=(0.2, 0.5, 1.0))]
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual(p._measure_times(p.events[0]), [0.7, 1.0])  # the first two bars' finishes; the still time is the third's


class FaceTolerance(unittest.TestCase):
    """A card resting on the head's edge may round a pixel or two over it: that isn't covering the face."""

    HEAD = [235, 480, 845, 1245]

    def test_rounding_is_not_the_face(self):
        self.assertFalse(SF.overlaps([129, 365, 951, 481], self.HEAD, SF.INSIDE_TOL))  # 1 px over, as measured
        self.assertTrue(SF.overlaps([129, 365, 951, 481], self.HEAD))  # strict still sees it, for placement

    def test_real_overlap_is_the_face(self):
        self.assertTrue(SF.overlaps([129, 365, 951, 520], self.HEAD, SF.INSIDE_TOL))

    def test_boxes_apart_never_overlap(self):
        self.assertFalse(SF.overlaps([0, 0, 100, 100], [200, 200, 300, 300]))
        self.assertFalse(SF.overlaps([0, 0, 100, 100], [100, 0, 200, 100]))


class CaptionsAndHead(Fixture):
    """`_caption_moves` on measured boxes written by hand: no render needed."""

    def project(self, text_box, head=True, content=None):
        spec = self.on("bright", {"in": 0.45, "out": 3.05})
        spec["events"] = [{"type": "StageDrawer", "start": 0, "duration": 2.4,
                           "props": {"card": {"kicker": "OLD", "title": "Plan"}, "dropAt": 1.0, "shutAt": 1.6}}]
        if head:
            spec["sources"]["bright"]["head"] = [38, 63, 70, 100]  # 108x192 take: the head is y 590-1065 in the output
        p, _ = S.load(self.write(spec), self.root)
        entry = {"t": 0.9, "event": 0, "type": "StageDrawer", "text": text_box, **({"content": content} if content else {})}
        (self.root / "edit" / "overlay_boxes.json").write_text(json.dumps({p._box_key(p.events[0]): entry}))
        return p

    def test_placement_never_goes_below_the_head(self):
        """However big the card and wherever the head, a placed card ends above the head or isn't placed."""
        import random
        rng = random.Random(7)
        for _ in range(500):
            top = rng.uniform(150, 1300)
            head = [rng.uniform(150, 450), top, rng.uniform(630, 930), top + rng.uniform(250, 700)]
            y0 = rng.uniform(0, 1700)
            content = [rng.uniform(0, 500), y0, rng.uniform(580, 1080), y0 + rng.uniform(40, 900)]
            frame, s = SF.Project._place(content, head, [rng.uniform(28, 90)])
            if frame is None:
                continue
            bottom = frame["y"] + frame["scale"] * content[3]  # Overlay.tsx: origin at the top, then translate
            self.assertLessEqual(bottom, head[1] + SF.INSIDE_TOL, (content, head, frame))  # rounding of scale and translate

    def test_only_band_crosses_the_eyes(self):
        """A band that clears the graphic but crosses the head is taken, with a warning that is no strict error."""
        p = self.project([255, 1250, 358, 1480])  # below it ends past 1536; above it starts at 1010, inside the head
        avoid, warns = p._caption_moves()
        self.assertEqual(avoid, [[0.0, 2.4, 1010]])
        (w,) = warns
        self.assertEqual(w.kind, "caption_head")
        self.assertIn("head (590–1065 px)", w)
        errors, warnings = S.strict_split(warns)
        self.assertEqual((errors, warnings), ([], [w]))

    def test_no_band_clears_the_graphic(self):
        """Neither band fits the page: the strict finding stays."""
        p = self.project([255, 300, 358, 1500], head=False)
        avoid, warns = p._caption_moves()
        (w,) = warns
        self.assertEqual((avoid, w.kind), ([], "captions_on_text"))

    def test_band_that_clears_both_is_used(self):
        p = self.project([255, 1100, 358, 1250])  # below it: 1310-1490, clear of the head
        avoid, warns = p._caption_moves()
        self.assertEqual((avoid, warns), ([[0.0, 2.4, 1310]], []))

    def test_without_a_head_the_old_rule_holds(self):
        p = self.project([255, 1250, 358, 1480], head=False)
        avoid, warns = p._caption_moves()
        self.assertEqual([w.kind for w in warns] or avoid[0][2], 1010)  # above it, nothing to clear


# four tone bursts: A 0.5-1.0, B 1.1-1.6 (0.10 s after A), C 2.0-2.5 (0.40 s after B), D 3.0-3.5
GAPS = [("A", 0.5, 1.0), ("B", 1.1, 1.6), ("C", 2.0, 2.5), ("D", 3.0, 3.5)]


class Gaps(Fixture):
    """A 4 s take of four tone bursts (GAPS) beside the usual synthetic project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_take(cls.root / "gaps.mov", GAPS, d=4.0)
        (cls.root / "edit" / "transcripts" / "gaps.json").write_text(json.dumps(
            {"words": [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in GAPS]}))


class Air(Gaps):
    def air(self, *segs, strict=True):
        spec = self.on("gaps", *segs)
        spec["sources"]["gaps"] = {"file": "gaps.mov", "face": [54, 96]}
        return self.check(spec, strict=strict)

    def test_next_word_a_tenth_away(self):
        res = self.air({"in": 0.3, "out": 1.05}, {"in": 2.9, "out": 3.6})  # keeps A, not B: 0.10 s of silence after A
        (err,) = [e for e in res["errors"] if getattr(e, "kind", None) == "no_air"]
        self.assertIn("segments[0].out", err)
        self.assertRegex(err, r"has 0\.(09|10) s of silence after")  # the envelope, not the transcript, sets the gap
        self.assertRegex(err, r"the next sound starts at 1\.(08|09|10)")

    def test_a_real_pause(self):
        res = self.air({"in": 1.9, "out": 2.6}, {"in": 2.9, "out": 3.6})  # C: 0.40 s before and 0.50 s after
        self.assertEqual([e for e in res["errors"] + res["warnings"] if getattr(e, "kind", None) == "no_air"], [])

    def test_last_out_point_is_the_tails_business(self):
        res = self.air({"in": 2.9, "out": 3.55}, strict=True)
        self.assertEqual([e for e in res["errors"] + res["warnings"] if getattr(e, "kind", None) == "no_air"], [])

    def test_a_warning_outside_strict(self):
        res = self.air({"in": 0.3, "out": 1.05}, {"in": 2.9, "out": 3.6}, strict=False)
        self.assertEqual(res["errors"], [])
        self.assertTrue(any(getattr(w, "kind", None) == "no_air" for w in res["warnings"]))


class Tail(Gaps):
    """The last clip holds its picture for END_TAIL s; its audio stops before the next word's onset."""

    def probe(self, path, *args):
        out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        return float(re.search(r"max_volume: (-?[\d.]+|-inf) dB", out).group(1).replace("-inf", "-999"))

    def duration(self, path):
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                    capture_output=True, text=True).stdout)

    def test_last_word_runs_into_the_next(self):
        spec = self.on("gaps", {"in": 0.3, "out": 1.05})  # keeps A (ends 1.0); B starts 0.10 s later at 1.1
        spec["sources"]["gaps"] = {"file": "gaps.mov", "face": [54, 96]}
        p, rep = S.load(self.write(spec), self.root)
        seg = p.segments[-1]
        self.assertAlmostEqual(seg.freeze_after, SF.END_TAIL)
        self.assertLess(seg.t_out, 1.1)  # the cut ends before the next word's onset
        (clip,) = p.extract(preview=True)
        self.assertAlmostEqual(self.duration(clip), round((seg.t_out - seg.t_in) * 30) / 30 + SF.END_TAIL, delta=0.04)
        self.assertAlmostEqual(rep["duration"], p.offsets()[-1], places=2)
        # B would sound at 0.8 s into the clip: nothing from there to the end
        self.assertLess(self.probe(clip, "-ss", f"{1.1 - seg.t_in - 0.02:.2f}"), -60)

    def test_a_word_whose_onset_only_plays_has_no_caption(self):
        """An out-point a few hundredths into the next word (no pause to cut in) plays its onset, not the word."""
        spec = self.on("gaps", {"in": 0.3, "out": 1.05})
        spec["sources"]["gaps"] = {"file": "gaps.mov", "face": [54, 96]}
        p, _ = S.load(self.write(spec), self.root)
        p.segments[-1].t_out = 1.18  # 0.08 s into B
        self.assertEqual([w["text"] for w in p.output_words()], ["A"])
        p.segments[-1].t_out = 1.4  # most of B
        self.assertEqual([w["text"] for w in p.output_words()], ["A", "B"])

    def test_a_longer_hold_is_kept(self):
        spec = self.on("gaps", {"in": 2.9, "out": 3.6, "freeze_after": 0.8})
        spec["sources"]["gaps"] = {"file": "gaps.mov", "face": [54, 96]}
        p, _ = S.load(self.write(spec), self.root)
        self.assertEqual(p.segments[-1].freeze_after, 0.8)

    def test_fade_stays_in_silence(self):
        spec = self.on("gaps", {"in": 0.3, "out": 1.05})
        spec["sources"]["gaps"] = {"file": "gaps.mov", "face": [54, 96]}
        p, _ = S.load(self.write(spec), self.root)
        f = p.end_fade(p.segments[-1])
        self.assertTrue(0.03 <= f <= SF.END_FADE, f)


if __name__ == "__main__":
    unittest.main()
