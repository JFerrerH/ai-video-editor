"""Shot lists, keyframe/animation prompts and duration planning. No network.

    uv run python -m unittest discover -s tools/tests
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gen"))

import animate  # noqa: E402
import fal  # noqa: E402
import keyframes  # noqa: E402
import shotlist  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "shots.json"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "images").mkdir()
        (self.dir / "keyframes").mkdir()
        for name in ("hero", "guide"):
            (self.dir / "images" / f"{name}.png").write_bytes(b"png")
        self.data = json.loads(TEMPLATE.read_text())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def sl(self) -> shotlist.ShotList:
        (self.dir / "shots.json").write_text(json.dumps(self.data))
        return shotlist.ShotList(self.dir / "shots.json")

    def shot(self, sid):
        return next(s for s in self.data["shots"] if s["id"] == sid)


class Validation(Fixture):
    def test_template_is_valid_once_the_base_exists(self):
        (self.dir / "keyframes" / "s01_hook.png").write_bytes(b"png")
        sl = self.sl()
        for need in ("frame", "motion", "line"):
            self.assertEqual(shotlist.errors(sl, sl.shots, need), [], need)

    def test_unknown_cast_member(self):
        del self.data["cast"]["guide"]
        sl = self.sl()
        errs = shotlist.errors(sl, sl.shots, "frame")
        self.assertTrue(any("s02_meet" in e and "'guide'" in e for e in errs), errs)

    def test_missing_reference_still(self):
        (self.dir / "images" / "hero.png").unlink()
        sl = self.sl()
        errs = shotlist.errors(sl, sl.shots, "frame")
        self.assertTrue(any(str(self.dir / "images" / "hero.png") in e for e in errs), errs)

    def test_empty_camera_refused_by_animate(self):
        self.shot("s01_hook")["camera"] = " "
        sl = self.sl()
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            animate.run(sl, None, self.dir / "keyframes", self.dir / "shots", self.dir / "log", self.dir / "v",
                        dur="5", dry_run=True)
        self.assertIn("s01_hook", str(e.exception))
        self.assertIn("camera", str(e.exception))

    def test_missing_base_keyframe(self):
        sl = self.sl()
        errs = shotlist.errors(sl, sl.shots, "frame")
        self.assertTrue(any("s02_meet" in e and "base" in e for e in errs), errs)

    def test_library_shot_needs_only_a_line(self):
        sl = self.sl()
        lib = [s for s in sl.shots if shotlist.is_library(s)]
        self.assertEqual(shotlist.errors(sl, lib, "motion"), [])
        lib[0]["line"] = ""
        self.assertTrue(shotlist.errors(sl, lib, "line"))

    def test_duplicate_ids(self):
        self.data["shots"].append(dict(self.shot("s01_hook")))
        sl = self.sl()
        self.assertTrue(any("twice" in e for e in shotlist.errors(sl, sl.shots, "line")))


class Prompts(Fixture):
    def test_new_still_carries_world_and_refs_in_order(self):
        self.shot("s01_hook")["cast"] = ["hero", "guide"]
        sl = self.sl()
        s = sl.shots[0]
        p = keyframes.prompt_for(sl, s)
        self.assertIn(sl.world, p)
        self.assertIn("HERO = the hero character, exactly as in its reference still (reference image 1)", p)
        self.assertIn("(reference image 2)", p)
        self.assertIn("do NOT copy the reference backgrounds", p)
        self.assertNotIn("band", p.lower())
        self.assertEqual([x.name for x in keyframes.images_for(sl, s)], ["hero.png", "guide.png"])

    def test_base_edit_sends_base_first(self):
        self.data["shots"][1]["cast"] = ["hero", "guide"]
        sl = self.sl()
        s = sl.shots[1]
        imgs = keyframes.images_for(sl, s)
        self.assertEqual([x.name for x in imgs], ["s01_hook.png", "hero.png", "guide.png"])
        p = keyframes.prompt_for(sl, s)
        self.assertTrue(p.startswith("Edit image 1"))
        self.assertIn("(reference image 2)", p)
        self.assertIn("(reference image 3)", p)
        self.assertNotIn(sl.world, p)  # the base already holds the world

    def test_animation_prompt(self):
        self.data["style"] = "paper cut-out look"
        sl = self.sl()
        s = sl.shots[0]
        p = animate.prompt_for(sl, s)
        self.assertTrue(p.startswith(s["motion"] + " " + s["camera"]))
        self.assertIn("camera never stays still", p)
        self.assertTrue(p.endswith("paper cut-out look."))


class Planning(Fixture):
    def run_animate(self, needs, model="minimax-h3-turbo", **kw):
        for s in ("s01_hook", "s02_meet"):
            (self.dir / "keyframes" / f"{s}.png").write_bytes(b"png")
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.object(fal, "client", side_effect=AssertionError("network")):
            animate.run(self.sl(), None, self.dir / "keyframes", self.dir / "shots", self.dir / "log",
                        self.dir / "v", model, "fit", needs, dry_run=True, **kw)
        return buf.getvalue()

    def test_fit_any_duration_adds_handle(self):
        out = self.run_animate({"s01_hook": 3.07, "s02_meet": 2.0})
        self.assertIn("s01_hook: 3.27s", out)
        self.assertIn("plan: 2 requests", out)
        self.assertNotIn("s03_payoff:", out)  # library shot: nothing generated

    def test_fit_fixed_rounds_up(self):
        out = self.run_animate({"s01_hook": 7.13, "s02_meet": 2.0}, "kling-2.5-turbo")
        self.assertIn("s01_hook: 10s", out)
        self.assertIn("s02_meet: 5s", out)

    def test_over_max_refused_before_send(self):
        with self.assertRaises(SystemExit) as e:
            self.run_animate({"s01_hook": 12.0, "s02_meet": 2.0}, "kling-2.5-turbo")
        self.assertIn("s01_hook", str(e.exception))

    def test_existing_clips_skipped(self):
        (self.dir / "shots").mkdir()
        (self.dir / "shots" / "s01_hook.mp4").write_bytes(b"mp4")
        out = self.run_animate({"s01_hook": 3.0, "s02_meet": 2.0})
        self.assertIn("kept: s01_hook.mp4", out)
        self.assertIn("plan: 1 request ", out)

    def test_keyframes_rerun_keeps_existing(self):
        for s in ("s01_hook", "s02_meet"):
            (self.dir / "keyframes" / f"{s}.png").write_bytes(b"png")
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.object(fal, "client", side_effect=AssertionError("network")):
            keyframes.run(self.sl(), None, self.dir / "keyframes", self.dir / "log", self.dir / "sheet.png")
        self.assertIn("plan: 0 requests", buf.getvalue())

    def test_keyframes_candidates_named(self):
        self.assertEqual([p.name for p in keyframes.outputs(self.dir, "s01", 2)], ["s01_1.png", "s01_2.png"])


if __name__ == "__main__":
    unittest.main()
