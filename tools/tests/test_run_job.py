"""run_job.py: job validation, path confinement and the JSON result contract.

    uv run python -m unittest tools.tests.test_run_job      (or: uv run --with pytest pytest tools/tests/test_run_job.py)
"""

import contextlib
import io
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
sys.path.insert(0, str(TOOLS / "tests"))

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

    def test_footage_ops(self):
        (self.root / "clip.mov").write_text("")
        (self.root / "edit").mkdir()
        (self.root / "edit" / "short.json").write_text("{}")
        (self.root / "edit" / "edl.json").write_text("{}")
        for op, args, msg in (
                ("conform", {"sources": ["clip.mov"], "crop": True}, "crop"),
                ("conform", {"sources": ["../../x.mov"]}, "outside the project"),
                ("conform", {"sources": "clip.mov"}, "must be strs"),
                ("conform", {"frame": "4:3"}, "must be one of"),
                ("pack", {"edit_dir": "/"}, "edit_dir"),
                ("pack", {}, "no edit/transcripts"),
                ("frames", {"source": "clip.mov", "at": [1], "vf": "x"}, "vf"),
                ("frames", {"source": "/etc/passwd", "at": [1]}, "outside the project"),
                ("frames", {"source": "clip.mov", "at": list(range(25))}, "1–24 times"),
                ("face", {"sources": ["clip.mov"], "backend": "x"}, "backend"),
                ("face", {"sources": [str(self.tmp)]}, "outside the project"),
                ("shortform", {"cmd": "build"}, "must be one of"),
                ("shortform", {"cmd": "check", "spec": "../../short.json"}, "outside the project"),
                ("shortform", {"cmd": "check", "spec": "edit"}, "must be a .json file"),
                ("shortform", {"cmd": "render", "build": "edit/build.py"}, "build"),
                ("cut", {"cmd": "render", "filter": "x"}, "filter"),
                ("cut", {"cmd": "check", "edl": "/etc/passwd"}, "outside the project"),
                ("cut", {"cmd": "render", "subtitles": "../x.srt"}, "must be one of")):
            with self.subTest(op=op, args=args):
                self.rejected(op, args, msg)


class Cut(Base):
    """`cut` validates the EDL before render.py (or any ffmpeg) can start."""

    def setUp(self):
        super().setUp()
        (self.root / "edit").mkdir()
        (self.root / "take.mov").write_text("")
        self.edl = {"version": 1, "sources": {"take": "take.mov"}, "ranges": [{"source": "take", "start": 0, "end": 1}]}

    def run_cut(self, edl, cmd="render"):
        (self.root / "edit" / "edl.json").write_text(json.dumps(edl))
        with mock.patch("cut_edl._duration", return_value=10.0), \
                mock.patch.object(R.subprocess, "run", side_effect=AssertionError("subprocess started")) as run:
            res, code = R.run({"op": "cut", "project": "demo", "args": {"cmd": cmd}})
        run.assert_not_called()
        return res, code

    def test_raw_filter_grade(self):
        res, code = self.run_cut({**self.edl, "grade": "eq=contrast=1.1,movie=/etc/passwd"})
        self.assertNotEqual(code, 0)
        self.assertIn("grade", res["error"])
        self.assertIn("auto", res["error"])

    def test_absolute_source(self):
        res, _ = self.run_cut({**self.edl, "sources": {"take": "/Users/someone/private.mov"}})
        self.assertIn("outside the project", res["error"])

    def test_unknown_field(self):
        res, _ = self.run_cut({**self.edl, "ranges": [{"source": "take", "start": 0, "end": 1, "vf": "x"}]})
        self.assertIn("'vf'", res["error"])

    def test_range_past_the_end(self):
        res, _ = self.run_cut({**self.edl, "ranges": [{"source": "take", "start": 5, "end": 12}]})
        self.assertIn("after the end of take", res["error"])

    def test_check_ok(self):
        res, code = self.run_cut({**self.edl, "grade": "auto"}, cmd="check")
        self.assertEqual(code, 0, res)
        self.assertEqual(res["duration"], 1.0)


class DataOnly(Base):
    """A hosted `shortform` job renders from short.json and never runs the project's build.py."""

    def test_build_py_never_runs(self):
        edit = self.root / "edit"
        edit.mkdir()
        marker = self.tmp / "marker"
        (edit / "build.py").write_text(f"open({str(marker)!r}, 'w').write('ran')\n")
        (edit / "short.json").write_text("{}")
        project = mock.Mock()
        project.build.side_effect = lambda preview: (edit / "preview.mp4").write_text("") or edit / "preview.mp4"
        with mock.patch("short_spec.load", return_value=(project, {"duration": 3.0, "edges": []})), \
                mock.patch("shortform.loudness", return_value=(-14.0, -1.5)):
            res, code = R.run({"op": "shortform", "project": "demo", "args": {"cmd": "render", "preview": True}})
        self.assertEqual(code, 0, res)
        project.build.assert_called_once_with(True)
        self.assertEqual(res["video"], "edit/preview.mp4")
        self.assertEqual((res["lufs"], res["true_peak"]), (-14.0, -1.5))
        self.assertFalse(marker.exists())


