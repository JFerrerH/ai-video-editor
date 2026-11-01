"""overlay_schema.py: validator keywords, annotations, pinned cue defaults and schema coverage.

    uv run python -m unittest tools.tests.test_overlay_schema
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import overlay_schema as O  # noqa: E402

MOTION = TOOLS / "motion"


def msgs(type_, props, **kw):
    return {p: m for p, m in O.validate(type_, props, **kw)}


class KeywordTest(unittest.TestCase):
    """Each supported keyword, on a throwaway schema registered for the test."""

    @classmethod
    def setUpClass(cls):
        O.schemas()["_T"] = {"type": "object", "required": ["n"], "properties": {
            "n": {"type": "number", "minimum": 0, "maximum": 10},
            "i": {"type": "integer"},
            "s": {"type": "string", "maxLength": 3},
            "e": {"type": "string", "enum": ["a", "b"]},
            "b": {"type": "boolean"},
            "multi": {"type": ["string", "number"]},
            "list": {"type": "array", "items": {"type": "object", "properties": {"x": {"type": "number"}}}},
            "map": {"type": "object", "additionalProperties": {"type": "number"}},
            "free": {"type": "object", "additionalProperties": True},
            "either": {"oneOf": [{"type": "number"}, {"type": "object", "required": ["k"], "properties": {"k": {"type": "string"}}}]},
            "t": {"type": "number", "x-time": "event"},
        }}

    @classmethod
    def tearDownClass(cls):
        O.schemas().pop("_T")

    def test_valid(self):
        self.assertEqual(O.validate("_T", {"n": 1, "i": 2, "s": "abc", "e": "a", "b": False, "multi": "x", "list": [{"x": 1}],
                                           "map": {"q": 1}, "free": {"anything": [1]}, "either": {"k": "v"}, "t": 0.5}), [])

    def test_type(self):
        self.assertIn("must be a whole number", msgs("_T", {"n": 1, "i": 1.5})["i"])
        self.assertIn("must be true or false, got the number 1", msgs("_T", {"n": 1, "b": 1})["b"])
        self.assertIn("must be a string or a number", msgs("_T", {"n": 1, "multi": []})["multi"])

    def test_required(self):
        self.assertEqual(msgs("_T", {})["n"], "missing required field")

    def test_range_enum_length(self):
        self.assertIn("between 0 and 10, got 11", msgs("_T", {"n": 11})["n"])
        self.assertIn('must be one of "a", "b"', msgs("_T", {"n": 1, "e": "c"})["e"])
        self.assertIn("at most 3 characters", msgs("_T", {"n": 1, "s": "abcd"})["s"])

    def test_items_and_properties(self):
        m = msgs("_T", {"n": 1, "list": [{"x": 1}, {"x": "2"}], "map": {"q": "no"}})
        self.assertIn("must be a number", m["list[1].x"])
        self.assertIn("must be a number", m["map.q"])

    def test_one_of(self):
        self.assertEqual(O.validate("_T", {"n": 1, "either": 3}), [])
        self.assertEqual(msgs("_T", {"n": 1, "either": {}})["either.k"], "missing required field")

    def test_not_finite(self):
        self.assertIn("finite", msgs("_T", {"n": float("nan")})["n"])

    def test_time_field_anchor(self):
        self.assertEqual(O.validate("_T", {"n": 1, "t": {"word": "x"}}, anchors=True), [])
        self.assertIn("must be seconds from the event's start (a number)", msgs("_T", {"n": 1, "t": {"word": "x"}})["t"])


class ComponentTest(unittest.TestCase):
    def test_string_for_number(self):
        self.assertEqual(msgs("StatScene", {"value": "400.000"})["value"], 'must be a number, got the string "400.000"')

    def test_unknown_key(self):
        m = msgs("KineticType", {"lines": [{"text": "Hi"}], "colour": "red"})
        self.assertTrue(m["colour"].startswith("unknown field; KineticType props are:"), m)
        self.assertIn("lines", m["colour"])

    def test_string_in_time_field(self):
        m = msgs("KineticType", {"lines": [{"text": "Hi", "at": "0.5s"}]}, anchors=True)
        self.assertIn("seconds from the event's start, or an anchor", m["lines[0].at"])

    def test_shared_event_props(self):
        for t, props in (("ListScene", {"items": [{"text": "a"}]}), ("HookTitle", {"lines": [{"text": "a"}]})):
            self.assertEqual(O.validate(t, {**props, "full": True, "dark": True, "frame": {"scale": 0.6, "y": -200}}), [], t)

    def test_marked_time_fields(self):
        def tf(t, props):
            return {p for p, *_ in O.time_fields(t, props)}
        self.assertEqual(tf("KineticType", {"lines": [{"text": "a", "at": 1}]}), {"lines[0].at"})
        self.assertEqual(tf("ListScene", {"items": [{"text": "a", "at": 1}]}), {"items[0].at"})
        self.assertEqual(tf("StatScene", {"value": 1, "countStart": 0, "countEnd": 1}), {"countStart", "countEnd"})
        props = O.schema("KineticType")["properties"]
        self.assertEqual(props["lines"]["items"]["properties"]["at"]["x-time"], "event")
        self.assertEqual(props["stagger"]["x-time"], "frames")  # the unit is stated: frames, not seconds
        for k in ("countStart", "countEnd"):
            self.assertEqual(O.schema("StatScene")["properties"][k]["x-time"], "event")

    def test_text_and_layout(self):
        self.assertEqual({p for p, *_ in O.text_fields("StatScene", {"value": 1, "kicker": "K", "label": "L"})}, {"kicker", "label"})
        self.assertEqual(O.layout("StatScene"), "full")
        self.assertEqual(O.layout("HookTitle"), "float")

    # pinned against the components' own defaults (ListScene.tsx, KineticType.tsx, StatScene.tsx)
    def test_list_scene_default_cues(self):
        cues = O.cue_finish("ListScene", {"items": [{"text": t} for t in "abcd"]}, 30, 4.0)
        self.assertEqual([c[1] for c in cues], [0.5, 1.1, 1.7, 2.3])
        self.assertEqual(cues[-1], ("items[3]", 2.3, round(2.3 + 14 / 30, 3)))

    def test_kinetic_type_rise_defaults(self):
        cues = O.cue_finish("KineticType", {"lines": [{"text": "one two three"}, {"text": "four"}]}, 30, 3.0)
        self.assertEqual([c[1] for c in cues], [0.1, 0.45])
        self.assertEqual(cues[0][2], round(0.1 + (14 + 2 * 2) / 30, 3))  # 3 words, stagger 2 frames
        pop = O.cue_finish("KineticType", {"style": "pop", "lines": [{"text": "a b"}]}, 30, 3.0)
        self.assertEqual(pop[0][2], round(0.1 + (14 + 3) / 30, 3))

    def test_stat_scene_count_end(self):
        self.assertEqual(O.cue_finish("StatScene", {"value": 1}, 30, 3.0), [("countEnd", 1.3, round(1.3 + 10 / 30, 3))])


def flat_keys(s: dict, prefix: str = "") -> list[str]:
    out = []
    for k, v in s.get("properties", {}).items():
        out.append(prefix + k)
        sub, sep = (v["items"], "[].") if isinstance(v.get("items"), dict) else (v, ".")
        if sub.get("properties"):
            out += flat_keys(sub, prefix + k + sep)
    return out


@unittest.skipUnless(shutil.which("node") and (MOTION / "node_modules" / "typescript").is_dir(), "needs node + tools/motion deps")
class CoverageTest(unittest.TestCase):
    """Every registry and scene component has a schema whose keys match its TypeScript props."""

    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "scripts/prop_keys.mjs"], cwd=MOTION, capture_output=True, text=True, check=True)
        cls.declared = json.loads(r.stdout)

    def test_every_component_has_a_schema(self):
        self.assertEqual(set(self.declared), O.COMPONENTS)
        missing = sorted(n for n in self.declared if n not in O.schemas())
        self.assertEqual(missing, [], f"no <Name>.schema.json for: {missing}")

    def test_keys_match(self):
        problems = []
        for name, d in sorted(self.declared.items()):
            if name not in O.schemas():
                continue
            ts, js = set(d["keys"]), set(flat_keys(O.schemas()[name]))
            problems += [f"{name}: prop {k!r} is declared in {d['file']} but not in its schema" for k in sorted(ts - js)]
            problems += [f"{name}: schema has {k!r}, which {d['file']} does not declare" for k in sorted(js - ts)]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
