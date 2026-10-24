"""Paid-call foundation: duration fitting, estimates, budget and key refusal. No network.

    uv run python -m unittest discover -s tools/tests
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gen"))

import fal  # noqa: E402

ANY = fal.MODELS["minimax-h3-turbo"]
FIXED = fal.MODELS["kling-2.5-turbo"]


class Fit(unittest.TestCase):
    def test_any_duration_rounds_up_to_centiseconds(self):
        self.assertEqual(ANY.fit(3.27), 3.27)
        self.assertEqual(ANY.fit(3.071), 3.08)
        self.assertEqual(ANY.fit(0.4), ANY.min_dur)

    def test_fixed_list_takes_smallest_cover(self):
        self.assertEqual(FIXED.fit(7.13), 10.0)
        self.assertEqual(FIXED.fit(5.0), 5.0)
        self.assertEqual(FIXED.fit(2.0), 5.0)

    def test_over_max_refused(self):
        with self.assertRaises(ValueError):
            FIXED.fit(10.5)
        with self.assertRaises(ValueError):
            ANY.fit(ANY.max_dur + 1)

    def test_api_duration_types(self):
        self.assertEqual(FIXED.video_args("u", "p", 10.0)["duration"], "10")
        self.assertEqual(ANY.video_args("u", "p", 3.27)["duration"], 3.27)
        self.assertEqual(fal.MODELS["kling-3-pro"].video_args("u", "p", 7.0)["start_image_url"], "u")

    def test_unknown_model_lists_names(self):
        with self.assertRaises(SystemExit) as e:
            fal.model("foo")
        self.assertIn("minimax-h3-turbo", str(e.exception))
        self.assertIn("kling-2.5-turbo", str(e.exception))


def reqs(n, dur, m=ANY):
    return [fal.Request("animate", m, f"s{k}", Path(f"/tmp/s{k}.mp4"), dur) for k in range(n)]


class Estimate(unittest.TestCase):
    def test_four_five_second_clips(self):
        buf = io.StringIO()
        n, usd = fal.plan(reqs(4, 5.0), out=buf)
        self.assertEqual(n, 4)
        self.assertAlmostEqual(usd, 0.30)
        self.assertIn("4 requests", buf.getvalue())
        self.assertIn("$0.30", buf.getvalue())

    def test_images_priced_per_image(self):
        m = fal.MODELS["nano-banana-edit"]
        r = fal.Request("keyframes", m, "s1", Path("/tmp/a.png"), n=2)
        self.assertAlmostEqual(r.usd, 2 * m.usd_per_image)


class Budget(unittest.TestCase):
    def test_over_budget_refused(self):
        # 5 clips x 10 s on a $0.07/s model = $3.50, default budget $2
        with self.assertRaises(SystemExit) as e:
            fal.plan(reqs(5, 10.0, FIXED), out=io.StringIO())
        msg = str(e.exception)
        self.assertIn("$3.50", msg)
        self.assertIn("--budget", msg)

    def test_raised_budget_passes(self):
        self.assertAlmostEqual(fal.plan(reqs(5, 10.0, FIXED), budget=4, out=io.StringIO())[1], 3.5)


class Key(unittest.TestCase):
    def test_missing_key_refused(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=True):
            env = Path(d) / ".env"
            env.write_text("OTHER=1\n")
            with self.assertRaises(SystemExit) as e:
                fal.load_key(env)
            self.assertIn("FAL_API_KEY", str(e.exception))
            self.assertIn(".env", str(e.exception))

    def test_key_from_env_file_never_printed(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=True):
            env = Path(d) / ".env"
            env.write_text('FAL_API_KEY="secret-123"\n')
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                fal.load_key(env)
            self.assertEqual(os.environ["FAL_KEY"], "secret-123")
            self.assertNotIn("secret", out.getvalue())


class SpendLog(unittest.TestCase):
    def test_lines_sum_to_estimate(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / fal.SPEND_LOG
            rs = reqs(3, 4.2)
            _, usd = fal.plan(rs, out=io.StringIO())
            for r in rs:
                fal.log_spend(log, r, 12.0)
            lines = [json.loads(x) for x in log.read_text().splitlines()]
            self.assertEqual(len(lines), 3)
            self.assertAlmostEqual(sum(x["est_usd"] for x in lines), usd, places=3)
            self.assertEqual(fal.total(log)[0], 3)
            self.assertNotIn("key", json.dumps(lines).lower())


if __name__ == "__main__":
    unittest.main()
