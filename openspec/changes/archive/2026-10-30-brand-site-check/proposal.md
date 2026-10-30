# Proposal

## Why

A brand kit today is built by hand: someone reads the brand's website, picks colours and fonts, and drops font files into `brands/<slug>/fonts/`. Nothing checks those files. That is fine on one trusted Mac. It is not fine for a hosted runner where kits are built from a website the user names and from files strangers upload: the capture must not become a way to reach private addresses, and a font, image or SVG must be proven harmless and usable before any render loads it.

The engine already owns Playwright, brand loading and the validated job layer (`tools/run_job.py`), so both steps belong here as two new data-only ops, released as `v0.4.0`.

## What Changes

- **New op `site`** (`url` → `site/` in the project). Loads one page in a phone-sized headless browser and writes measured facts, never judgments:
  - `site/viewport.png` (phone viewport screenshot)
  - `site/capture.json`: colours ranked by on-screen area (backgrounds, text, buttons/links), font families with where they come from (`@font-face` URL, Google Fonts, system/generic) and where they are used, image and logo candidates (icons, `og:image`, header images and inline SVGs), title, description, headings and social links. Every text field is length-capped and the file is size-capped.
  - `site/images/`: up to 12 candidates, each passed through the brand-file validators and stored as a PNG preview, plus the validated original
  - `site/fonts/`: the font files of Google Fonts families the page uses (OFL-licensed). Other web fonts are listed, not downloaded.
  - **Network guard.** The browser makes no request on its own. Every request is checked and fetched by the engine: http/https only, ports 80/443, no credentials in the URL, the host resolved and every address checked against private, loopback, link-local (incl. `169.254.169.254`), CGNAT, multicast and IPv6 ULA ranges, the connection pinned to the checked address, and each redirect hop re-checked. The page has a 30 s and 20 MB budget; downloads, service workers and WebSockets are blocked.
- **New op `brand`, `cmd=check`** (a brand directory inside the project, default `brand/`). Validates every file in `<dir>/incoming/`:
  - fonts (TTF/OTF/WOFF/WOFF2, ≤ 5 MB) must parse with fontTools; they are stored as TTF/OTF in `<dir>/fonts/` and reported with family, weight and style
  - raster images (PNG/JPEG, ≤ 20 MB, ≤ 8000 px a side) must decode with Pillow; they are re-encoded to PNG in `<dir>/logos/`
  - SVGs are parsed with defusedxml and rejected on scripts, event handlers, `foreignObject` or any external reference; clean SVGs are rasterized to PNG in `<dir>/logos/`
  - invalid files are deleted and reported with a reason. Nothing from a rejected file is kept.
  - `<dir>/brand.json`, if present, is checked for shape (colour roles as `#RRGGBB`, font roles, `fontFiles` naming validated fonts, known caption keys and ranges); errors name the field.
- **CLI `tools/brand_check.py <dir>`** runs the same check on any kit, e.g. `brands/<slug>/`, so local kits get the same validation.
- **Self-check** gains a `capture browser` item that actually launches the browser `site` uses.
- CLAUDE.md: the "New brand" bullet and the routing table mention `site` and `brand_check.py`; the "Linux / Docker" op list adds both ops.

## Out of scope

- Crawling more than one page, logging in, or capturing pages behind consent walls beyond what loads.
- Downloading non-Google web fonts (licences vary; the user supplies licensed files).
- Writing `brand.json` or `brand.md` from the capture. Choosing colours, fonts and taste stays with whoever builds the kit.
- Detecting which candidate is "the" logo. Candidates are listed with where they came from; someone chooses.
- Animated or video logos, colour profiles beyond sRGB conversion, variable-font instancing.
- The hosted service (accounts, storage, which files reach `incoming/`). That lives outside this repo.

## Capabilities

### New Capabilities
- `site-capture`: guarded capture of one web page into measured brand facts (screenshot, colours, fonts, images, text) for building a kit.
- `brand-validation`: validating brand files (fonts, raster images, SVGs) and `brand.json` shape before any render can use them.

### Modified Capabilities
- `headless-jobs`: the fixed op list adds `site` and `brand` (`check`); both report their outputs and measured fields in the result.
- `engine-container`: the self-check reports the capture browser.

## Impact

- **Code:** new `tools/site_guard.py` (address checks and pinned fetch), `tools/brand_files.py` (font, raster and SVG validators, `brand.json` shape), `tools/brand_check.py` (CLI); `tools/site_capture.py` gains the guarded `capture_facts()` used by the op (its existing CLI keeps working for trusted local b-roll captures); `tools/run_job.py` (two ops, one self-check item).
- **Skills and docs:** CLAUDE.md (new-brand bullet, routing, Linux/Docker op list). `short-form-pro` and `motion-graphics` are unchanged; `brands/_template/brand.md` gets one line saying to run the check after adding files. `video-use` is unaffected.
- **Dependencies (default group, so the Docker image gets them):** `fonttools` (MIT), `brotli` (MIT, needed for WOFF2), `defusedxml` (PSF-2.0). Pure-Python or small wheels, about 10 MB on disk, no models, negligible RAM. No new browser: `site` and SVG rasterizing reuse the Chrome Headless Shell Remotion already installs (system Chrome on the Mac).
- **Speed (32 GB M-series Mac, estimate):** `site` 5–15 s for a typical marketing page (bounded at 30 s); `brand check` under 1 s for a few fonts and PNGs, plus about 1 s browser start when any SVG is present.
- **Release:** tag `v0.4.0` once the tasks pass.
