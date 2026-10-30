"""site_capture.capture_facts and the `site` job op, on the fixture pages in fixtures/site/.

    uv run python -m unittest tools.tests.test_site_capture      (or: uv run --with pytest pytest tools/tests/test_site_capture.py)

The pages are served by a local listener under public-looking names (resolver stub + `Guard.dial`),
so the browser, the guard and the measurements run for real with no outside network. A second
listener stands in for a private host and must never be hit.
"""

import functools
import io
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))

import brand_files as BF  # noqa: E402
import run_job as R  # noqa: E402
import site_capture as SC  # noqa: E402
import site_guard as G  # noqa: E402
from test_brand_files import make_font, png_bytes  # noqa: E402
from test_site_guard import PRIVATE, PUBLIC, PUBLIC2, Listener, stub  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "site"
HOSTS = {"fixture.example": [PUBLIC], "intranet.example": [PRIVATE],
         "fonts.googleapis.com": [PUBLIC2], "fonts.gstatic.com": [PUBLIC2]}
HTML = {"Content-Type": "text/html; charset=utf-8"}


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        routes = {f"/{p.name}": (200, {"Content-Type": "text/css" if p.suffix == ".css" else HTML["Content-Type"]},
                                 p.read_bytes()) for p in FIXTURE.iterdir()}
        routes["/"] = routes["/index.html"]
        routes["/fonts/display.ttf"] = (200, {"Content-Type": "font/ttf"}, make_font(family="Fixture Display"))
        routes["/favicon.png"] = (200, {"Content-Type": "image/png"}, png_bytes(size=(64, 64), color=(224, 58, 62, 255)))
        routes["/og.png"] = (200, {"Content-Type": "image/png"}, png_bytes(size=(1200, 630), color=(16, 24, 32, 255)))
        routes["/css2?family=Fixture+Grotesk"] = (200, {"Content-Type": "text/css"}, b"""
@font-face { font-family: 'Fixture Grotesk'; font-style: normal; font-weight: 400;
  src: url(https://fonts.gstatic.com/s/fixturegrotesk/v1/latin.woff2) format('woff2'); }""")
        routes["/s/fixturegrotesk/v1/latin.woff2"] = (200, {"Content-Type": "font/woff2"},
                                                      make_font(family="Fixture Grotesk", flavor="woff2"))
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (4 * 1024 * 1024)
        for i in range(10):
            routes[f"/big/{i}.png"] = (200, {"Content-Type": "image/png"}, big)
        routes["/moved"] = (302, {"Location": "http://10.0.0.5/"}, b"")
        cls.site = Listener(routes)
        cls.private = Listener({"/logo.png": (200, {}, png_bytes()), "/": (200, HTML, b"<p>inside</p>")})
        cls.patch = mock.patch.object(G, "Guard", functools.partial(
            G.Guard, resolver=stub(HOSTS), dial={PUBLIC: ("127.0.0.1", cls.site.port),
                                                 PUBLIC2: ("127.0.0.1", cls.site.port),
                                                 PRIVATE: ("127.0.0.1", cls.private.port)}))
        cls.patch.start()
        cls.tmp = Path(tempfile.mkdtemp())
        t0 = time.time()
        cls.cap = SC.capture_facts("http://fixture.example/", cls.tmp / "site")
        cls.seconds = time.time() - t0

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.site.close()
        cls.private.close()
        shutil.rmtree(cls.tmp)

    def test_files_and_network(self):
        shot = Image.open(self.tmp / "site" / "viewport.png")
        self.assertGreaterEqual(shot.width, 1075)
        self.assertGreaterEqual(self.cap["blocked"], 1)
        self.assertEqual(self.private.hits, [])
        self.assertEqual(self.cap["final_url"], "http://fixture.example/")
        self.assertFalse(self.cap["truncated"])
        self.assertLess(self.seconds, 30)

    def test_colors(self):
        cols = {c["hex"]: c for c in self.cap["colors"]}
        order = [c["hex"] for c in self.cap["colors"]]
        self.assertEqual(order[:2], ["#FFFFFF", "#101820"])
        self.assertIn("background", cols["#FFFFFF"]["roles"])
        self.assertIn("background", cols["#101820"]["roles"])
        self.assertTrue({"background", "interactive"} <= set(cols["#E03A3E"]["roles"]))
        self.assertIn("text", cols["#333333"]["roles"])
        self.assertLessEqual(sum(c["share"] for c in self.cap["colors"]), 1.0 + 1e-6)
        self.assertLessEqual(len(order), 16)

    def test_fonts(self):
        f = {x["family"]: x for x in self.cap["fonts"]}
        self.assertEqual(f["Fixture Display"]["source"], "font-face")
        self.assertEqual(f["Fixture Display"]["url"], "http://fixture.example/fonts/display.ttf")
        self.assertIn("headings", f["Fixture Display"]["use"])
        self.assertEqual(f["Arial"]["source"], "system")
        self.assertFalse((self.tmp / "site" / "fonts").exists())

    def test_images(self):
        imgs = self.cap["images"]
        kinds = [i["kind"] for i in imgs]
        self.assertEqual(kinds[:2], ["icon", "og:image"])
        icon, og = imgs[0], imgs[1]
        self.assertEqual((icon["status"], icon["source"]), ("valid", "http://fixture.example/favicon.png"))
        self.assertEqual((og["status"], og["width"], og["height"]), ("valid", 1200, 630))
        svg = next(i for i in imgs if i["kind"] == "header-svg")
        self.assertEqual((svg["status"], svg["source"]), ("invalid", "inline"))
        self.assertIn("script", svg["reason"])
        self.assertNotIn("file", svg)
        private = next(i for i in imgs if i["source"] == "http://intranet.example/logo.png")
        self.assertEqual(private["status"], "invalid")
        files = sorted(p.name for p in (self.tmp / "site" / "images").iterdir())
        self.assertEqual(files, ["01.orig.png", "01.png", "02.orig.png", "02.png"])
        for p in (self.tmp / "site" / "images").iterdir():  # 3.5: everything kept decodes as PNG
            im = Image.open(p)
            im.load()
            self.assertEqual(im.format, "PNG")
        self.assertEqual(Image.open(self.tmp / "site" / "images" / "02.png").size, (1024, 538))

    def test_text(self):
        self.assertEqual(self.cap["title"], "Sample Bakery")
        self.assertEqual(len(self.cap["description"]), 300)
        self.assertEqual(len(self.cap["headings"]), 30)
        self.assertEqual(self.cap["headings"][0], "Fresh bread every morning")
        self.assertEqual(self.cap["social"], ["https://www.instagram.com/samplebakery"])
        size = (self.tmp / "site" / "capture.json").stat().st_size
        self.assertLess(size, 64 * 1024)
        self.assertEqual(json.loads((self.tmp / "site" / "capture.json").read_text())["title"], "Sample Bakery")

    def test_google_font_saved(self):
        out = self.tmp / "g" / "site"
        cap = SC.capture_facts("http://fixture.example/google.html", out)
        f = {x["family"]: x for x in cap["fonts"]}["Fixture Grotesk"]
        self.assertEqual(f["source"], "google")
        self.assertEqual(f["files"], ["site/fonts/Fixture_Grotesk-400.ttf"])
        data = (out / "fonts" / "Fixture_Grotesk-400.ttf").read_bytes()
        self.assertEqual(BF.validate_font(data)[2]["family"], "Fixture Grotesk")
        self.assertEqual(cap["colors"][0]["hex"], "#F4F1EA")

    def test_heavy_page_truncated(self):
        t0 = time.time()
        g = G.Guard()
        with mock.patch.object(G, "Guard", lambda: g):
            cap = SC.capture_facts("http://fixture.example/heavy.html", self.tmp / "h" / "site")
        self.assertLess(time.time() - t0, 40)
        self.assertTrue(cap["truncated"])
        self.assertLessEqual(g.fetched, 20 * 1024 * 1024)
        self.assertTrue((self.tmp / "h" / "site" / "viewport.png").exists())

    def test_redirect_to_private_refused(self):
        with self.assertRaisesRegex(G.GuardError, "redirect to http://10.0.0.5/ refused"):
            SC.capture_facts("http://fixture.example/moved", self.tmp / "r" / "site")
        self.assertFalse((self.tmp / "r").exists())
        self.assertNotIn("/", self.private.hits)


