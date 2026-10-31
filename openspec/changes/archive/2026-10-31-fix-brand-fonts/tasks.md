# Tasks

## 1. Test fixtures

- [x] 1.1 Add fixture fonts to `tools/tests/fixtures/fonts/`: one OFL variable sans with a weight axis, one OFL static light face, one OFL variable mono, each with its `OFL.txt`; plus a `make_font(..., wght=(min, max))` option in the test helpers for synthetic variable fonts. Verify: `fc-scan` / fontTools reads each fixture; the licence files are present.

## 2. Weights render in any accepted form (D1)

- [x] 2.1 `load_brand` writes every `fontFiles` weight as a string; `useBrandFonts` uses `String(f.weight ?? "400")`. Verify: a `load_brand` unit test with `400` and a missing weight → `"400"` and absent; `npx tsc --noEmit` in `tools/motion`; `npx remotion still Overlay` with a numeric-weight kit built from the fixtures renders (exit 0) on the Mac and in the Docker image.

## 3. Errors keep their cause (D5)

- [x] 3.1 `run_job.py`: the `SystemExit` handler writes the full message to stderr and sets `error` with `_cause_line` (last error line, else first; engine root made relative; ≤ 500 chars). Verify: `tools/tests/test_run_job.py` cases with a captured Remotion `TypeError` output, an ffmpeg failure output, a single-line message, and a line holding an absolute engine path.
- [x] 3.2 `useBrandFonts` reports `Font did not load: <style> <weight> "<family>" (<file>)`, also when `loadFont` rejects. Verify: a still with a kit whose font file is replaced by random bytes fails, and the job's `error` contains the family, weight, style and file name.

## 4. Weight ranges and the entry-vs-file check (D2)

- [x] 4.1 `validate_font` reports a variable font's weight as `"<min> <max>"`. Verify: tests for a synthetic variable font, the fixture variable fonts and an unchanged static report; update `tools/brand_files.py` module docstring.
- [x] 4.2 `check_kit` compares each `fontFiles` entry with its file (range, single weight, italic) and returns mismatches as `warnings` (in `check_dir`'s result, the `brand` op result and `tools/brand_check.py` output); `ok` ignores them. Verify: tests for every scenario in `specs/brand-validation/spec.md` "Font entries that don't match their files are warned about"; `brands/_template/` gives `warnings: []`; every local kit under `brands/` still checks `ok: true`.

## 5. Font roles and neutral faces (D3, D4)

- [x] 5.1 `load_brand` falls back per role to kit `sans`, then the first font file's family, then neutral. Verify: tests for sans+mono only, font files only, all roles set, and `brand: none`.
- [x] 5.2 `NEUTRAL["fonts"]` and `defaultBrand.fonts` become the CSS lists in D4 (kept in sync, with a test that compares them). Verify: in the Docker image, an unbranded `EndCard` still equals the same still with roles forced to Noto and differs from one forced to `Liberation Serif`; on the Mac, the unbranded still is byte-identical to one rendered at `v0.4.0`; `Headline` text measures without errors (`npx tsc --noEmit`).

## 6. Docs

- [x] 6.1 Add to the brand steps of both skills: resolve `brand check` warnings (set the weight or range the file provides) before a final render. Update CLAUDE.md "Differences from the Mac" (unbranded Linux renders use Noto; why), `.claude/skills/short-form-pro/SKILL.md` and `.claude/skills/motion-graphics/SKILL.md` (weight forms, variable ranges, role fallback), `brands/_template/` comments if any, and `tools/motion/README.md`. Verify: each names the behaviour as shipped; `grep -rn "Noto Serif/Sans on Linux"` finds no stale claim.

## 7. Verification

- [x] 7.1 `--self-check` and all `tools/tests` pass on the Mac and in a fresh Docker image build.
- [x] 7.2 Pilot under `footage/` (gitignored) with a fixture brand kit (numeric weights, two variable fonts, no `serif`): `shortform check`, `stills` and a 720p preview render through `tools/run_job.py` in the Docker image. Verify by reading the stills: the headline and end card use the kit's sans, mono text uses the kit's mono, and an unbranded copy shows Noto; loudness of the preview matches the unbranded one (±0.5 LU) since audio is untouched.

## Workflow follow-up

- Merge, tag `v0.5.0`, and let hosted callers bump their pin.
- Separate fix (found in the pilot): `Project.stage_overlay` keeps a staged public file whose mtime is newer than the source even when its bytes differ (same file name, different kit); compare size/hash instead.
- `/opsx:verify`, then `/opsx:archive` once the tag is out.
