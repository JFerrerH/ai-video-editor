"""Brand file validation: prove a font, image or SVG is harmless and usable before a render loads it.

    from brand_files import check_dir
    res = check_dir(Path("brands/acme"))     # validates brands/acme/incoming/* → fonts/ or logos/

    res == {"files": [{"name", "kind", "status": "valid"|"invalid", "reason"?, "stored"?, "replaced"?,
                       "family"?, "weight"?, "style"?, "width"?, "height"?}],
            "errors": ["colors.accent: …", …]}      # brand.json shape errors (empty when fine)

Kinds come from the bytes, not the name; the extension only says whether a font or an image was
expected. Fonts (TTF/OTF/WOFF/WOFF2, ≤ 5 MB) must parse completely and map A–Z a–z 0–9; WOFF/WOFF2
are unwrapped to TTF/OTF. Raster images (PNG/JPEG, ≤ 20 MB, ≤ 8000 px a side) are size-checked
from the header before decoding, then re-encoded as PNG without metadata. SVGs (≤ 2 MB) are parsed
without DTDs or entities, refused on scripts, event handlers, foreignObject/iframe/embed/object or
any external reference, and kept only as a PNG rasterized in the headless browser (image context,
network off). Invalid files are deleted; nothing derived from them is kept.
"""

from __future__ import annotations

import base64
import io
import json
import re
import shutil
import tempfile
import warnings
from pathlib import Path

MAX_FONT = 5 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024
MAX_SIDE = 8000
MAX_PIXELS = 64_000_000
MAX_SVG = 2 * 1024 * 1024
SVG_LONG_SIDE = 2048

FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".svg"}
SVG_NS = "{http://www.w3.org/2000/svg}"
SVG_BANNED = {"script", "foreignobject", "iframe", "embed", "object"}
DATA_IMAGE = re.compile(r"data:image/(png|jpeg);base64,[A-Za-z0-9+/=\s]*")
CSS_URL = re.compile(r"url\(\s*['\"]?\s*([^'\")\s]*)", re.I)

COLOR_ROLES = ("bg", "tint1", "tint2", "ink", "muted", "accent", "success")
FONT_ROLES = ("serif", "sans", "mono")
HEX = re.compile(r"#[0-9A-Fa-f]{6}")
# caption options the renderer accepts (tools/motion/src/components/Captions.tsx) and their ranges
CAPTIONS = {"top": (0, 1920), "size": (20, 160), "emphSize": (20, 160), "emphWeight": (100, 900), "shade": (0, 1)}


class Invalid(Exception):
    """The file is refused; the message is the reason."""


def sniff(data: bytes) -> str | None:
    head = data[:4]
    if head in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
        return "font"
    if head == b"wOFF":
        return "woff"
    if head == b"wOF2":
        return "woff2"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    text = data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith(b"<?xml") or text.startswith(b"<svg") or text.startswith(b"<!--"):
        return "svg"
    return None


def safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).stem).strip("._") or "file"
    return stem[:80]


# ── fonts ─────────────────────────────────────────────────────────────────
def validate_font(data: bytes) -> tuple[bytes, str, dict]:
    """→ (stored bytes, extension, {family, weight, style}); Invalid if it doesn't parse completely."""
    from fontTools.pens.boundsPen import ControlBoundsPen
    from fontTools.ttLib import TTFont

    if len(data) > MAX_FONT:
        raise Invalid(f"font is {len(data) / 1e6:.1f} MB; the limit is 5 MB")
    kind = sniff(data)
    if kind not in ("font", "woff", "woff2"):
        raise Invalid("not a TTF, OTF, WOFF or WOFF2 font")
    try:
        f = TTFont(io.BytesIO(data), lazy=False, recalcBBoxes=False, recalcTimestamp=False)
        missing = [t for t in ("cmap", "name", "head", "hhea", "hmtx", "maxp", "OS/2") if t not in f]
        outlines = "glyf" if "glyf" in f else "CFF " if "CFF " in f else "CFF2" if "CFF2" in f else None
        if missing or not outlines:
            raise Invalid(f"font is missing table(s): {', '.join(missing + ([] if outlines else ['glyf/CFF']))}")
        f.ensureDecompiled()
        gs = f.getGlyphSet()
        for g in f.getGlyphOrder():  # decompile every outline: a truncated table fails here, not in the renderer
            gs[g].draw(ControlBoundsPen(gs))
        cmap = f.getBestCmap() or {}
        need = [chr(c) for c in (*range(65, 91), *range(97, 123), *range(48, 58)) if c not in cmap]
        if need:
            raise Invalid(f"font doesn't map {''.join(need[:12])}{'…' if len(need) > 12 else ''}")
        name = f["name"]
        family = str(name.getDebugName(16) or name.getDebugName(1) or "").strip()
        if not family:
            raise Invalid("font has no family name")
        weight = min(900, max(100, int(f["OS/2"].usWeightClass)))
        italic = bool(f["OS/2"].fsSelection & 1) or bool(f["head"].macStyle & 2)
        ext = ".ttf" if outlines == "glyf" else ".otf"
        if kind == "font":
            out = data  # parsed completely; re-saving could alter hinting
        else:
            f.flavor = None
            buf = io.BytesIO()
            f.save(buf)
            out = buf.getvalue()
    except Invalid:
        raise
    except Exception as e:  # noqa: BLE001 - any parser failure is a refusal
        raise Invalid(f"font doesn't parse: {type(e).__name__}: {str(e)[:120]}") from None
    return out, ext, {"family": family[:80], "weight": weight, "style": "italic" if italic else "normal"}


