"""The never-list (short_spec.NEVER_LIST): every item has a check that strict mode makes an error, and a fixture
under tools/tests/fixtures/never/ that reproduces it on the synthetic project of test_short_spec.

    uv run python -m unittest tools.tests.test_never_list

A fixture is a spec fragment: {"item", "kind", "stage": "check" | "stills", "take", "segments", "events"?,
"captions"?, "head"?, "also"?, "note"}; `also` lists further kinds the same fixture must trigger. `check` fixtures
go through `check --strict`; `stills` fixtures through the legibility probe (Remotion), then strict mode.
"""

import json
import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))

import short_spec as S  # noqa: E402
from test_short_spec import Fixture  # noqa: E402

NEVER = TOOLS / "tests" / "fixtures" / "never"
MOTION = TOOLS / "motion"
REMOTION = shutil.which("npx") is not None and (MOTION / "node_modules" / "remotion").is_dir()


def fixtures() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(NEVER.glob("*.json"))}


class Coverage(unittest.TestCase):
    def test_every_item_has_its_check_and_fixture(self):
        fx = fixtures()
        for n, what, kinds in S.NEVER_LIST:
            self.assertTrue(kinds and set(kinds) <= S.STRICT_KINDS, (n, what))
            mine = [f for f in fx.values() if f["item"] == n]
            self.assertTrue(mine, f"never-list item {n} ({what}) has no fixture in {NEVER}")
            self.assertTrue(all(f["kind"] in kinds for f in mine), (n, [f["kind"] for f in mine]))
        self.assertEqual(sorted({f["item"] for f in fx.values()}), [n for n, _, _ in S.NEVER_LIST])

    def test_list_names_ten(self):
        self.assertEqual([n for n, _, _ in S.NEVER_LIST], list(range(1, 11)))
        self.assertEqual(len(S.never_list()), 10)


class Reproduced(Fixture):
    """Each fixture triggers its own check, as an error in strict mode."""

    def spec(self, f: dict) -> dict:
        spec = self.on(f["take"], *({k: v for k, v in s.items() if k != "take"} for s in f["segments"]))
        if "head" in f:
            spec["sources"][f["take"]]["head"] = f["head"]
        if "events" in f:
            spec["events"] = f["events"]
        if "captions" in f:
            spec["captions"] = f["captions"]
        return spec

    def strict_errors(self, f: dict) -> list[str]:
        if f["stage"] == "check":
            return S.check(self.write(self.spec(f)), self.root, strict=True)["errors"]
        p, _ = S.load(self.write(self.spec(f)), self.root)  # stills fixtures may use `frame`: probe them as local
        warnings = []
        p.measure_events(warnings=warnings)
        return S.strict_split(warnings + p.caption_warnings())[0]

    def test_check_fixtures(self):
        for name, f in fixtures().items():
            if f["stage"] != "check":
                continue
            with self.subTest(name):
                errors = self.strict_errors(f)
                self.assertTrue(any(getattr(e, "kind", None) == f["kind"] for e in errors), (f["kind"], errors))

    @unittest.skipUnless(REMOTION, "needs tools/motion deps")
    def test_stills_fixtures(self):
        for name, f in fixtures().items():
            if f["stage"] != "stills":
                continue
            with self.subTest(name):
                shutil.rmtree(self.root / "edit" / "stills", ignore_errors=True)
                (self.root / "edit" / "overlay_boxes.json").unlink(missing_ok=True)
                errors = self.strict_errors(f)
                kinds = {getattr(e, "kind", None) for e in errors}
                for kind in [f["kind"], *f.get("also", [])]:
                    self.assertIn(kind, kinds, errors)


if __name__ == "__main__":
    unittest.main()