class ResultFields(Base):
    def test_schema_op(self):
        before = self.tree()
        res, code = R.run({"op": "schema", "args": {}})
        self.assertEqual(code, 0, res)
        self.assertTrue(res["ok"])
        self.assertEqual(res["outputs"], [])
        for k in ("KineticType", "ListScene", "StatScene", "event"):
            self.assertIn(k, res["schema"])
        self.assertEqual(self.tree(), before)
        res, code = R.run({"op": "schema", "project": "demo", "args": {}})
        self.assertEqual(code, 2)

    def test_help_lists_schema(self):
        r = subprocess.run([sys.executable, str(TOOLS / "run_job.py"), "--help"], capture_output=True, text=True)
        self.assertIn("\n  schema ", r.stdout)

    def test_transcribe_fields(self):
        (self.root / "clip.mov").write_text("")

        def fake(video, edit_dir, model, language, track, backend):
            out = edit_dir / "transcripts" / "clip.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"language_code": "es", "language_detected": "es", "words": [],
                                       "untranscribed": [[4.0, 7.0]],
                                       "source": {"patched": [{"from": 0.5, "to": 30.0, "words": 61}]}}))
            return out
        with mock.patch("transcribe_local.transcribe_one", side_effect=fake):
            res, code = R.run({"op": "transcribe", "project": "demo", "args": {"source": "clip.mov"}})
        self.assertEqual(code, 0, res)
        self.assertEqual(res["language_detected"], "es")
        self.assertEqual(res["untranscribed"], [[4.0, 7.0]])
        self.assertEqual(res["patched"], [{"from": 0.5, "to": 30.0, "words": 61}])

    def test_stills_fields(self):
        edit = self.root / "edit"
        edit.mkdir()
        (edit / "short.json").write_text("{}")
        project = mock.Mock()

        def stills(at, preview, warnings):
            warnings.append("events[0] (KineticType) shows almost no text at 1.20 s")
            return [{"path": edit / "stills" / f"short_{t:06.2f}.png", "t": t} for t in (1.0, 3.0)] + \
                [{"path": edit / "stills" / "ev00_KineticType_001.20.png", "t": 1.2, "event": 0, "type": "KineticType"}]
        project.stills.side_effect = stills
        with mock.patch("short_spec.load", return_value=(project, {"duration": 4.0, "edges": [], "warnings": []})):
            res, code = R.run({"op": "shortform", "project": "demo", "args": {"cmd": "stills"}})
        self.assertEqual(code, 0, res)
        self.assertEqual(len(res["stills"]), 3)
        ev = [s for s in res["stills"] if "event" in s]
        self.assertEqual(ev, [{"path": "edit/stills/ev00_KineticType_001.20.png", "t": 1.2, "event": 0, "type": "KineticType"}])
        self.assertEqual(res["warnings"], ["events[0] (KineticType) shows almost no text at 1.20 s"])

    def test_render_failure_names_the_event(self):
        from errors import ToolError

        def op(root, a):
            raise ToolError(["npx", "remotion", "still"], "Error: inputRange must contain only finite numbers",
                            "events[2] (ListScene) failed at 1.55 s: Error: inputRange must contain only finite numbers")
        with mock.patch.dict(R.OPS, {"inventory": R.Op(op, {})}), contextlib.redirect_stderr(io.StringIO()):
            res, code = R.run({"op": "inventory", "project": "demo", "args": {}})
        self.assertEqual(res["error"], "events[2] (ListScene) failed at 1.55 s: Error: inputRange must contain only finite numbers")


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