# ── raster images ─────────────────────────────────────────────────────────
def validate_raster(data: bytes, long_side: int | None = None) -> tuple[bytes, dict]:
    """→ (PNG bytes without metadata, {width, height, format}); Invalid if refused."""
    from PIL import Image, ImageOps

    if len(data) > MAX_IMAGE:
        raise Invalid(f"image is {len(data) / 1e6:.1f} MB; the limit is 20 MB")
    kind = sniff(data)
    if kind not in ("png", "jpeg"):
        raise Invalid("not a PNG or JPEG image")
    saved = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(data), formats=["PNG", "JPEG"])
            w, h = im.size  # header only: nothing decoded yet
            if w > MAX_SIDE or h > MAX_SIDE:
                raise Invalid(f"image is {w}x{h} px; the limit is 8000 px a side")
            im.load()
            im = ImageOps.exif_transpose(im)
            alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            im = im.convert("RGBA" if alpha else "RGB")
            if long_side and max(im.size) > long_side:
                im.thumbnail((long_side, long_side), Image.Resampling.LANCZOS)
            clean = Image.new(im.mode, im.size)
            clean.paste(im)
            buf = io.BytesIO()
            clean.save(buf, "PNG", optimize=True)
    except Invalid:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise Invalid("image declares too many pixels; the limit is 8000 px a side") from None
    except Exception as e:  # noqa: BLE001
        raise Invalid(f"image doesn't decode: {type(e).__name__}: {str(e)[:120]}") from None
    finally:
        Image.MAX_IMAGE_PIXELS = saved
    return buf.getvalue(), {"width": clean.width, "height": clean.height, "format": kind}


# ── SVG ───────────────────────────────────────────────────────────────────
def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].split(":")[-1].lower()


def _bad_css(text: str) -> str | None:
    if "@import" in text.lower():
        return "CSS @import"
    for m in CSS_URL.finditer(text):
        if not m.group(1).startswith("#"):
            return f"external CSS url({m.group(1)[:60]})"
    return None


def validate_svg(data: bytes) -> tuple[float, float]:
    """Refuse anything that could run or fetch; → the drawing's (width, height) aspect source."""
    from defusedxml import ElementTree as ET
    from defusedxml.common import DefusedXmlException

    if len(data) > MAX_SVG:
        raise Invalid(f"SVG is {len(data) / 1e6:.1f} MB; the limit is 2 MB")
    try:
        root = ET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as e:
        raise Invalid(f"SVG declares a DTD or entities ({type(e).__name__})") from None
    except Exception as e:  # noqa: BLE001
        raise Invalid(f"SVG doesn't parse: {str(e)[:120]}") from None
    if root.tag != f"{SVG_NS}svg":
        raise Invalid("not an SVG document")
    for el in root.iter():
        tag = _local(str(el.tag))
        if tag in SVG_BANNED:
            raise Invalid(f"SVG contains a <{tag}> element")
        for k, v in el.attrib.items():
            name = _local(k)
            if name.startswith("on"):
                raise Invalid(f"SVG has an event handler ({name})")
            if name == "href" and not (v.startswith("#") or DATA_IMAGE.fullmatch(v.strip())):
                raise Invalid(f"SVG has an external reference ({v[:60]})")
            if tag in ("set", "animate") and name == "attributename" and (v.lower().endswith("href") or v.lower().startswith("on")):
                raise Invalid(f"SVG animates {v}")
            if why := _bad_css(v):
                raise Invalid(f"SVG has an {why}")
        if tag == "style" and (why := _bad_css("".join(el.itertext()))):
            raise Invalid(f"SVG has an {why}")
    vb = re.split(r"[\s,]+", root.get("viewBox", "").strip())
    try:
        if len(vb) == 4 and float(vb[2]) > 0 and float(vb[3]) > 0:
            return float(vb[2]), float(vb[3])
        w, h = (float(re.sub(r"(px)?$", "", root.get(a, ""))) for a in ("width", "height"))
        if w > 0 and h > 0:
            return w, h
    except ValueError:
        pass
    raise Invalid("SVG has no size (viewBox or width/height in px)")


