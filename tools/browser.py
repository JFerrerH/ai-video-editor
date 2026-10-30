"""One headless browser for the tools that drive a page (site capture, SVG rasterizing).

    from browser import launch_browser
    with sync_playwright() as p:
        b = launch_browser(p)                  # → playwright Browser
        b = launch_browser(p, proxy={...})     # extra launch options pass through

No browser download: system Chrome on the Mac, then the Chrome Headless Shell Remotion already
installs under tools/motion (the only browser in the Docker image), then Playwright's own Chromium
if someone ran `playwright install`.
"""

from __future__ import annotations

import sys
from pathlib import Path

MOTION = Path(__file__).resolve().parent / "motion"


def remotion_shell() -> Path | None:
    """Remotion's Chrome Headless Shell binary (macOS and Linux names), if installed."""
    for name in ("chrome-headless-shell", "headless_shell"):
        for p in sorted((MOTION / "node_modules" / ".remotion").glob(f"chrome-headless-shell/*/*/{name}")):
            if p.is_file():
                return p
    return None


def launch_browser(p, **opts):
    """Launch the first browser that starts; raises the last error if none does."""
    attempts: list[dict] = []
    if sys.platform == "darwin":
        attempts.append({"channel": "chrome"})
    if shell := remotion_shell():
        attempts.append({"executable_path": str(shell)})
    attempts.append({})  # Playwright's own Chromium
    err: Exception | None = None
    for a in attempts:
        try:
            return p.chromium.launch(headless=True, **a, **opts)
        except Exception as e:  # noqa: BLE001 - try the next browser
            err = e
    raise RuntimeError(f"no headless browser starts: {err}")


def smoke() -> str:
    """Launch, open about:blank, close. Returns the browser version."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = launch_browser(p)
        try:
            page = b.new_page()
            page.goto("about:blank")
            return b.version
        finally:
            b.close()