class SiteOp(unittest.TestCase):
    """The op through run_job: refusals exit 2 with nothing written; a capture reports its files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage" / "demo").mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.tmp)
        for k in ("FOOTAGE", "EXPORTS"):
            p = mock.patch.object(R, k, self.tmp / k.lower())
            p.start()
            self.addCleanup(p.stop)
        self.listener = Listener({"/": (200, HTML, (FIXTURE / "google.html").read_bytes().replace(
            b"https://fonts.googleapis.com/css2?family=Fixture+Grotesk", b"/none.css"))})
        self.addCleanup(self.listener.close)
        p = mock.patch.object(G, "Guard", functools.partial(
            G.Guard, resolver=stub(HOSTS), dial={PUBLIC: ("127.0.0.1", self.listener.port)}))
        p.start()
        self.addCleanup(p.stop)

    def tree(self):
        return sorted(str(p.relative_to(self.tmp)) for p in self.tmp.rglob("*"))

    def test_refused_urls_exit_2(self):
        before = self.tree()
        for url in ("file:///etc/passwd", "http://169.254.169.254/latest/meta-data/", "http://fixture.example:8080/"):
            with self.subTest(url=url):
                res, code = R.run({"op": "site", "project": "demo", "args": {"url": url}})
                self.assertEqual(code, 2, res)
                self.assertFalse(res["ok"])
                self.assertEqual(self.tree(), before)
        res, _ = R.run({"op": "site", "project": "demo", "args": {"url": "file:///etc/passwd"}})
        self.assertIn("scheme", res["error"])
        res, _ = R.run({"op": "site", "project": "demo", "args": {"url": "http://169.254.169.254/"}})
        self.assertIn("link-local", res["error"])

    def test_capture_result(self):
        res, code = R.run({"op": "site", "project": "demo", "args": {"url": "http://fixture.example/"}})
        self.assertEqual(code, 0, res)
        for k in ("final_url", "title", "colors", "fonts", "images", "blocked"):
            self.assertIn(k, res)
        self.assertEqual(res["title"], "Sample Studio")
        self.assertTrue({"site/viewport.png", "site/capture.json"} <= set(res["outputs"]))

    def test_unreachable_is_an_op_failure(self):
        res, code = R.run({"op": "site", "project": "demo", "args": {"url": "http://nowhere.example/"}})
        self.assertEqual(code, 1, res)
        self.assertIn("can't capture", res["error"])


if __name__ == "__main__":
    unittest.main()
