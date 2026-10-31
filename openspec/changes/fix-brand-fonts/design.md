# Design

## Context

See proposal.md (Why) for the failure and its reproduction. How a font weight travels today:

| Layer | Weight |
|---|---|
| Kit check (`tools/brand_files.py` `check_kit`) | `str` or `int`, each part 100–900; not compared with the file |
| Font report (`validate_font`) | `usWeightClass` only, even for a variable font |
| `tools/brand.py` `load_brand` → theme | copied unchanged |
| `FontFile` in `theme.ts` | `weight?: string`, not enforced (props are JSON) |
| `useBrandFonts` in `Overlay.tsx` | `(f.weight ?? "400").split(" ")` → `TypeError` on a number |

Font roles: `load_brand` merges kit `fonts` over `NEUTRAL["fonts"]` (`Georgia` / `Helvetica Neue` / `Menlo`), and
`defaultBrand` in `theme.ts` mirrors it. Scenes set `fontFamily: fonts.<role>` with a single name and no generic
fallback, so on Linux, where none of the three exists, Chromium draws its default font (Liberation Serif, measured
byte-identical). `Headline.tsx` measures text with `measureText({fontFamily: fonts.sans, …})`.

Errors: `shortform.run` (also used by `storyboard.py`) raises `SystemExit("FAILED: <cmd>\n<last 4000 chars of
stderr>")`. `run_job.py` turns it into `error` with `_one_line`, which keeps the first line (the command) and drops
the rest; the rest is never printed.

## Goals / Non-Goals

**Goals:**
- The layers agree on one weight form at the Remotion boundary, and the overlay doesn't depend on every caller
  getting the type right.
- A kit that claims a weight or style its file doesn't have is flagged, without breaking kits that render today.
- No role ever reaches the browser's default font.

**Non-Goals:**
- Changing `shortform.run`'s message format or the ASS caption engine.
- Running the kit check from `shortform check` or at render time: it stays in `brand check`, as today.

## Decisions

### D1. Normalise weights at both ends
`load_brand` converts each `fontFiles` weight with `str()` (`400` → `"400"`, `"100 800"` unchanged). `useBrandFonts`
uses `String(f.weight ?? "400")` before splitting. Both ends, because props are untyped JSON at runtime and
`Story`/sheet compositions can receive a hand-written theme. `FontFile.weight` stays `string` in TypeScript.
*Alternative:* refuse numbers in the kit check. Rejected: numbers are valid JSON for a weight, hosted callers already
store them, and refusing would break kits that render fine once normalised.

### D2. Weight ranges from the file
`validate_font` reads the `fvar` table. If it has a `wght` axis, the report's `weight` is `"<min> <max>"`
(clamped to 100–900); otherwise `usWeightClass` as today. `check_kit` validates each entry's file (already parsed
during the check) and compares:
- range on a static font, or not inside the variable range → warning;
- single weight on a variable font outside its range, or on a static font ≠ `usWeightClass` → warning;
- `style: italic` on a face that isn't italic (`fsSelection` bit 0 / `macStyle` bit 1, or an `ital`/`slnt` axis) → warning;
- no weight → nothing (the renderer defaults to 400; a variable font is then loaded at 400, unchanged behaviour).
Warnings name the entry field and what the file provides (`fontFiles[1].weight: Brand-Light.ttf provides weight 300,
not "100 900"`) and go in a new `warnings` list in the `brand check` result (and the CLI output); `ok` and `errors`
are unchanged. The facts come from the same reader as the report, so they can't disagree.
*Why a warning, not an error:* a mismatch is harmless to the render (the browser clamps the weight or synthesises
bold), and local kits rely on that today: of the kits checked while writing this, one gave a variable font a wider
range than its subset file has and one gave a static face a range. Refusing would stop them rendering until edited.
A hosted caller that accepts kits from end users enforces the match itself when the kit is saved, where the user
can act on the message.
*Alternative:* fill a missing variable weight with the range in `load_brand`. Deferred: it changes how existing kits
render (bold would switch from synthesised to real), so callers opt in by writing the range.

### D3. Role fallback inside the kit
`load_brand`: for each role, `kit.fonts[role] or kit.fonts["sans"] or first_file_family or NEUTRAL[role]`, where
`first_file_family` is `fontFiles[0].family`. `brand: none` is unchanged apart from D4.
*Alternative:* require all three roles in the kit check. Rejected: many brands have one or two faces, and a required
field invites the editor to invent a third that isn't the brand's.

### D4. Neutral faces as CSS lists
`NEUTRAL["fonts"]` and `defaultBrand.fonts` become CSS family lists:
`Georgia, "Noto Serif", serif` / `"Helvetica Neue", "Noto Sans", sans-serif` / `Menlo, "Noto Sans Mono", monospace`.
Every scene already passes `fonts.<role>` to `fontFamily`, which accepts a list, so no scene changes. `measureText`
builds a canvas font string, which also accepts a list. On the Mac the first face exists, so nothing changes;
on Linux Noto is used. `fonts-noto-core` already provides all three Noto families (`fc-match` checked in the
`v0.4.0` image), so the Dockerfile doesn't change. A kit role is used as given: a kit family name with spaces works
unquoted in `fontFamily`.
*Alternative:* swap the neutral faces for Noto everywhere. Rejected: it changes the Mac look for no reason.

### D5. Keep the cause, drop the command
`run_job.py` `SystemExit` handler: write the full message to stderr, then pick `error` with a new `_cause_line`:
the last line matching `Error|error:|Font did not load|Exception` (for example `TypeError …`), else the first line;
replace the engine root prefix (`REPO` with a trailing slash) with nothing; cap at 500 characters. `_one_line` stays
for single-line messages and `JobError`. This covers `storyboard.py` too, because it uses `shortform.run` and fails
through the same handler. `useBrandFonts` builds its error as
`Font did not load: <style> <weight> "<family>" (<file>)`, using the entry's `url` basename, and also uses it when
`loadFont` itself rejects.
*Alternative:* put the whole stderr in `error`. Rejected: `error` is one line by contract and is shown to end users;
the full text belongs in stderr, where callers keep logs.

## Risks / Trade-offs

- [A warning is easy to ignore, so a local kit keeps a faked bold] → The warning names the fix (the range or weight
  the file provides), and the skills tell the editor to resolve brand warnings before a final render.
- [`_cause_line` picks a misleading line in some tool's output] → The full message is on stderr; the pattern list is
  small and covered by tests with real Remotion and ffmpeg failure text.
- [The Mac look changes] → D4 keeps the Mac faces first; a Mac still before and after is compared byte-for-byte.

## Migration Plan

Ship as a minor tag (`v0.5.0`). Hosted callers bump their pin. Rollback: re-pin `v0.4.0`; no data format changes
apart from the weight range in `brand check` reports, which old callers would read as an unknown string.