class Rasterizer:
    """Draws clean SVGs to PNG in the headless browser, started on first use, network off.

    with Rasterizer() as r:
        png = r.png(svg_bytes, (200, 50), long_side=2048)
    """

    def __init__(self):
        self._pw = self._browser = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def png(self, svg: bytes, size: tuple[float, float], long_side: int = SVG_LONG_SIDE) -> bytes:
        if self._browser is None:
            from playwright.sync_api import sync_playwright

            from browser import launch_browser

            self._pw = sync_playwright().start()
            self._browser = launch_browser(self._pw, proxy={"server": "http://127.0.0.1:9"})
        sw, sh = size
        scale = long_side / max(sw, sh)
        w, h = max(1, round(sw * scale)), max(1, round(sh * scale))
        ctx = self._browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                        java_script_enabled=True, service_workers="block")
        try:
            ctx.route("**/*", lambda route: route.abort())
            page = ctx.new_page()
            src = "data:image/svg+xml;base64," + base64.b64encode(svg).decode()
            page.set_content(f'<html><body style="margin:0;background:transparent">'
                             f'<img src="{src}" style="display:block;width:{w}px;height:{h}px"></body></html>')
            page.wait_for_function("document.images[0].complete", timeout=10_000)
            if not page.evaluate("document.images[0].naturalWidth > 0"):
                raise Invalid("SVG doesn't render")
            return page.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
        except Invalid:
            raise
        except Exception as e:  # noqa: BLE001 - a timeout or crash is a refusal of this file
            raise Invalid(f"SVG doesn't render: {type(e).__name__}") from None
        finally:
            ctx.close()


# ── one file ──────────────────────────────────────────────────────────────
def validate_file(src: Path, raster: Rasterizer) -> tuple[str, bytes, str, dict]:
    """→ (kind, stored bytes, stored extension, facts). Invalid with the reason if refused."""
    ext = src.suffix.lower()
    if ext not in FONT_EXT | IMAGE_EXT:
        raise Invalid(f"unsupported file type {ext or '(none)'} (fonts: TTF, OTF, WOFF, WOFF2; images: PNG, JPEG, SVG)")
    size = src.stat().st_size
    if size > MAX_IMAGE:
        raise Invalid(f"file is {size / 1e6:.1f} MB; the limit is 20 MB")
    data = src.read_bytes()
    if ext in FONT_EXT:
        out, oext, facts = validate_font(data)
        return "font", out, oext, facts
    if sniff(data) == "svg":
        if ext not in (".svg",):
            raise Invalid("not a PNG or JPEG image")
        aspect = validate_svg(data)
        png = raster.png(data, aspect)
        out, facts = validate_raster(png)  # what the browser drew is checked like any other image
        return "svg", out, ".png", {"width": facts["width"], "height": facts["height"]}
    if ext == ".svg":
        raise Invalid("not an SVG document")
    out, facts = validate_raster(data)
    return "image", out, ".png", {"width": facts["width"], "height": facts["height"]}


