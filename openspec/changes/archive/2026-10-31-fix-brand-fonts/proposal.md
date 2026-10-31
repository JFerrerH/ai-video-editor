# Proposal

## Why

A hosted caller saved a brand kit whose `fontFiles` weights are JSON numbers (`"weight": 400`). The kit check
accepts numbers, `tools/brand.py` passes them to the overlay unchanged, and `useBrandFonts` runs
`(f.weight ?? "400").split(" ")`. The overlay crashes on its first frame, so every `shortform stills` and render
with that kit fails. When the job failed, `run_job.py` kept only the first line of the error (the `npx remotion …`
command), so the cause reached neither the logs nor the caller.

Reproduced in the `v0.4.0` Linux image with a three-font kit (two variable fonts, one static, no `serif` role)
built through `load_brand`, then `npx remotion still Overlay`:

- Numeric weights: `TypeError (f.weight ?? "400").split is not a function` at `src/Overlay.tsx:118`, exit 1.
- The same weights as strings: renders. But the headline, which uses `fonts.serif`, is drawn in a fallback serif,
  because the kit sets no `serif` and the neutral one is Georgia.
- `brand: none`: renders, but the headline, the sans tagline **and** the mono URL are all drawn in the same
  Times-metric serif. A still drawn with `Georgia` is byte-identical to one drawn with `Liberation Serif`. Chromium
  doesn't use fontconfig's substitutes (`fc-match Georgia` says Noto Serif) and falls back to its default font
  instead. CLAUDE.md says unbranded Linux renders use Noto; they don't.

Variable fonts can only be given one weight, so bold text in a variable brand face is synthesised instead of using
the font's own weight axis.

## What Changes

- A font file's `weight` reaches the overlay as a string whether the kit gives a number or a string, and the overlay
  accepts either form. A kit that passed the check renders.
- `brand check` reports a variable font's weight as its range (`"100 800"`). The kit check **warns** about a
  `fontFiles` entry whose weight or style the file can't provide, naming the entry and what the file provides. It
  stays a warning so that local kits that render today keep rendering; a hosted caller that takes kits from end
  users refuses the mismatch on its own side, when the kit is saved.
- A font role the kit leaves unset (`serif`, `sans`, `mono`) uses the kit's `sans`, then its first font file's
  family. The neutral face is used only when the kit names no font at all.
- The neutral faces become fallback lists that end in fonts the Linux image ships (Noto Serif / Noto Sans /
  Noto Sans Mono). The Mac look doesn't change.
- A failed job's `error` is the most specific line of the failure (for example the `TypeError` or
  `Font did not load: …`), with paths under the engine root made relative. The full failure text goes to stderr.
  A font that doesn't load is reported with its family, weight, style and file.

Out of scope:
- Loading every brand font in the render browser during `brand check` (the font parse is enough for this bug).
- Font subsetting, conversion or repair; a new neutral look; the caption engine `ass` (it doesn't use the theme's
  fonts).
- Other overlay-still failures unrelated to fonts. This change only makes their cause visible.

Skills and workflows: `short-form-pro` and `motion-graphics` (both render through the brand theme), and the
headless runner used by hosted callers. `video-use` is unaffected. No new models or dependencies; the Dockerfile
needs no new font package (`fc-match "Noto Sans Mono"` already resolves with `fonts-noto-core`).

## Capabilities

### New Capabilities
- `brand-theme`: how a brand kit (or no brand) becomes the render theme: font weight forms, font roles, the neutral
  faces, and what happens when a brand font doesn't load.

### Modified Capabilities
- `brand-validation`: a variable font is reported with its weight range, and the check warns (in a new `warnings`
  list) when a kit's `fontFiles` entry claims a weight or style its file doesn't provide.
- `headless-jobs`: a failed job's `error` carries the specific cause, without engine paths, and the full failure
  goes to stderr.

## Impact

- `tools/brand.py` (weights as strings, role fallback, `NEUTRAL` lists), `tools/motion/src/theme.ts`
  (`defaultBrand` lists, `FontFile.weight` type), `tools/motion/src/Overlay.tsx` (`useBrandFonts`),
  `tools/brand_files.py` (weight range in font reports, entry-vs-file check), `tools/run_job.py` (error line,
  stderr), tests in `tools/tests/`.
- `.claude/skills/short-form-pro/SKILL.md`, `.claude/skills/motion-graphics/SKILL.md`, `brands/_template/`,
  `tools/motion/README.md` and CLAUDE.md ("Differences from the Mac").
- Kits: those that set every role and use string weights render exactly as before. Kits missing a role switch that
  role from a neutral face to their own. Unbranded Linux renders switch from Liberation Serif to Noto.
- Hosted callers: an integer weight renders. `brand check` results report a range string for variable fonts and
  carry a `warnings` list; `ok` is unchanged by warnings, so no existing kit stops checking or rendering.
