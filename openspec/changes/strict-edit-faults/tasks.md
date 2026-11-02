## 1. Fixtures first (the faults as failing tests)

- [ ] 1.1 Add synthetic fixtures to `tools/tests/` (generated tones/noise, neutral words): a take with a word stretched over 3.7 s of speech, a 0.8 s hole, a "phrase… phrase again" restart, and a "sentence. sentence." anaphora
- [ ] 1.2 Add failing tests for each new or modified scenario in the four spec deltas (they must fail on `main` before the fix)

## 2. Transcription (local-transcription)

- [ ] 2.1 Implausible-word pass in `fill_holes`: detect, re-transcribe the window, replace or list as `untranscribed`, record `replaced`
- [ ] 2.2 Midpoint rule ignores implausible words; `MIN_HOLE` = 0.6
- [ ] 2.3 `mark_restarts(words)` → `restarts` in the JSON; show restarts inline in the packed transcript

## 3. Check (shortform-spec, edit-faults)

- [ ] 3.1 Segment `from`/`to` validation and resolution (D1); timeline shows resolved seconds
- [ ] 3.2 In-word edge is always an error; loud-edge message no longer suggests a lock (D2)
- [ ] 3.3 "Restart kept" and "Untranscribed speech kept" findings with kind tags
- [ ] 3.4 `strict` through `run_job` → `shortform` → `check`/`stills`/`render`; locks and `keep_restart` refused; listed kinds become errors; `stills --strict` returns `renderable: false` on any

- [ ] 3.5 Speech-relative silence for the pause search and edge placement (merge ≤ 50 ms, runs ≥ 60 ms, word cores); dead-air split inside `from`/`to` segments (≥ 0.30 s, removes ≥ 0.08 s) (D13). Tests against the prototype's measured cases
- [ ] 3.6 Loud-edge rule: source time 0 is clean (D14); scene/backdrop dark mismatch is an error (D15)

## 4. Contrast (shortform-spec probe, brand-theme)

- [ ] 4.1 Probe measures contrast over the changed-pixel mask (D5); new warning text; strict → error
- [ ] 4.2 `accentOn(fill)` in `theme.ts`; use it in `Receipt` and every component the grep `colors.accent` finds drawing text or a text border on a fixed fill; `npx tsc --noEmit`
- [ ] 4.3 Contrast matrix test (D7) with the pale- and dark-accent fixture brands; it passes

## 4b. The never-list (edit-faults)

- [ ] 4b.1 Head box in `face_centre.py` and the face step output (footage-prep)
- [ ] 4b.2 `overlay_text.json` text boxes and sizes from the still render (D9); `npx tsc --noEmit`
- [ ] 4b.3 Probe composites over the source frame; contrast thresholds 4.5/3 by text height (D5)
- [ ] 4b.4 Findings: text over the face (D8; `behind` text under the cut-out is exempt), captions on overlay text (D10), text under 28 px
- [ ] 4b.5 Engine placement of floating overlays; `frame` refused in strict (D11)
- [ ] 4b.6 `NEVER_LIST` + `--never-list` + a fixture per item under `tools/tests/fixtures/never/`, including the floating-stat-across-the-face case; a test that every item has its check and fixture (D12)

## 5. Docs and release

- [ ] 5.1 `short-form-pro` SKILL.md: cut with `from`/`to`; locks never excuse a word cut; restarts and untranscribed speech; CLAUDE.md: `--strict`
- [ ] 5.2 Export: the segment `from`/`to` shape is in `overlay_schema.py --export`, if segments are exported; else note it in the spec format docs
- [ ] 5.3 Full test suite green; `npx tsc --noEmit` clean

## 6. Verification

- [ ] 6.1 Pilot under `footage/` (gitignored), using a real take with a known false start and a pale-accent brand:
  - re-transcribe and confirm the false start appears as words and in `restarts`;
  - `check --strict` refuses an edit that keeps it, and one with a locked in-word edge;
  - the word-anchored version passes;
  - `stills --strict` reports no contrast error; read each event still;
  - render the preview: −14 ±1 LUFS, and re-transcribing it shows no repeated phrase or cut word.