# ── brand.json shape ──────────────────────────────────────────────────────
def check_kit(d: Path) -> list[str]:
    """Shape errors of `<d>/brand.json`, each naming its field; [] when fine or absent."""
    p = d / "brand.json"
    if not p.exists():
        return []
    try:
        kit = json.loads(p.read_text())
    except (OSError, ValueError) as e:
        return [f"brand.json: not valid JSON ({e})"]
    if not isinstance(kit, dict):
        return ["brand.json: must be an object"]
    errs: list[str] = []
    errs += [f"{k}: unknown key" for k in kit if k not in ("name", "colors", "fonts", "fontFiles", "captions")]
    if "name" in kit and not (isinstance(kit["name"], str) and 0 < len(kit["name"]) <= 80):
        errs.append("name: must be text of 1–80 characters")
    colors = kit.get("colors", {})
    if not isinstance(colors, dict):
        errs.append("colors: must be an object")
    else:
        for k, v in colors.items():
            if k not in COLOR_ROLES:
                errs.append(f"colors.{k}: unknown colour role (use {', '.join(COLOR_ROLES)})")
            elif not (isinstance(v, str) and HEX.fullmatch(v)):
                errs.append(f"colors.{k}: must be #RRGGBB, got {v!r}")
    fonts = kit.get("fonts", {})
    if not isinstance(fonts, dict):
        errs.append("fonts: must be an object")
    else:
        for k, v in fonts.items():
            if k not in FONT_ROLES:
                errs.append(f"fonts.{k}: unknown font role (use serif, sans, mono)")
            elif not (isinstance(v, str) and 0 < len(v) <= 80):
                errs.append(f"fonts.{k}: must be a family name of 1–80 characters")
    files = kit.get("fontFiles", [])
    if not isinstance(files, list):
        errs.append("fontFiles: must be a list")
        files = []
    for i, f in enumerate(files):
        at = f"fontFiles[{i}]"
        if not isinstance(f, dict):
            errs.append(f"{at}: must be an object")
            continue
        errs += [f"{at}.{k}: unknown key" for k in f if k not in ("family", "file", "weight", "style")]
        if not (isinstance(f.get("family"), str) and 0 < len(f["family"]) <= 80):
            errs.append(f"{at}.family: must be a family name of 1–80 characters")
        name = f.get("file")
        if not (isinstance(name, str) and name and Path(name).name == name and not name.startswith(".")):
            errs.append(f"{at}.file: must be a file name in fonts/")
        elif not (d / "fonts" / name).is_file():
            errs.append(f"{at}.file: {name} is not a validated font in fonts/")
        if "weight" in f:
            w = f["weight"]
            parts = str(w).split() if isinstance(w, (str, int)) and not isinstance(w, bool) else []
            if not (1 <= len(parts) <= 2 and all(p.isdigit() and 100 <= int(p) <= 900 for p in parts)):
                errs.append(f"{at}.weight: must be 100–900 or a range like \"400 700\"")
        if "style" in f and f["style"] not in ("normal", "italic"):
            errs.append(f"{at}.style: must be normal or italic")
    caps = kit.get("captions", {})
    if not isinstance(caps, dict):
        errs.append("captions: must be an object")
        caps = {}
    for k, v in caps.items():
        at = f"captions.{k}"
        if k in CAPTIONS:
            lo, hi = CAPTIONS[k]
            if not (isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi):
                errs.append(f"{at}: must be a number from {lo} to {hi}")
        elif k == "emphColor":
            if not (isinstance(v, str) and (HEX.fullmatch(v) or v in ("white", "black"))):
                errs.append(f"{at}: must be #RRGGBB, white or black")
        elif k == "mode":
            if v not in ("phrase", "word"):
                errs.append(f"{at}: must be phrase or word")
        elif k == "emphCaps":
            if not isinstance(v, bool):
                errs.append(f"{at}: must be true or false")
        else:
            errs.append(f"{at}: unknown caption option")
    return errs


# ── a whole kit directory ─────────────────────────────────────────────────
def check_dir(d: Path) -> dict:
    """Validate every file directly in `<d>/incoming/` into `fonts/` or `logos/`, delete the rest,
    then check `<d>/brand.json`. See the module docstring for the result shape."""
    incoming = d / "incoming"
    entries: list[dict] = []
    items = sorted(incoming.iterdir()) if incoming.is_dir() else []
    with Rasterizer() as raster, tempfile.TemporaryDirectory() as tmp:
        for src in items:
            e: dict = {"name": src.name[:200], "kind": "unknown"}
            try:
                if src.is_symlink() or not src.is_file():
                    e["kind"] = "directory" if src.is_dir() else "other"
                    raise Invalid("not a regular file")
                kind, data, ext, facts = validate_file(src, raster)
                e["kind"] = "font" if kind == "font" else "image"
                sub = "fonts" if kind == "font" else "logos"
                staged = Path(tmp) / (safe_stem(src.name) + ext)
                staged.write_bytes(data)
                dest = d / sub / staged.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                replaced = dest.exists()
                shutil.move(str(staged), dest)
                e.update(status="valid", stored=f"{sub}/{dest.name}", **facts)
                if replaced:
                    e["replaced"] = True
            except Invalid as err:
                if e["kind"] == "unknown":
                    e["kind"] = "font" if src.suffix.lower() in FONT_EXT else "image" if src.suffix.lower() in IMAGE_EXT else "other"
                e.update(status="invalid", reason=str(err))
            finally:
                if src.is_dir() and not src.is_symlink():
                    shutil.rmtree(src, ignore_errors=True)
                else:
                    src.unlink(missing_ok=True)
            entries.append(e)
    return {"files": entries, "errors": check_kit(d)}
