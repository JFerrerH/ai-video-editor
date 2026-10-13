"""Capture a website as video-ready stills (Playwright + your installed Chrome).

Writes a phone-sized viewport shot and a full-page shot. Animate the full-page
PNG as a smooth scroll in Remotion (`WebsiteScroll` in tools/motion) — that is
smoother and more deterministic than a screen recording.

Before the full-page shot it scrolls the page top→bottom so scroll-triggered
reveals and lazy images render, then returns to the top.

Only capture sites the user owns or has rights to show.

Usage:
    uv run tools/site_capture.py https://www.example.com -o footage/<p>/edit/downloads/site
    uv run tools/site_capture.py URL -o DIR --width 430 --height 932 --dpr 2.5
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


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
            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"),
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
