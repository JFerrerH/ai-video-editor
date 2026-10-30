"""Capture a website as video-ready stills (Playwright + your installed Chrome).

Writes a phone-sized viewport shot and a full-page shot. Animate the full-page
PNG as a smooth scroll in Remotion (`WebsiteScroll` in tools/motion) — that is
smoother and more deterministic than a screen recording.

Before the full-page shot it scrolls the page top→bottom so scroll-triggered
reveals and lazy images render, then returns to the top.

Only capture sites the user owns or has rights to show.

This CLI is for trusted b-roll on your own machine (no network guard). Untrusted URLs go through
`capture_facts()` (the `site` job op): every request checked by tools/site_guard.py, measured
colours/fonts/images/text instead of a full-page shot.

Usage:
    uv run tools/site_capture.py https://www.example.com -o footage/<p>/edit/downloads/site
    uv run tools/site_capture.py URL -o DIR --width 430 --height 932 --dpr 2.5
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

PHONE = {"width": 430, "height": 932}
DPR = 2.5
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


def capture(url: str, out: Path, width: int, height: int, dpr: float, wait: float) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")  # system Chrome, no download
        except Exception:
            browser = p.chromium.launch()  # falls back to `playwright install chromium`
        ctx = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=dpr,
            is_mobile=True,
            has_touch=True,
            user_agent=MOBILE_UA,
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        time.sleep(wait)
        page.screenshot(path=str(out / "viewport.png"))

        # trigger scroll reveals / lazy loading
        total = page.evaluate("document.documentElement.scrollHeight")
        y = 0
        while y < total:
            y += height // 2
            page.evaluate(f"window.scrollTo(0, {y})")
            time.sleep(0.15)
            total = page.evaluate("document.documentElement.scrollHeight")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(wait)
        page.screenshot(path=str(out / "fullpage.png"), full_page=True)
        print(f"viewport.png + fullpage.png ({width}x{total} css px @ {dpr}x) → {out}")
        browser.close()


# ── measured brand facts (the `site` job op) ──────────────────────────────
MAX_COLORS = 16
MAX_IMAGES = 12
MAX_FONTS = 12
MAX_HEADINGS = 30
MAX_TEXT = 300
MAX_JSON = 64 * 1024
DELTA_E = 4.0
SETTLE_MS = 2000
SOCIAL = ("instagram.com", "tiktok.com", "youtube.com", "youtu.be", "x.com", "twitter.com", "facebook.com",
          "linkedin.com", "pinterest.com", "threads.net", "threads.com")
GOOGLE_CSS = "fonts.googleapis.com"
GOOGLE_FILES = "fonts.gstatic.com"
FONT_FACE = re.compile(r"@font-face\s*{([^}]*)}", re.I)
FACE_FAMILY = re.compile(r"font-family\s*:\s*['\"]?([^;'\"]+)", re.I)
FACE_WEIGHT = re.compile(r"font-weight\s*:\s*([^;]+)", re.I)
FACE_STYLE = re.compile(r"font-style\s*:\s*([^;]+)", re.I)
FACE_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)", re.I)

# One pass over the rendered page; returns plain JSON (Python caps and merges).
MEASURE = r"""() => {
  const W = innerWidth, H = innerHeight;
  const parse = c => { const m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const hex = o => '#' + [o.r, o.g, o.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
  const visArea = rect => Math.max(0, Math.min(rect.right, W) - Math.max(rect.left, 0)) * Math.max(0, Math.min(rect.bottom, H) - Math.max(rect.top, 0));
  const MEDIA = new Set(['img', 'video', 'canvas', 'picture', 'svg', 'iframe']);
  // the canvas: html's background, else body's (CSS propagates it to the whole viewport), else white
  const canvasOf = el => { const c = el && parse(getComputedStyle(el).backgroundColor); return c && c.a >= 0.99 ? hex(c) : null; };
  const canvas = canvasOf(document.documentElement) || canvasOf(document.body) || '#FFFFFF';
  const bg = {}; const GX = 27, GY = 58;
  for (let i = 0; i < GX; i++) for (let j = 0; j < GY; j++) {
    let found = null;
    for (const el of document.elementsFromPoint((i + 0.5) * W / GX, (j + 0.5) * H / GY)) {
      if (MEDIA.has(el.tagName.toLowerCase()) || el.closest('svg')) { found = 'image'; break; }
      const cs = getComputedStyle(el), c = parse(cs.backgroundColor);
      if (c && c.a >= 0.99) { found = hex(c); break; }
      if (cs.backgroundImage && cs.backgroundImage !== 'none') { found = 'image'; break; }
    }
    found = found || canvas;
    bg[found] = (bg[found] || 0) + 1;
  }
  const text = {};
  const tw = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (!n.textContent.trim() || !n.parentElement) continue;
    const cs = getComputedStyle(n.parentElement);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    let a = 0; for (const b of r.getClientRects()) a += visArea(b);
    const c = parse(cs.color);
    if (a > 0 && c && c.a >= 0.5) text[hex(c)] = (text[hex(c)] || 0) + a;
  }
  const inter = {};
  for (const el of document.querySelectorAll('a, button, [role=button], input[type=submit], input[type=button]')) {
    const a = visArea(el.getBoundingClientRect()); if (!a) continue;
    const cs = getComputedStyle(el);
    for (const c of [parse(cs.backgroundColor), parse(cs.color)]) if (c && c.a >= 0.99) inter[hex(c)] = (inter[hex(c)] || 0) + a;
  }
  const unq = s => s.trim().replace(/^["']|["']$/g, '');
  const loaded = new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => unq(f.family)));
  const ownText = el => [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim());
  const fonts = {};
  const groups = {headings: 'h1, h2, h3', body: 'body, p, li, span, div, td', interactive: 'a, button, [role=button], input[type=submit]'};
  for (const [use, sel] of Object.entries(groups)) for (const el of [...document.querySelectorAll(sel)].slice(0, 600)) {
    if (!ownText(el) && el.tagName !== 'INPUT') continue;
    const cs = getComputedStyle(el); const list = cs.fontFamily.split(',').map(unq).filter(Boolean);
    const fam = list.find(f => loaded.has(f)) || list[0]; if (!fam) continue;
    const f = fonts[fam] = fonts[fam] || {family: fam, use: [], weights: []};
    if (!f.use.includes(use)) f.use.push(use);
    const w = parseInt(cs.fontWeight, 10); if (w && !f.weights.includes(w)) f.weights.push(w);
  }
  const imgs = []; const seen = new Set();
  const add = (kind, src, extra) => { if (!src || seen.has(src) || imgs.length >= 24) return; seen.add(src); imgs.push({kind, src, ...extra}); };
  for (const l of document.querySelectorAll('link[rel~="icon"], link[rel~="apple-touch-icon"]'))
    add(/apple/i.test(l.rel) ? 'apple-touch-icon' : 'icon', l.href);
  const og = document.querySelector('meta[property="og:image"]');
  if (og && og.content) try { add('og:image', new URL(og.content, location.href).href); } catch (e) {}
  const inTop = el => { if (el.closest('header, nav')) return true; const r = el.getBoundingClientRect(); return r.width > 0 && r.top < H * 0.25; };
  for (const el of document.querySelectorAll('img, svg')) {
    if (!inTop(el)) continue;
    if (el.tagName.toLowerCase() === 'img') add('header-image', el.currentSrc || el.src);
    else if (!(el.parentElement && el.parentElement.closest('svg'))) {
      const svg = new XMLSerializer().serializeToString(el);
      add('header-svg', 'inline:' + svg.length + ':' + svg.slice(0, 200), {svg: svg.slice(0, 2100000)});
    }
  }
  const meta = n => { const m = document.querySelector(`meta[name="${n}"], meta[property="${n}"]`); return m ? m.content || '' : ''; };
  const headings = [...document.querySelectorAll('h1, h2, h3')].map(h => h.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 30);
  const social = [...new Set([...document.querySelectorAll('a[href]')].map(a => a.href))];
  return {bg, cells: GX * GY, text, inter, fonts: Object.values(fonts), imgs, title: document.title, description: meta('description'),
          og_title: meta('og:title'), og_description: meta('og:description'), headings, links: social.slice(0, 2000),
          styles: [...document.querySelectorAll('style')].map(s => s.textContent).join('\n').slice(0, 500000),
          viewport_area: W * H};
}"""


def _lab(h: str) -> tuple[float, float, float]:
    """#RRGGBB → CIE Lab (D65)."""
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _colors(m: dict) -> list[dict]:
    """Merge near-identical colours (ΔE76 < 4), rank by viewport share, tag roles; ≤ 16."""
    area = m["viewport_area"] or 1
    raw: dict[str, dict] = {}
    for h, n in m["bg"].items():
        if h != "image":
            raw.setdefault(h, {"share": 0.0, "text": 0.0, "inter": 0.0})["share"] += n / m["cells"]
    for key, src in (("text", m["text"]), ("inter", m["inter"])):
        for h, a in src.items():
            raw.setdefault(h, {"share": 0.0, "text": 0.0, "inter": 0.0})[key] += a / area
    order = sorted(raw, key=lambda h: (raw[h]["share"], raw[h]["text"] + raw[h]["inter"]), reverse=True)
    groups: list[tuple[str, tuple, dict]] = []
    for h in order:
        lab = _lab(h)
        for rep, rlab, acc in groups:
            if math.dist(lab, rlab) < DELTA_E:
                for k in acc:
                    acc[k] += raw[h][k]
                break
        else:
            groups.append((h, lab, dict(raw[h])))
    out = []
    for h, _, acc in sorted(groups, key=lambda g: (g[2]["share"], g[2]["text"] + g[2]["inter"]), reverse=True):
        roles = [r for r, k in (("background", "share"), ("text", "text"), ("interactive", "inter")) if acc[k] > 0]
        out.append({"hex": h, "share": round(acc["share"], 4), "text_share": round(acc["text"], 4),
                    "interactive_share": round(acc["inter"], 4), "roles": roles})
    return out[:MAX_COLORS]


def _faces(css: str, base: str) -> list[dict]:
    faces = []
    for block in FONT_FACE.findall(css):
        fam = FACE_FAMILY.search(block)
        if not fam:
            continue
        urls = [urljoin(base, u.strip()) for u in FACE_URL.findall(block) if not u.strip().startswith("data:")]
        w, st = FACE_WEIGHT.search(block), FACE_STYLE.search(block)
        faces.append({"family": fam.group(1).strip(), "urls": urls, "weight": w.group(1).strip() if w else "400",
                      "style": st.group(1).strip() if st else "normal"})
    return faces


def _cap(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()[:MAX_TEXT]


def _candidate_bytes(c: dict, g, stats: dict) -> bytes:
    """An image candidate's bytes: inline SVG markup, a base64 data URL, or one guarded fetch."""
    import brand_files as BF
    from site_guard import FetchError, GuardError

    if "svg" in c:
        return c["svg"].encode()
    if c["src"].startswith("data:"):  # no request
        if not (mm := BF.DATA_IMAGE.fullmatch(c["src"].strip())):
            raise BF.Invalid("inline data URL that isn't a base64 PNG or JPEG")
        return base64.b64decode(mm.group(0).split(",", 1)[1])
    try:
        r = g.fetch(c["src"], {"user-agent": MOBILE_UA})
    except GuardError as err:
        stats["blocked"] += 1
        raise BF.Invalid(f"refused: {err}") from None
    except FetchError as err:
        raise BF.Invalid(str(err)) from None
    if r.status != 200:
        raise BF.Invalid(f"HTTP {r.status}")
    return r.body


def capture_facts(url: str, out: Path, guard=None, settle_ms: int = SETTLE_MS) -> dict:
    """Load `url` through the guard into `out` (viewport.png, capture.json, images/, fonts/).

    Raises site_guard.GuardError if the page itself is refused, FetchError if it can't be loaded."""
    import brand_files as BF
    from browser import launch_browser
    from site_guard import FetchError, Guard, GuardError

    g = guard or Guard()
    head = {"user-agent": MOBILE_UA, "accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    main = g.fetch(url, head)  # refusal or failure here: nothing is launched
    if "html" not in main.content_type:
        raise FetchError(f"not an HTML page ({main.content_type or 'no content type'})")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    stats = {"requests": 0, "blocked": 0, "failed": 0}

    def handle(route, request) -> None:
        u = request.url
        if u.startswith(("data:", "blob:")):
            route.continue_()
            return
        stats["requests"] += 1
        if request.method not in ("GET", "HEAD"):
            stats["blocked"] += 1
            route.abort("blockedbyclient")
            return
        try:
            r = g.fetch(u, request.headers)
        except GuardError:
            stats["blocked"] += 1
            route.abort("blockedbyclient")
            return
        except FetchError:
            stats["failed"] += 1
            route.abort("failed")
            return
        route.fulfill(status=r.status, headers=g.fulfil_headers(r), body=r.body)

    with sync_playwright() as p:
        browser = launch_browser(p, proxy={"server": "http://127.0.0.1:9"},  # a closed port: anything unrouted fails
                                 args=["--disable-features=DnsPrefetching",
                                       "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
        try:
            ctx = browser.new_context(viewport=PHONE, device_scale_factor=DPR, is_mobile=True, has_touch=True,
                                      user_agent=MOBILE_UA, service_workers="block", accept_downloads=False)
            ctx.route("**/*", handle)
            ctx.route_web_socket("**/*", lambda ws: ws.close())
            page = ctx.new_page()
            try:
                page.goto(main.url, wait_until="load", timeout=max(1000, g.remaining() * 1000))
            except Exception:  # noqa: BLE001 - slow page: measure what loaded
                g.truncated = True
            page.wait_for_timeout(max(0, min(settle_ms, g.remaining() * 1000)))
            page.screenshot(path=str(out / "viewport.png"))
            m = page.evaluate(MEASURE)
        finally:
            browser.close()

    # fonts: where each family comes from (CSS the guard fetched + inline <style>)
    google_faces, own_faces = [], []
    for r in list(g.cache.values()):
        if r.content_type == "text/css" or urlsplit(r.url).hostname == GOOGLE_CSS:
            text = r.body.decode("utf-8", "replace")
            (google_faces if urlsplit(r.url).hostname == GOOGLE_CSS else own_faces).extend(_faces(text, r.url))
    own_faces += _faces(m["styles"], main.url)
    google_names = {f["family"].lower() for f in google_faces}
    fonts = []
    for f in m["fonts"][:MAX_FONTS]:
        name = f["family"]
        e = {"family": name[:80], "use": f["use"], "weights": sorted(f["weights"])}
        own = next((x for x in own_faces if x["family"].lower() == name.lower() and x["urls"]), None)
        if name.lower() in google_names:
            e["source"] = "google"
        elif own:
            e.update(source="font-face", url=own["urls"][0][:MAX_TEXT])
        else:
            e["source"] = "system"
        fonts.append(e)
    saved_fonts = (out / "fonts")
    used_google = {f["family"].lower() for f in fonts if f["source"] == "google"}
    for face in google_faces:
        if face["family"].lower() not in used_google:
            continue
        for u in face["urls"]:
            r = g.cache.get(u)
            if not r or urlsplit(u).hostname != GOOGLE_FILES:
                continue  # only files the page actually loaded, only from Google's font host
            try:
                data, ext, facts = BF.validate_font(r.body)
            except BF.Invalid:
                continue  # e.g. a subset without Latin letters
            stem = BF.safe_stem(f"{facts['family']}-{facts['weight']}{'-italic' if facts['style'] == 'italic' else ''}")
            dest, i = saved_fonts / f"{stem}{ext}", 1
            while dest.exists():
                i += 1
                dest = saved_fonts / f"{stem}-{i}{ext}"
            saved_fonts.mkdir(exist_ok=True)
            dest.write_bytes(data)
            for fe in fonts:
                if fe["family"].lower() == face["family"].lower():
                    fe.setdefault("files", []).append(f"site/fonts/{dest.name}")

    # image candidates: the same validators as brand files; the page's bytes, else one guarded fetch
    images = []
    with BF.Rasterizer() as raster:
        for c in m["imgs"][:MAX_IMAGES]:
            n = len(images) + 1
            inline = "svg" in c or c["src"].startswith("data:")
            e = {"n": n, "kind": c["kind"], "source": "inline" if inline else c["src"][:MAX_TEXT]}
            try:
                body = _candidate_bytes(c, g, stats)
                orig = None
                if BF.sniff(body) == "svg":  # kept only as the rasterized preview
                    png, facts = BF.validate_raster(raster.png(body, BF.validate_svg(body), long_side=1024))
                else:
                    orig, facts = BF.validate_raster(body)
                    png, _ = BF.validate_raster(body, long_side=1024)
                (out / "images").mkdir(exist_ok=True)
                (out / "images" / f"{n:02d}.png").write_bytes(png)
                e.update(status="valid", width=facts["width"], height=facts["height"], file=f"site/images/{n:02d}.png")
                if orig is not None:
                    (out / "images" / f"{n:02d}.orig.png").write_bytes(orig)
                    e["original"] = f"site/images/{n:02d}.orig.png"
            except BF.Invalid as err:
                e.update(status="invalid", reason=str(err)[:MAX_TEXT])
            images.append(e)

    social = []
    for link in m["links"]:
        host = (urlsplit(link).hostname or "").lower().removeprefix("www.").removeprefix("m.")
        if any(host == s or host.endswith("." + s) for s in SOCIAL) and link not in social:
            social.append(link[:MAX_TEXT])
    cap = {
        "url": url[:2048], "final_url": main.url[:2048], "status": main.status,
        "title": _cap(m["title"]), "description": _cap(m["description"]),
        "og_title": _cap(m["og_title"]), "og_description": _cap(m["og_description"]),
        "headings": [_cap(h) for h in m["headings"][:MAX_HEADINGS]],
        "social": social[:12], "colors": _colors(m), "fonts": fonts, "images": images,
        "requests": stats["requests"], "blocked": stats["blocked"], "failed": stats["failed"],
        "fetched_bytes": g.fetched, "truncated": g.truncated,
    }
    while len(json.dumps(cap, ensure_ascii=False, indent=1).encode()) > MAX_JSON:  # caps keep this rare
        for k in ("headings", "social", "images", "colors", "fonts"):
            if cap[k]:
                cap[k] = cap[k][:-1]
                break
        else:
            break
    (out / "capture.json").write_text(json.dumps(cap, ensure_ascii=False, indent=1))
    return cap


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--width", type=int, default=430)
    ap.add_argument("--height", type=int, default=932)
    ap.add_argument("--dpr", type=float, default=2.5)
    ap.add_argument("--wait", type=float, default=1.5, help="seconds to let animations settle")
    a = ap.parse_args()
    capture(a.url, a.out, a.width, a.height, a.dpr, a.wait)


if __name__ == "__main__":
    main()
