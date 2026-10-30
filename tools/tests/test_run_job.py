"""run_job.py: job validation, path confinement and the JSON result contract.

    uv run python -m unittest tools.tests.test_run_job      (or: uv run --with pytest pytest tools/tests/test_run_job.py)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import run_job as R  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.footage, self.assets, self.exports = (self.tmp / d for d in ("footage", "assets", "exports"))
        for d in (self.footage, self.assets, self.exports):
            d.mkdir()
        self.root = self.footage / "demo"
        self.root.mkdir()
        self.patches = [mock.patch.object(R, k, v) for k, v in
                        (("FOOTAGE", self.footage), ("ASSETS", self.assets), ("EXPORTS", self.exports))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def tree(self) -> set[str]:
        return {str(p.relative_to(self.tmp)) for p in self.tmp.rglob("*")}


class Rejections(Base):
    def test_unknown_op(self):
        before = self.tree()
        res, code = R.run({"op": "shell", "project": "demo", "args": {"cmd": "touch x"}})
        self.assertEqual(code, 2)
        self.assertFalse(res["ok"])
        self.assertIn("unknown op", res["error"])
        self.assertEqual(self.tree(), before)

    def test_unknown_argument(self):
        before = self.tree()
        res, code = R.run({"op": "inventory", "project": "demo", "args": {"recursive": True}})
        self.assertEqual(code, 2)
        self.assertIn("recursive", res["error"])
        self.assertEqual(self.tree(), before)

    def test_invalid_project_names(self):
        for name in ("../demo", "Demo", "demo_1", "demo/edit", "", "-demo", "demo-", None, 3):
            res, code = R.run({"op": "inventory", "project": name, "args": {}})
            self.assertEqual(code, 2, name)
            self.assertIn("project", res["error"], name)

    def test_missing_project(self):
        res, code = R.run({"op": "inventory", "project": "nope", "args": {}})
        self.assertEqual(code, 2)
        self.assertIn("not found", res["error"])

    def test_unknown_job_field(self):
        res, code = R.run({"op": "inventory", "project": "demo", "args": {}, "cwd": "/"})
        self.assertEqual(code, 2)
        self.assertIn("cwd", res["error"])


class OpSchemas(Base):
    def rejected(self, op, args, msg):
        before = self.tree()
        res, code = R.run({"op": op, "project": "demo", "args": args})
        self.assertEqual(code, 2, res)
        self.assertFalse(res["ok"])
        self.assertIn(msg, res["error"])
        self.assertEqual(len(res["error"].splitlines()), 1)
        self.assertEqual(self.tree(), before)

    def test_transcribe(self):
        self.rejected("transcribe", {"source": "clip.mov", "translate": True}, "translate")
        self.rejected("transcribe", {"source": "missing.mov"}, "not found: missing.mov")
        (self.root / "clip.mov").write_text("")
        self.rejected("transcribe", {"source": "clip.mov", "model": "../../models/x"}, "invalid value")
        self.rejected("transcribe", {"source": "clip.mov", "backend": "openai"}, "must be one of")

    def test_voice(self):
        self.rejected("voice", {"text": "Hi.", "out": "../../exports/x.wav"}, "outside the project")
        self.rejected("voice", {"text": "Hi.", "out": "edit/x.wav", "lang": "../x"}, "invalid value")
        self.rejected("voice", {"text": "Hi.", "out": "edit/x.mp3"}, ".wav")
        self.rejected("voice", {"text": "Hi.", "out": "edit/x.wav", "lang": "xx"}, "isn't supported")

    def test_matte(self):
        (self.root / "clip.mov").write_text("")
        self.rejected("matte", {"source": "clip.mov", "start": 0, "dur": 1, "out": "/tmp/m.mov"}, "outside the project")
        self.rejected("matte", {"source": "clip.mov", "start": "8", "dur": 1, "out": "m.mov"}, "must be float")

    def test_storyboard(self):
        self.rejected("storyboard", {"cmd": "rm"}, "must be one of")
        self.rejected("storyboard", {"cmd": "check"}, "not found: edit")
        (self.root / "edit").mkdir()
        self.rejected("storyboard", {"cmd": "render", "export": "../../x"}, "invalid value")

    def test_shortform_needs_build_file(self):
        self.rejected("shortform.build", {"preview": True}, "no edit/build.py")


class Confinement(Base):
    def setUp(self):
        super().setUp()
        (self.tmp / "brands" / "x").mkdir(parents=True)
        (self.tmp / "brands" / "x" / "brand.json").write_text("{}")
        (self.root / "clip.mov").write_text("")

    def test_parent_escape(self):
        with self.assertRaisesRegex(R.JobError, "outside the project"):
            R.confine(self.root, "../../brands/x/brand.json", "in")

    def test_absolute_outside(self):
        with self.assertRaisesRegex(R.JobError, "outside the project"):
            R.confine(self.root, str(self.tmp / "brands" / "x" / "brand.json"), "in")
        with self.assertRaisesRegex(R.JobError, "outside the project"):
            R.confine(self.root, "/etc/passwd", "in")

    def test_symlink_out_of_project(self):
        os.symlink(self.tmp / "brands", self.root / "link")
        with self.assertRaisesRegex(R.JobError, "outside the project"):
            R.confine(self.root, "link/x/brand.json", "in")
        with self.assertRaisesRegex(R.JobError, "outside the project"):
            R.confine(self.root, "link/out.wav", "out")

    def test_inside_ok(self):
        self.assertEqual(R.confine(self.root, "clip.mov", "in"), (self.root / "clip.mov").resolve())
        self.assertEqual(R.confine(self.root, str(self.root / "clip.mov"), "in"), (self.root / "clip.mov").resolve())
        self.assertTrue(R.confine(self.root, "edit/new.wav", "out").is_relative_to(self.root.resolve()))

    def test_assets_readable_not_writable(self):
        (self.assets / "music.wav").write_text("")
        self.assertTrue(R.confine(self.root, str(self.assets / "music.wav"), "in").exists())
        with self.assertRaisesRegex(R.JobError, "outside the project"):
            R.confine(self.root, str(self.assets / "x.wav"), "out")

    def test_missing_input(self):
        with self.assertRaisesRegex(R.JobError, "not found"):
            R.confine(self.root, "nope.mov", "in")


class Schema(unittest.TestCase):
    def test_types_and_choices(self):
        schema = {"n": R.Arg("int"), "x": R.Arg("float"), "b": R.Arg("bool", default=False),
                  "c": R.Arg("str", choices=("a", "b")), "r": R.Arg("str", required=True)}
        root = Path(tempfile.gettempdir())
        self.assertEqual(R.check_args(schema, {"r": "y", "x": 2}, root),
                         {"n": None, "x": 2.0, "b": False, "c": None, "r": "y"})
        for bad, msg in (({"r": "y", "n": True}, "'n' must be int"), ({"r": "y", "x": "1"}, "'x' must be float"),
                         ({"r": "y", "c": "z"}, "must be one of"), ({}, "missing argument: r")):
            with self.assertRaisesRegex(R.JobError, msg):
                R.check_args(schema, bad, root)


@unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
class Inventory(Base):
    def test_inventory_and_cli_contract(self):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=1",
                        "-pix_fmt", "yuv420p", str(self.root / "clip.mp4")], check=True)
        res, code = R.run({"op": "inventory", "project": "demo", "args": {}})
        self.assertEqual(code, 0, res)
        self.assertEqual(res["outputs"], ["edit/inventory.json"])
        inv = json.loads((self.root / "edit" / "inventory.json").read_text())
        self.assertEqual(inv["files"][0]["file"], "clip.mp4")
        self.assertAlmostEqual(inv["files"][0]["duration"], 1.0, places=1)

    def test_cli_stdout_is_one_json(self):
        env = {**os.environ, "PYTHONPATH": str(TOOLS)}
        job = json.dumps({"op": "inventory", "project": "missing-project", "args": {}})
        r = subprocess.run([sys.executable, str(TOOLS / "run_job.py"), "-"], input=job,
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        res = json.loads(r.stdout)
        self.assertFalse(res["ok"])
        self.assertNotIn("Traceback", r.stdout)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
