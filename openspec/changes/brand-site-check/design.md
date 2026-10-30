# Design

## Context

- **`tools/run_job.py`** runs one validated op in `footage/<project>/`. `outputs` is computed by snapshotting the project before and after the op, so an op that writes outside the project reports nothing. Paths in `args` are confined with `confine()`. Exit codes: 0 ok, 1 the op failed, 2 the job was rejected (`JobError`).
- **`tools/site_capture.py`** is a trusted CLI for b-roll: Playwright, system Chrome (or Playwright's Chromium), phone viewport and full-page PNGs, no network guard.
- **`tools/brand.py`** loads `brands/<slug>/brand.json` and stages `fonts/` for Remotion. It checks only that font files exist.
- **The Docker image** installs the Playwright Python package (default deps) but no Playwright browser. Remotion's Chrome Headless Shell is installed under `tools/motion/node_modules/.remotion/` by `npx remotion browser ensure`. `libcairo2` is present only as a Chrome dependency.
- **Caption options** the renderer accepts (`tools/motion/src/components/Captions.tsx`): `top`, `size`, `emphSize`, `emphColor`, `mode` (`phrase`/`word`), `emphCaps`, `emphWeight`, `shade`.

## Goals / Non-Goals

**Goals:**
- A capture cannot reach a refused address, even with DNS rebinding, redirects, or requests the page makes from script.
- No byte of an uploaded or captured file reaches a kit unless a validator accepted it, and what is stored is re-encoded by the engine (PNG, unwrapped sfnt), not the original bytes, except for fonts that already parsed completely.
- No new browser download, no heavy dependency, and the same behaviour on the Mac and in the image.

**Non-Goals:**
- Process-level isolation of the browser (network namespaces, seccomp). The hosted caller adds a scrubbed environment; the engine guarantees the request path.
- Perfect colour extraction for image-heavy pages. Facts are measured from CSS plus pixels; a person chooses.

## Decisions

### 1. Both ops are project-scoped

`site` writes `footage/<project>/site/`; `brand check` works on `footage/<project>/<dir>/` (default `brand`). A caller lays a kit out as `brand/incoming/…` and optionally `brand/brand.json`, runs the check, and collects `outputs`. This keeps the existing job contract (confined paths, `outputs` from the snapshot) with no special case for `brands/`. Local kits use `tools/brand_check.py brands/<slug>`, which calls the same function.

*Alternative:* a `brand` arg naming `brands/<slug>/`. Rejected: it needs a second confinement root and a second snapshot, and a hosted runner would have to sync results from outside the project.

### 2. The guard fetches; the browser only renders

Checking a host and then letting Chrome connect leaves a gap: Chrome resolves the name again, and a rebinding DNS server can answer differently the second time. So Chrome never connects anywhere:
- Every request is intercepted with `context.route("**/*")`. The handler (`tools/site_guard.py`) parses the URL, refuses bad schemes, ports and credentials, resolves the host with `getaddrinfo`, refuses if **any** address is in a refused range (`ipaddress` `is_private`/`is_loopback`/`is_link_local`/`is_multicast`/`is_reserved`/`is_unspecified`, plus explicit `100.64.0.0/10`, `fc00::/7`, `fe80::/10` and IPv4-mapped IPv6 unwrapped first), then fetches with `urllib3` connected to the **checked IP** (`server_hostname` and `assert_hostname` set to the host, so TLS still verifies the real name; `Host` header kept). Redirects are not followed by urllib3: the handler follows up to 5 hops itself, re-checking each, then `route.fulfill()`s the final response.
- Defence in depth: the browser is launched with `proxy={"server": "http://127.0.0.1:9"}` (a closed port), so any request that escaped routing fails instead of going out. `service_workers="block"`, `accept_downloads=False`, `context.route_web_socket("**/*", close)`, `--disable-features=DnsPrefetching`, WebRTC limited to proxied (`--force-webrtc-ip-handling-policy=disable_non_proxied_udp`).
- Budget: a shared counter of body bytes (per response capped at 8 MB, total 20 MB) and a deadline (30 s). Past either, the handler aborts new requests and the capture measures what has loaded (`truncated: true`).
- The main document is checked before the browser starts (exit 2 on refusal, nothing launched). A redirect of the main document to a refused address raises the same rejection. Refused sub-resources are aborted and counted.

*Alternative:* `route.continue_()` after a DNS check. Rejected for the rebinding gap. *Alternative:* a separate egress proxy process. Rejected as more moving parts for the same guarantee.

### 3. Browser: Remotion's headless shell, system Chrome on the Mac

`launch(executable_path=<remotion chrome-headless-shell>)` on Linux; `channel="chrome"` first on the Mac, then the headless shell, then Playwright's own Chromium if installed. The Playwright Python version is pinned (1.63) and talks CDP; a task verifies it drives the shell Remotion 4.0.535 installs, on both arm64 and amd64. If it does not, fall back to `playwright install chromium-headless-shell` in the Dockerfile (~110 MB) and record the size.

### 4. Measuring the page

After `load` plus a short settle (≤ 2 s, inside the budget), one `page.evaluate` script collects:
- **Background area:** a 27×58 grid over the viewport; at each point `document.elementsFromPoint`, the first element with an opaque computed `background-color` (or an `<img>`/`<video>`/canvas, counted as `image`) gives that cell's colour. Shares = cells / total.
- **Text colour:** for each visible text node's element, computed `color` weighted by its client-rect area.
- **Interactive:** `a`, `button`, `[role=button]`, `input[type=submit]`: background and text colours with their area.
- **Fonts:** computed `font-family` of `h1–h3`, body text and interactive elements, resolved to the first family the document actually loaded (`document.fonts` with status `loaded`), with weights in use. Source comes from the responses the guard fetched: CSS from `fonts.googleapis.com` → `google`; an `@font-face` `src` URL → `font-face`; otherwise `system`.
- **Images:** `link[rel~=icon]`, `apple-touch-icon`, `meta[property=og:image]`, then `img`/inline `svg` inside `header`, `nav` or the top 25% of the viewport, deduplicated by URL, first 12.
- **Text:** `title`, `meta[name=description]`, `og:title`/`og:description`, `h1–h3` (30), and links whose host is a known social network (fixed list: Instagram, TikTok, YouTube, X/Twitter, Facebook, LinkedIn, Pinterest, Threads).

Colours merge when their CIE76 ΔE is under 4 (sRGB → Lab, no new dependency: a small function). The script returns plain JSON; Python caps lengths and sizes.

Image and Google-font bytes come from the guard's response cache (the bytes the page already fetched), so capturing adds no extra requests. Candidates are validated with `brand_files` (Decision 6) before anything is written.

### 5. Viewport and timing

430×932 CSS px at DPR 2.5 (1075×2330 screenshot), the existing CLI's phone defaults, mobile user agent. `wait_until="load"`, not `networkidle` (pages with polling never go idle; the budget bounds the rest). No full-page screenshot in the op (the CLI keeps it for b-roll).

### 6. `tools/brand_files.py`: one validator per kind, sniffed by bytes

Kind comes from magic bytes, not the extension (`\x00\x01\x00\x00`/`true`/`OTTO` sfnt, `wOFF`, `wOF2`, PNG, JPEG `FFD8FF`, SVG = XML whose root is `{http://www.w3.org/2000/svg}svg`). Upload extensions only pick the expected family (font vs image).
- **Fonts:** size ≤ 5 MB; `TTFont(path, lazy=False)` then touch `cmap`, `name`, `head`, `hhea`, `hmtx`, `maxp`, `OS/2`, and `glyf` (decompile every glyph) or `CFF `/`CFF2` (decompile every charstring), so a truncated table fails here rather than in the renderer. Requires the best cmap to cover `A–Z a–z 0–9`. Family from name ID 16 → 1, weight from `OS/2.usWeightClass` clamped to 100–900, italic from `fsSelection` bit 0 or `macStyle` bit 1. WOFF/WOFF2 are saved with `flavor=None` as `.ttf` (glyf) or `.otf` (CFF). Plain sfnt files are copied as is after parsing (re-saving could alter hinting).
- **Raster:** size ≤ 20 MB; `Image.open` reads only the header, so width/height are checked against 8000 before `load()`; `Image.MAX_IMAGE_PIXELS` set to 64 M as a second stop and `DecompressionBombWarning` turned into an error. `ImageOps.exif_transpose`, convert to RGBA/RGB, save PNG with no metadata.
- **SVG:** size ≤ 2 MB; `defusedxml.ElementTree.fromstring(forbid_dtd=True, forbid_entities=True, forbid_external=True)`; walk every element: refuse the listed elements, `on*` attributes, `href`/`xlink:href` not `#…` or `data:image/(png|jpeg);base64,…`, `style` attributes and `<style>` text containing `url(` not followed by `#` or containing `@import`. Clean SVGs are rasterized in the same headless browser as `site` (Decision 3) with all network routes aborted: the SVG is loaded as an `<img>` from a data URL (image context: no script, no external loads, a second guarantee) on a transparent page sized to the target, and screenshotted with `omit_background=True`. The browser starts only if there is an SVG to render.

*Alternative for SVG:* CairoSVG (LGPL, needs libcairo on the Mac) or resvg bindings (new native wheel). Rejected: the browser is already present on both platforms and image-context SVG is the most restricted renderer we have.

### 7. `brand check` flow and result

1. List `incoming/` (files only, no recursion; a subdirectory is reported invalid and removed).
2. For each file: validate into a temp dir → move to `fonts/` or `logos/` (stem kept and sanitised to `[A-Za-z0-9._-]`, extension from the stored format), report `replaced` if it overwrote. Always delete the incoming file.
3. If `brand.json` exists, validate shape (rules in the spec; caption keys and ranges: `top` 0–1920, `size`/`emphSize` 20–160, `emphColor` `#RRGGBB` or `white`/`black`, `mode` `phrase`/`word`, `emphCaps` bool, `emphWeight` 100–900, `shade` 0–1).

Result: `{"files": [{name, kind, status, reason?, stored?, replaced?, family?, weight?, style?, width?, height?}], "errors": [...]}`; `error` set (so `ok: false`) only when `errors` is non-empty.

### 8. Dependencies

`fonttools`, `brotli`, `defusedxml` go in the default group: small, pure Python or prebuilt wheels, needed by both the CLI and the image. `urllib3` is already present through `requests`; it becomes a direct dependency because the guard relies on its pinned-connection API.

## Risks / Trade-offs

- [Playwright 1.63 cannot drive Remotion's headless shell version] → task 1.2 verifies on both arches; fallback is Playwright's own headless shell in the image (+~110 MB, measured and recorded).
- [Fulfilling every request from Python slows heavy pages] → budget bounds it; typical marketing pages are 2–6 MB. Measured in the verification task.
- [Sites behind bot protection return a challenge page] → the capture reports what loaded; the caller sees the screenshot. No evasion.
- [Fonts that parse but render badly] → completeness checks catch truncated tables; the pilot task renders a caption still with the validated font and reads it.
- [Validators in the same process as the job runner] → inputs are size-capped before parsing; image size is checked before decode; XML has no DTD/entities. A parser crash fails the job; it cannot run code.

## Migration Plan

Additive: new ops and a new CLI; existing ops, `brand.py` and `site_capture.py`'s CLI are unchanged. Release as `v0.4.0` after the verification task; the hosted runner bumps its pin and adds `site` and `brand` to its allow-list.

## Open Questions

None blocking. The exact grid size and ΔE threshold are tuned in task 2.3 against the test page and one real public page.
