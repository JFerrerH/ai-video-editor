"""brand_files.py: font, raster and SVG validators, the brand.json shape check and check_dir.

    uv run python -m unittest tools.tests.test_brand_files      (or: uv run --with pytest pytest tools/tests/test_brand_files.py)

Fixtures are built here (fontTools FontBuilder, Pillow, hand-written SVG and PNG headers).
"""

import io
import json
import shutil
import struct
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import brand_files as B  # noqa: E402

REPO = TOOLS.parent
FIXTURE_FONTS = TOOLS / "tests" / "fixtures" / "fonts"  # OFL faces, licences next to them
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def make_font(family="Test Sans", weight=400, italic=False, flavor=None, cff=False, wght=None) -> bytes:
    """A minimal font mapping A–Z a–z 0–9; `wght=(min, max)` makes it variable with that weight axis."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    names = [".notdef", "space"] + [f"g{ord(c)}" for c in CHARS]
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({32: "space", **{ord(c): f"g{ord(c)}" for c in CHARS}})

    def box(pen):
        pen.moveTo((50, 0)), pen.lineTo((50, 700)), pen.lineTo((450, 700)), pen.lineTo((450, 0)), pen.closePath()

    if cff:
        cs = {}
        for n in names:
            p = T2CharStringPen(500, None)
            if n != "space":
                box(p)
            cs[n] = p.getCharString()
        fb.setupCFF(family.replace(" ", ""), {"FullName": family}, cs, {})
    else:
        glyphs = {}
        for n in names:
            p = TTGlyphPen(None)
            if n != "space":
                box(p)
            glyphs[n] = p.glyph()
        fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (500, 50) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    style = ("Bold " if weight >= 700 else "") + ("Italic" if italic else "") or "Regular"
    fb.setupNameTable({"familyName": family, "styleName": style.strip()})
    fb.setupOS2(usWeightClass=weight, fsSelection=(1 if italic else 0) | (0 if italic or weight >= 700 else 0x40))
    fb.setupPost()
    if italic:
        fb.font["head"].macStyle |= 2
    if wght:
        fb.setupFvar([("wght", wght[0], min(max(weight, wght[0]), wght[1]), wght[1], "Weight")], [])
        if not cff:
            fb.setupGvar({})
    buf = io.BytesIO()
    fb.font.flavor = flavor
    fb.font.save(buf)
    return buf.getvalue()


def png_bytes(size=(64, 32), color=(255, 0, 0, 255), mode="RGBA", fmt="PNG", exif=None) -> bytes:
    im = Image.new(mode, size, color if mode == "RGBA" else color[:3])
    buf = io.BytesIO()
    im.save(buf, fmt, **({"exif": exif} if exif else {}))
    return buf.getvalue()


def png_header_only(w: int, h: int) -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 1000)) + chunk(b"IEND", b"")


CLEAN_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 50">'
             b'<rect x="10" y="5" width="80" height="40" fill="#101820"/>'
             b'<circle cx="150" cy="25" r="20" fill="#E03A3E"/></svg>')


class Fonts(unittest.TestCase):
    def test_ttf(self):
        out, ext, facts = B.validate_font(make_font())
        self.assertEqual(ext, ".ttf")
        self.assertEqual(facts, {"family": "Test Sans", "weight": 400, "style": "normal"})

    def test_cff_otf(self):
        out, ext, facts = B.validate_font(make_font(cff=True))
        self.assertEqual(ext, ".otf")
        self.assertEqual(out[:4], b"OTTO")

    def test_woff2_bold_italic_unwrapped(self):
        data = make_font(weight=700, italic=True, flavor="woff2")
        self.assertEqual(data[:4], b"wOF2")
        out, ext, facts = B.validate_font(data)
        self.assertEqual((ext, facts["weight"], facts["style"]), (".ttf", 700, "italic"))
        self.assertEqual(out[:4], b"\x00\x01\x00\x00")
        B.validate_font(out)  # the unwrapped file parses on its own

    def test_truncated(self):
        data = make_font()
        with self.assertRaisesRegex(B.Invalid, "doesn't parse|missing table"):
            B.validate_font(data[: len(data) // 2])

    def test_oversized(self):
        data = make_font(cff=True)
        with self.assertRaisesRegex(B.Invalid, "5 MB"):
            B.validate_font(data + b"\x00" * (6 * 1024 * 1024))

    def test_not_a_font(self):
        with self.assertRaisesRegex(B.Invalid, "not a TTF"):
            B.validate_font(png_bytes())

    def test_variable_weight_range(self):
        self.assertEqual(B.validate_font(make_font(wght=(100, 800)))[2]["weight"], "100 800")
        self.assertEqual(B.validate_font(make_font(wght=(1, 1000)))[2]["weight"], "100 900")  # clamped

    def test_fixture_fonts(self):
        got = {p.name: B.validate_font(p.read_bytes())[2] for p in sorted(FIXTURE_FONTS.glob("*/*.ttf"))}
        self.assertEqual(got, {
            "Barlow-Light.ttf": {"family": "Barlow", "weight": 300, "style": "normal"},
            "Outfit-VF.ttf": {"family": "Outfit", "weight": "100 900", "style": "normal"},
            "RedHatMono-VF.ttf": {"family": "Red Hat Mono", "weight": "300 700", "style": "normal"},
        })


class Rasters(unittest.TestCase):
    def test_png_keeps_alpha_drops_metadata(self):
        im = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
        buf = io.BytesIO()
        from PIL import PngImagePlugin
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "secret")
        im.save(buf, "PNG", pnginfo=info)
        out, facts = B.validate_raster(buf.getvalue())
        back = Image.open(io.BytesIO(out))
        self.assertEqual((back.mode, back.size, facts["width"]), ("RGBA", (40, 20), 40))
        self.assertNotIn("Comment", back.info)

    def test_bomb_refused_before_decode(self):
        data = png_header_only(30000, 30000)
        self.assertLess(len(data), 40_000)
        t0 = time.time()
        with self.assertRaisesRegex(B.Invalid, "8000 px"):
            B.validate_raster(data)
        self.assertLess(time.time() - t0, 1)

    def test_jpeg_named_png(self):
        out, facts = B.validate_raster(png_bytes(fmt="JPEG", mode="RGB"))
        self.assertEqual(facts["format"], "jpeg")
        self.assertEqual(out[:8], b"\x89PNG\r\n\x1a\n")

    def test_exif_orientation_applied(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90°
        out, facts = B.validate_raster(png_bytes(size=(60, 20), fmt="JPEG", mode="RGB", exif=exif.tobytes()))
        self.assertEqual((facts["width"], facts["height"]), (20, 60))

    def test_html_named_png(self):
        with self.assertRaisesRegex(B.Invalid, "not a PNG or JPEG"):
            B.validate_raster(b"<!doctype html><html><body>hi</body></html>")

    def test_preview_long_side(self):
        out, facts = B.validate_raster(png_bytes(size=(3000, 1000)), long_side=1024)
        self.assertEqual((facts["width"], facts["height"]), (1024, 341))


class Svgs(unittest.TestCase):
    def reject(self, svg: bytes, reason: str):
        with self.assertRaisesRegex(B.Invalid, reason):
            B.validate_svg(svg)

    def test_rejects(self):
        head = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">'
        cases = {
            "script": (b"<script>alert(1)</script>", "<script>"),
            "onload": (b'<rect width="5" height="5" onload="alert(1)"/>', "event handler"),
            "foreignObject": (b"<foreignObject><div/></foreignObject>", "<foreignobject>"),
            "external image": (b'<image href="https://example.com/x.png" width="5" height="5"/>', "external reference"),
            "xlink": (b'<use xlink:href="other.svg#a"/>', "external reference"),
            "css url": (b'<rect style="fill:url(http://example.com/p.svg)" width="5" height="5"/>', "external CSS url"),
            "import": (b"<style>@import 'http://example.com/a.css';</style>", "@import"),
            "style url": (b"<style>rect{fill:url(https://x.example/a#b)}</style>", "external CSS url"),
            "animate href": (b'<a><set attributeName="href" to="javascript:alert(1)"/></a>', "animates href"),
        }
        for name, (body, reason) in cases.items():
            with self.subTest(name=name):
                self.reject(head + body + b"</svg>", reason)

    def test_billion_laughs_fast(self):
        bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
                + b"".join(f'<!ENTITY lol{i} "{("&lol" + (str(i - 1) if i > 1 else "") + ";") * 10}">'.encode()
                           for i in range(1, 10))
                + b']><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><text>&lol9;</text></svg>')
        t0 = time.time()
        self.reject(bomb, "DTD or entities")
        self.assertLess(time.time() - t0, 2)

    def test_fragment_and_data_uri_ok(self):
        data = png_bytes(size=(4, 4))
        import base64
        svg = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><defs><linearGradient id="g"/></defs>'
               b'<rect fill="url(#g)" width="5" height="5"/>'
               b'<image href="data:image/png;base64,' + base64.b64encode(data) + b'" width="5" height="5"/></svg>')
        self.assertEqual(B.validate_svg(svg), (10.0, 10.0))

    def test_no_size(self):
        self.reject(b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>', "no size")

    def test_not_svg_root(self):
        self.reject(b'<html xmlns="http://www.w3.org/1999/xhtml"/>', "not an SVG")

    def test_clean_logo_rasterized(self):
        size = B.validate_svg(CLEAN_SVG)
        with B.Rasterizer() as r:
            png = r.png(CLEAN_SVG, size)
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        self.assertEqual(im.size, (2048, 512))
        for xy in ((0, 0), (2047, 0), (0, 511), (2047, 511)):
            self.assertEqual(im.getpixel(xy)[3], 0, xy)
        self.assertEqual(im.getpixel((500, 256))[:3], (0x10, 0x18, 0x20))
        r_, g_, b_, a_ = im.getpixel((1536, 256))
        self.assertEqual(((r_, g_, b_), a_), ((0xE0, 0x3A, 0x3E), 255))


class Kit(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d)

    def kit(self, data: dict) -> list[str]:
        (self.d / "brand.json").write_text(json.dumps(data))
        return B.check_kit(self.d)[0]

    def test_template_passes(self):
        shutil.copytree(REPO / "brands" / "_template", self.d, dirs_exist_ok=True)
        self.assertEqual(B.check_kit(self.d), ([], []))

    def test_invalid_colour(self):
        errs = self.kit({"colors": {"accent": "red"}})
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("colors.accent"))

    def test_unknown_keys(self):
        errs = self.kit({"logo": "x.png", "colors": {"brand": "#000000"}, "captions": {"blink": True}})
        self.assertEqual(sorted(e.split(":")[0] for e in errs), ["captions.blink", "colors.brand", "logo"])

    def test_font_file_not_validated(self):
        errs = self.kit({"fontFiles": [{"family": "Brand", "file": "Brand-Bold.ttf"}]})
        self.assertEqual(len(errs), 1)
        self.assertIn("fontFiles[0].file", errs[0])
        self.assertIn("Brand-Bold.ttf", errs[0])
        (self.d / "fonts").mkdir()
        (self.d / "fonts" / "Brand-Bold.ttf").write_bytes(make_font())
        self.assertEqual(B.check_kit(self.d), ([], []))

    def test_caption_ranges_and_weights(self):
        errs = self.kit({"captions": {"top": 5000, "mode": "karaoke", "emphCaps": "yes", "shade": 0.5,
                                      "emphColor": "white"},
                         "fontFiles": [{"family": "X", "file": "../x.ttf", "weight": "100 900"}]})
        self.assertEqual(sorted(e.split(":")[0] for e in errs),
                         ["captions.emphCaps", "captions.mode", "captions.top", "fontFiles[0].file"])


class FontEntries(unittest.TestCase):
    """fontFiles entries compared with their files: warnings only, `errors` stays empty."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d)
        (self.d / "fonts").mkdir()

    def check(self, *entries: tuple[str, bytes, dict]) -> list[str]:
        files = []
        for name, data, extra in entries:
            (self.d / "fonts" / name).write_bytes(data)
            files.append({"family": "Brand", "file": name, **extra})
        (self.d / "brand.json").write_text(json.dumps({"fontFiles": files}))
        errs, warns = B.check_kit(self.d)
        self.assertEqual(errs, [])
        return warns

    def test_range_on_static(self):
        w = self.check(("Brand-Light.ttf", make_font(weight=300), {"weight": "100 900"}))
        self.assertEqual(w, ['fontFiles[0].weight: Brand-Light.ttf provides weight 300, not "100 900"'])

    def test_weight_outside_variable_range(self):
        w = self.check(("Brand-VF.ttf", make_font(wght=(400, 800)), {"weight": "100 800"}))
        self.assertEqual(w, ['fontFiles[0].weight: Brand-VF.ttf provides the weight range "400 800", not "100 800"'])
        w = self.check(("Brand-VF.ttf", make_font(wght=(400, 800)), {"weight": 900}))
        self.assertEqual(len(w), 1)

    def test_single_weight_on_static(self):
        self.assertEqual(len(self.check(("Brand.ttf", make_font(weight=400), {"weight": "700"}))), 1)

    def test_matching_entries(self):
        w = self.check(("Brand-VF.ttf", make_font(wght=(100, 900)), {}),
                       ("Brand.ttf", make_font(weight=400), {"weight": 400}),
                       ("Brand-Mid.ttf", make_font(wght=(100, 900)), {"weight": "300 700"}),
                       ("Brand-It.ttf", make_font(italic=True), {"style": "italic", "weight": "400"}))
        self.assertEqual(w, [])

    def test_italic_on_upright(self):
        w = self.check(("Brand.ttf", make_font(), {"style": "italic"}))
        self.assertEqual(w, ["fontFiles[0].style: Brand.ttf is upright, not italic"])

    def test_file_that_no_longer_loads(self):
        font = make_font()
        w = self.check(("Brand.ttf", font[: len(font) // 2], {"weight": 400}))
        self.assertEqual(len(w), 1)
        self.assertTrue(w[0].startswith("fontFiles[0].file: Brand.ttf doesn't load ("), w[0])

    def test_fixture_kit(self):
        for name in ("outfit/Outfit-VF.ttf", "barlow/Barlow-Light.ttf", "redhatmono/RedHatMono-VF.ttf"):
            shutil.copy(FIXTURE_FONTS / name, self.d / "fonts")
        (self.d / "brand.json").write_text(json.dumps({"fontFiles": [
            {"family": "Outfit", "file": "Outfit-VF.ttf", "weight": 400},
            {"family": "Barlow", "file": "Barlow-Light.ttf", "weight": "100 900"},
            {"family": "Red Hat Mono", "file": "RedHatMono-VF.ttf", "weight": "100 800"}]}))
        errs, warns = B.check_kit(self.d)
        self.assertEqual(errs, [])
        self.assertEqual([w.split(":")[0] for w in warns], ["fontFiles[1].weight", "fontFiles[2].weight"])

    def test_check_dir_ok_with_warnings(self):
        sub = self.d / "kit"
        (sub / "incoming").mkdir(parents=True)
        (sub / "incoming" / "Brand-Light.ttf").write_bytes(make_font(weight=300))
        (sub / "brand.json").write_text(json.dumps({"fontFiles": [{"family": "Brand", "file": "Brand-Light.ttf",
                                                                   "weight": "100 900"}]}))
        res = B.check_dir(sub)
        self.assertEqual(res["errors"], [])
        self.assertEqual(len(res["warnings"]), 1)


class CheckDir(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()) / "brand"
        (self.d / "incoming").mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.d.parent)

    def put(self, name: str, data: bytes):
        (self.d / "incoming" / name).write_bytes(data)

    def test_mixed_upload(self):
        font = make_font(family="Brand Sans")
        self.put("Brand-Regular.ttf", font)
        self.put("logo.png", png_bytes())
        self.put("broken.ttf", font[: len(font) // 2])
        self.put("notes.txt", b"hello")
        res = B.check_dir(self.d)
        by = {e["name"]: e for e in res["files"]}
        self.assertEqual(len(by), 4)
        self.assertEqual({n: e["status"] for n, e in by.items()},
                         {"Brand-Regular.ttf": "valid", "logo.png": "valid", "broken.ttf": "invalid", "notes.txt": "invalid"})
        self.assertEqual(by["Brand-Regular.ttf"]["family"], "Brand Sans")
        self.assertTrue(by["broken.ttf"]["reason"])
        self.assertIn("unsupported file type", by["notes.txt"]["reason"])
        self.assertEqual(sorted(p.name for p in (self.d / "fonts").iterdir()), ["Brand-Regular.ttf"])
        self.assertEqual(sorted(p.name for p in (self.d / "logos").iterdir()), ["logo.png"])
        self.assertEqual(list((self.d / "incoming").iterdir()), [])
        self.assertEqual((res["errors"], res["warnings"]), ([], []))

    def test_replaced_and_svg_kept_as_png_only(self):
        (self.d / "fonts").mkdir()
        (self.d / "fonts" / "Brand-Bold.ttf").write_bytes(b"old")
        self.put("Brand-Bold.ttf", make_font(weight=700))
        self.put("mark.svg", CLEAN_SVG)
        self.put("evil.svg", CLEAN_SVG.replace(b"</svg>", b"<script>x()</script></svg>"))
        res = B.check_dir(self.d)
        by = {e["name"]: e for e in res["files"]}
        self.assertTrue(by["Brand-Bold.ttf"]["replaced"])
        self.assertEqual(by["mark.svg"]["stored"], "logos/mark.png")
        self.assertEqual((by["mark.svg"]["width"], by["mark.svg"]["height"]), (2048, 512))
        self.assertEqual(by["evil.svg"]["status"], "invalid")
        self.assertEqual(sorted(p.name for p in (self.d / "logos").iterdir()), ["mark.png"])

    def test_kit_errors(self):
        (self.d / "brand.json").write_text(json.dumps({"colors": {"accent": "red"}}))
        res = B.check_dir(self.d)
        self.assertEqual(len(res["errors"]), 1)
        self.assertIn("colors.accent", res["errors"][0])


if __name__ == "__main__":
    unittest.main()
