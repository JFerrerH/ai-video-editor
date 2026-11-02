"""theme.ts `accentOn`: the brand accent as text reads on its fill (brand-theme "Accent text reads on its fill").
theme.ts is transpiled with tools/motion's TypeScript and run in Node.

    uv run python -m unittest tools.tests.test_accent_on
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

MOTION = Path(__file__).resolve().parent.parent / "motion"
INK = "#16150F"

RUN = """
const ts = require("typescript");
const fs = require("fs");
const src = fs.readFileSync("src/theme.ts", "utf8");
const js = ts.transpileModule(src, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
                                                      jsx: ts.JsxEmit.React}}).outputText;
const m = {exports: {}};
new Function("module", "exports", "require", js)(m, m.exports, (n) => n === "react" ? {createContext: () => null,
                                                                                      useContext: () => null} : require(n));
const T = m.exports;
const cases = JSON.parse(process.argv[1]);
console.log(JSON.stringify(cases.map(([accent, fill, min]) => {
  const c = T.accentOn({accent, ink: "%s"}, fill, min);
  return [c, T.contrast(c, fill)];
})));
"""


@unittest.skipUnless(shutil.which("node") and (MOTION / "node_modules" / "typescript").is_dir(), "needs tools/motion deps")
class AccentOn(unittest.TestCase):
    def run_cases(self, cases):
        r = subprocess.run(["node", "-e", RUN % INK, json.dumps(cases)], cwd=MOTION, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_pale_accent_on_white(self):
        (c, ratio), = self.run_cases([["#E8FD5A", "#FFFFFF", 3]])
        self.assertGreaterEqual(ratio, 3)
        self.assertNotEqual(c.lower(), "#e8fd5a")
        self.assertNotEqual(c, INK)  # a darker colour of the same hue reaches 3:1 before ink is needed

    def test_accent_that_already_reads(self):
        (c, _), = self.run_cases([["#1F4FD8", "#FFFFFF", 3]])
        self.assertEqual(c, "#1F4FD8")

    def test_small_text_asks_more(self):
        (c3, r3), (c45, r45) = self.run_cases([["#D64545", "#F4F4F2", 3], ["#D64545", "#F4F4F2", 4.5]])
        self.assertEqual(c3, "#D64545")  # 4.1:1 reads as large text
        self.assertGreaterEqual(r45, 4.5)

    def test_dark_accent_on_dark_fill(self):
        (c, ratio), = self.run_cases([["#1A1A40", "#16150F", 3]])
        self.assertGreaterEqual(ratio, 3)  # lighter, same hue


if __name__ == "__main__":
    unittest.main()