class BrandOp(Base):
    def setUp(self):
        super().setUp()
        from test_brand_files import make_font, png_bytes

        self.font, self.png = make_font(family="Brand Sans"), png_bytes()
        self.inc = self.root / "brand" / "incoming"
        self.inc.mkdir(parents=True)

    def fill(self):
        (self.inc / "Brand-Regular.ttf").write_bytes(self.font)
        (self.inc / "logo.png").write_bytes(self.png)
        (self.inc / "broken.ttf").write_bytes(self.font[: len(self.font) // 2])
        (self.inc / "notes.txt").write_bytes(b"hello")

    def test_mixed_upload(self):
        self.fill()
        res, code = R.run({"op": "brand", "project": "demo", "args": {"cmd": "check"}})
        self.assertEqual(code, 0, res)
        self.assertTrue(res["ok"])
        self.assertEqual(sorted((f["name"], f["status"]) for f in res["files"]),
                         [("Brand-Regular.ttf", "valid"), ("broken.ttf", "invalid"), ("logo.png", "valid"),
                          ("notes.txt", "invalid")])
        self.assertEqual(res["errors"], [])
        self.assertEqual(sorted(res["outputs"]), ["brand/fonts/Brand-Regular.ttf", "brand/logos/logo.png"])
        self.assertEqual(list(self.inc.iterdir()), [])

    def test_warnings_dont_fail_the_job(self):
        self.fill()
        (self.root / "brand" / "brand.json").write_text(json.dumps(
            {"fontFiles": [{"family": "Brand Sans", "file": "Brand-Regular.ttf", "weight": "100 900"}]}))
        res, code = R.run({"op": "brand", "project": "demo", "args": {"cmd": "check"}})
        self.assertEqual(code, 0, res)
        self.assertTrue(res["ok"])
        self.assertEqual(res["warnings"], ['fontFiles[0].weight: Brand-Regular.ttf provides weight 400, not "100 900"'])

    def test_kit_error_fails_the_job(self):
        (self.root / "brand" / "brand.json").write_text(json.dumps({"colors": {"accent": "red"}}))
        res, code = R.run({"op": "brand", "project": "demo", "args": {"cmd": "check"}})
        self.assertEqual(code, 1)
        self.assertFalse(res["ok"])
        self.assertIn("colors.accent", res["error"])

    def test_dir_confined(self):
        for d in ("../other", "/tmp", "missing"):
            with self.subTest(d=d):
                res, code = R.run({"op": "brand", "project": "demo", "args": {"cmd": "check", "dir": d}})
                self.assertEqual(code, 2, res)
        (self.root / "brand" / "fonts").symlink_to(self.tmp)
        res, code = R.run({"op": "brand", "project": "demo", "args": {"cmd": "check"}})
        self.assertEqual(code, 2)
        self.assertIn("symlink", res["error"])

    def test_cli_matches_op(self):
        self.fill()
        res, _ = R.run({"op": "brand", "project": "demo", "args": {"cmd": "check"}})
        self.fill()
        r = subprocess.run([sys.executable, str(TOOLS / "brand_check.py"), str(self.root / "brand")],
                           capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(TOOLS)})
        self.assertEqual(r.returncode, 0, r.stderr)
        cli = json.loads(r.stdout)
        drop = lambda fs: [{k: v for k, v in f.items() if k != "replaced"} for f in fs]  # noqa: E731
        self.assertEqual(drop(cli["files"]), drop(res["files"]))
        self.assertEqual(cli["errors"], res["errors"])
        self.assertEqual(cli["warnings"], res["warnings"])

    def test_help_lists_brand_and_site(self):
        r = subprocess.run([sys.executable, str(TOOLS / "run_job.py"), "--help"], capture_output=True, text=True)
        for op in ("site ", "brand "):
            self.assertIn(f"\n  {op}", r.stdout)


# Failure text as tools.shortform.run raises it (captured from real runs; `{R}` is the engine root)
REMOTION_FAIL = """FAILED: npx remotion still Overlay {R}/footage/demo/edit/stills/ov_002.00.png --props={R}/footage/demo/edit/overlay_props.json --frame=60 --scale=0.5 --log=error
 TypeError  Cannot read properties of null (reading 'map')"""
FFMPEG_FAIL = """FAILED: ffmpeg -hide_banner -y -i {R}/footage/demo/missing.mov -t 1 {R}/footage/demo/edit/o.mp4
[in#0 @ 0xc08c24000] Error opening input: No such file or directory
Error opening input file {R}/footage/demo/missing.mov.
Error opening input files: No such file or directory"""


class Failures(Base):
    def fail_with(self, msg):
        def op(root, a):
            raise SystemExit(msg)

        err = io.StringIO()
        with mock.patch.dict(R.OPS, {"inventory": R.Op(op, {})}), contextlib.redirect_stderr(err):
            res, code = R.run({"op": "inventory", "project": "demo", "args": {}})
        self.assertEqual(code, 1)
        self.assertFalse(res["ok"])
        return res["error"], err.getvalue()

    def test_remotion_type_error(self):
        msg = REMOTION_FAIL.format(R=R.REPO)
        error, stderr = self.fail_with(msg)
        self.assertEqual(error, "TypeError  Cannot read properties of null (reading 'map')")
        self.assertIn(msg, stderr)

    def test_ffmpeg_failure(self):
        error, _ = self.fail_with(FFMPEG_FAIL.format(R=R.REPO))
        self.assertEqual(error, "Error opening input files: No such file or directory")

    def test_engine_paths_relative(self):
        error, _ = self.fail_with(f"FAILED: npx remotion still …\nError: cannot read {R.REPO}/footage/demo/edit/overlay_props.json")
        self.assertEqual(error, "Error: cannot read footage/demo/edit/overlay_props.json")

    def test_font_did_not_load(self):
        error, _ = self.fail_with('FAILED: npx remotion still …\n Font did not load: normal 400 "Brand Sans" (Brand.ttf)\n    at x (y.js:1)')
        self.assertEqual(error, 'Font did not load: normal 400 "Brand Sans" (Brand.ttf)')

    def test_one_line_unchanged(self):
        error, _ = self.fail_with("no edit/short.json (copy templates/short.json)")
        self.assertEqual(error, "no edit/short.json (copy templates/short.json)")

    def test_no_error_line_keeps_first(self):
        error, _ = self.fail_with("FAILED: auto-editor in.mp4\nsome output\nmore output")
        self.assertEqual(error, "FAILED: auto-editor in.mp4")

    def test_capped(self):
        error, _ = self.fail_with("FAILED: x\nError: " + "y" * 900)
        self.assertEqual(len(error), 500)


if __name__ == "__main__":
    unittest.main()
