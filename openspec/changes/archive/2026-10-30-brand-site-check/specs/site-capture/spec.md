# Spec Delta

## Purpose

Capture one web page the user owns or may use as measured brand facts (a phone screenshot, colours, fonts, image candidates and page text) that someone can build a brand kit from, without the capture being able to reach private networks or bring untrusted files into a kit unvalidated.

## ADDED Requirements

### Requirement: One page, measured facts

The `site` op SHALL load the one page at `url` in a phone-sized headless browser and write into `site/` in the project:
- `viewport.png`: the phone viewport, at least 1075 px wide
- `capture.json`: the final URL, colours, fonts, image candidates, page text and network counts

It SHALL return the same facts (without image bytes) in the result and list every file it wrote in `outputs`. It SHALL NOT describe, summarise or judge the page; every value is measured from the page.

#### Scenario: Local test site

- **WHEN** `site` runs on a local test page served over http with a dark header, a white body, a red button, one `@font-face` font, a favicon and an `og:image`
- **THEN** `site/viewport.png` and `site/capture.json` exist, `colors` lists the white, the dark header colour and the red with area shares that sum to at most 1, `fonts` lists the `@font-face` family with source `font-face`, and `images` lists the favicon and the `og:image`

#### Scenario: Output fields

- **WHEN** a `site` job succeeds
- **THEN** the result has `ok: true`, `final_url`, `title`, `colors`, `fonts`, `images` and `blocked` (a count), and `outputs` includes `site/viewport.png` and `site/capture.json`

### Requirement: Colours by on-screen area

`colors` SHALL rank distinct `#RRGGBB` colours by the share of the viewport they cover, and SHALL tag each with its roles: `background`, `text` (weighted by rendered text area) and `interactive` (buttons and links). Near-identical colours SHALL merge. At most 16 colours SHALL be listed.

#### Scenario: Dominant background first

- **WHEN** a page's body background is `#FFFFFF` over most of the viewport and its header is `#101820`
- **THEN** `#FFFFFF` is listed before `#101820`, both with role `background`

### Requirement: Fonts with their source

`fonts` SHALL list each font family the page renders text with, its use (`headings`, `body`, `interactive`), its source (`font-face` with the file URL, `google` with the family, or `system` for local and generic families) and the weights in use. For `google` families, the op SHALL save the font files the page loaded into `site/fonts/` and name them. For other web fonts it SHALL list the URL and SHALL NOT save the file.

#### Scenario: Google font saved

- **WHEN** the page loads a family from the Google Fonts CSS endpoint
- **THEN** that family is listed with source `google` and its files are in `site/fonts/`

#### Scenario: Other web font listed only

- **WHEN** the page loads a font from its own `@font-face` URL
- **THEN** the family is listed with source `font-face` and the URL, and no file for it is written

### Requirement: Image candidates validated

`images` SHALL list at most 12 candidates in this order: page icons, `og:image`, then images and inline SVGs in the page header, each with its kind, source URL (or `inline`) and size. Each candidate SHALL pass the same validation as brand files: a candidate that fails is listed with its reason and no file is kept. A valid candidate SHALL be saved as `site/images/<nn>.png` (long side ≤ 1024 px) plus its validated original as `site/images/<nn>.orig.<ext>`.

#### Scenario: SVG logo with a script

- **WHEN** the header's inline SVG logo contains a `<script>` element
- **THEN** the candidate is listed with status `invalid` and a reason naming the script, and no file for it exists under `site/images/`

### Requirement: Page text as data

`capture.json` SHALL hold the page title, meta description, up to 30 headings (h1–h3) and social profile links. Each text field SHALL be capped at 300 characters and `capture.json` at 64 KB. Text SHALL be stored as found, without interpretation.

#### Scenario: Long page

- **WHEN** a page has 200 headings and a 5,000-character description
- **THEN** `capture.json` lists 30 headings, the description is cut to 300 characters, and the file is under 64 KB

### Requirement: Guarded network

Every request the page makes SHALL go through the engine's guard, with no other network path. The guard SHALL refuse non-http(s) schemes, ports other than 80/443, credentials in the URL, and hosts with any non-public address (loopback, private, link-local incl. `169.254.169.254`, CGNAT, multicast, reserved, IPv6 ULA). A refused main document SHALL reject the job (exit 2) with an `error` naming the reason. A refused sub-resource SHALL be skipped and counted in `blocked`.

#### Scenario: Metadata address

- **WHEN** `url` is `http://169.254.169.254/latest/meta-data/`
- **THEN** the job exits 2 with an error naming a link-local address, and a listener on that address (simulated in the test) receives no connection

### Requirement: Pinned connections and redirects

The guard SHALL connect only to the address it checked, keeping TLS verification for the requested name, and SHALL re-check every redirect hop (at most 5). No request SHALL reach a refused address.

#### Scenario: Rebinding name

- **WHEN** a test resolver answers a public address for the check and a private one afterwards
- **THEN** the only connection made goes to the public address

#### Scenario: Redirect to a private address

- **WHEN** the page URL answers with a redirect to `http://10.0.0.5/`
- **THEN** the job exits 2 with an error naming the redirect, and a listener standing in for `10.0.0.5` receives no connection

#### Scenario: Name that resolves to loopback

- **WHEN** `url` names a host that resolves to `127.0.0.1`
- **THEN** the job is refused before any connection

#### Scenario: Private sub-resource

- **WHEN** an allowed page includes an image from a host that resolves to a private address
- **THEN** the capture succeeds, the image is not fetched, and `blocked` is at least 1

### Requirement: Capture budget

A capture SHALL stop loading after 30 s of wall time or 20 MB of response bodies, whichever comes first, and SHALL still write what it has measured, marking `capture.json` with `truncated: true`. Downloads, service workers and WebSocket connections SHALL be blocked.

#### Scenario: Heavy page

- **WHEN** a test page references 40 MB of images
- **THEN** no more than 20 MB of bodies are fetched, the job succeeds with `truncated: true`, and it finishes within 40 s
