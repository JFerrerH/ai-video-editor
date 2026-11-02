# Design

## Context

`check` already knows everything needed to stop the three faults:
- word times;
- the RMS envelope and its pauses (`_pause_near`);
- each edge's energy;
- the event stills.

But there are three gaps:
- edges are written in seconds by the caller;
- a lock turns an in-word error into a warning (and the message itself suggests a lock);
- the probe counts changed pixels.

The transcription patch exists (`fill_holes`), but two rules defeat it:
- re-transcribed words whose midpoint falls inside an existing word are dropped, so a word Whisper stretched over a false start blocks its own repair;
- holes under 1.5 s are ignored.

## Goals / Non-goals

Goals:
- the three observed faults can't reach a strict render;
- every refusal names its fix;
- no new models.

Non-goals:
- choosing between two takes of a phrase;
- render speed;
- product-side policy (which caller uses strict).

## Decisions

### D1. Word-anchored edges resolve to a pause, else to the quietest point between words

`from` / `to` resolve with the same word lookup as event anchors (`p.word(take, word, after)`). Then:
- `from`: `_pause_near(take, word.start, "in")`, limited to the gap back to the previous word's end;
- `to`: `_pause_near(take, word.end, "out")`, limited to the gap up to the next word's start;
- without a pause in that gap: the minimum-energy 5 ms hop between the two words. It is never past either word, so it can't land inside one.

The resolved seconds replace `from` / `to` before the rest of `load()`, so overlap checks, joins, timeline and render are unchanged. Resolved edges count as refined, which disables the old ±refinement on them.

*Alternative*: keep seconds and only tighten errors. Rejected: the caller still has to guess a number, and every guess costs a round.

### D2. Locks never excuse an in-word edge; strict removes locks entirely

In `_edge_rules`, the `(warnings if d["locked"] else errors)` branch becomes errors always. The loud-edge message stops suggesting `lock_*`. It suggests the pause or the `to`/`from` form instead.

`strict` is threaded `run_job args → shortform cmd → short_spec.check(strict=)`. One function, `_strict_findings(spec, findings)`, does two things:
- it moves the listed warning kinds to errors by a kind tag carried on each finding. Kinds are tags, not message text, so wording can change;
- it adds the lock and `keep_restart` errors.

### D3. Implausible words are repaired by replacement

`fill_holes` gains a pass before the hole pass. Each implausible word goes through `retranscribe(lo, hi)` over `[start − PATCH_PAD, end + PATCH_PAD]`:
- non-hallucinated results replace the word: remove it, insert the new words clipped to its window;
- otherwise the window goes to `untranscribed`.

The implausibility test is `duration > max(1.0, 0.12·letters + 0.4)`, with speech covering ≥ 60% by the envelope. At normal Spanish/English rates (≈ 0.06–0.09 s per letter), real words stay well under the limit.

`MIN_HOLE` drops to 0.6 s, measured: the observed hidden run was 1.56 s split by a 0.6 s pause into two sub-1.5 s runs.

Then the existing `fill_holes` midpoint rule is changed: it only rejects a new word when an existing word *that isn't implausible* covers the midpoint.

### D4. Restarts: conservative marker in transcription, hard refusal in check

Detection runs on the final word list (`mark_restarts(words)`):
- an abandoned end: a trailing `…`/`...`, or a gap ≥ 0.3 s after a word without `.?!`;
- followed within 6 s by a normalised bigram equal to the abandoned phrase's first bigram.

The abandoned phrase is taken back to the previous sentence end or pause ≥ 0.3 s.

False positives matter more than misses here, because a refusal costs a round. Requiring the abandoned-end signal keeps deliberate anaphora out ("I spend X on food. I spend Y on rent." ends a sentence first). Misses are still caught downstream by the product's preview QA.

`check` reads `restarts` from the transcript JSON. A segment whose `[in, out]` contains both `abandoned` and `again` is an error. The suggested fix is "start at {again}" when the segment begins before the abandoned phrase's end; otherwise "split it before {abandoned.from}". Old transcripts without `restarts` simply have none.

### D5. Contrast from the probe's two renders, over the footage

The probe already renders the event with and without text, alone on a transparent canvas. Both renders are now alpha-composited over the conformed source frame at the event's still time (one `ffmpeg` frame grab per event, at the probe's 0.5 scale), so floating text is judged against the wall or face really behind it. Over the changed-pixel mask:
- median relative luminance of each render;
- `ratio = (L1 + 0.05)/(L2 + 0.05)`, the lighter over the darker.

This measures what is drawn, in any component and any brand, with no per-component metadata. The mask is dilated by 0 px, so anti-aliased edges count in both.

Thresholds: 4.5:1 for text under 48 px tall, 3:1 for larger text (WCAG normal and large text). The text height comes from D9.

### D8. Head box and face findings

`face_centre.py` already computes the head band (the top 30% of the person matte) to get its centroid. It now also returns the band's box, as the median per side over the sampled frames.

`check` scales the box into output pixels through the same crop and zoom the segment uses: the per-frame zoom at the still time, the conservative maximum over the event. Then it grows the box by 6% of the width on each side.

Text boxes come from D9. Any intersection is a finding.

### D9. Text element boxes and sizes from the still render

The overlay still render already runs Remotion; the CLI's `remotion still` drops browser logs, so measured stills go through `tools/motion/scripts/stills.mjs` (one bundle, many stills, logs captured). A `measure` mode writes `overlay_text.json`: for every DOM element that renders a schema text field, its bounding box and computed font size × scale, using `getBoundingClientRect` and `getComputedStyle` in a `useEffect`, collected by `delayRender`. The schema's text annotations already name which props are text.

This file feeds three checks:
- face intersection (D8);
- captions vs text (D10);
- minimum size (28 px).

It also gives the contrast thresholds their text height.

### D10. Captions move off any overlay text

`caption_event()` already moves captions off full-layout content boxes. It now uses the union of text boxes of every overlay on screen at that time, with the same below-then-above rule. When neither fits, that is a finding.

### D11. Engine placement replaces `frame`

For a floating event without `frame`:
- band = `[SAFE.top, head_top − margin]`;
- the scale is `min(1, band_height / content_height, safe_width / content_width)`, with the content box measured at scale 1 in the probe pass;
- the event is centred horizontally;
- the result is written as the event's effective `frame` before render.

If the scale would take any text element below 28 px, `check` fails with the fix. With no head box (no person), the band is the upper half of the frame.

Full-layout events are untouched. Strict refuses `frame`, so placement can't be overridden in hosted use.

*Alternative*: keep `frame` and add checks only. Rejected: the caller would still guess, and each guess costs a 7-minute round.

### D12. The never-list is code, not prose

`NEVER_LIST` in `short_spec.py` holds each item as `(number, text, check kind)`. `--never-list` prints it. A test asserts that every item has its check kind in `_strict_findings` and a fixture under `tools/tests/fixtures/never/` that triggers it.

Brand notes and guides can repeat the list. The check is what holds.

### D6. `accentOn(fill)` in theme.ts

The helper:
- computes the contrast of `colors.accent` on `fill`;
- if under 3:1, steps lightness down in HSL (same hue and saturation) in 5% steps until ≥ 3:1;
- otherwise falls back to `ink`.

Components drawing accent text or text borders on a fixed fill call it (`Receipt` stamp first). The grep in tasks finds the rest.

`textOn` stays for text *on* an accent fill.

### D7. Contrast matrix test

A Node test script under `tools/motion/` renders one still per registry entry per fixture brand at 540x960 (`--scale=0.5`), using each schema's example props. It then runs the D5 probe through the Python tool on each pair. As built: a Python harness (`tools/tests/contrast_matrix.py`, `npm run test:contrast`) renders through `scripts/stills.mjs` and runs the probe's own `low_contrast`; scenes without a dark tone of their own are drawn on the light backdrop only.

It is slow (about 40 entries × 2 brands), so it runs on demand (`npm run test:contrast`) and in the release check, not on every unit test run.

### D13. Silence relative to the take's speech, and dead air removed

All of this was measured in the 2026-11-02 compiler prototype on 6 held-out takes. Its output silence matched the user's own approved local edits: cea 3.0 % vs 3.4 %, launch 12.2 % vs 12.4 %, habilidades 17.6 % vs 17.3 %.
- **Threshold.** A floor-only threshold (floor + 18) kept breaths in a quiet room. A speech-relative one (`max(floor + 9, speech − 25)`) did not.
- **Merging.** Room-noise flicker split real pauses into runs too short to count, so runs at most 50 ms apart are merged.
- **Early stamps.** Whisper stamps a word to the end of the pause after it, so the search starts at the word's core.
- **Splits.** A split that removes under 0.08 s showed up as a zoom jump mid-word, so it is skipped.

Reference: `openspec/changes/edit-plans/prototype/compile_plan.py` (`env`, `gap_between`, `build_segments`).

Found in implementation: on quiet-floor takes (−77 dB, voice isolation) the silence threshold sits 30 dB over the floor, so the loud-edge check measures against the same threshold, not the floor alone; a cut also moves on past a click merged into its pause; an edge in the silence of an early stamp isn't inside the word. Measured on the prototype's three takes: output silence 18.0 / 22.9 / 16.6 % vs the prototype's 18.4 / 23.8 / 16.6 %, no errors.

### D14. The media start is a clean edge

A take recorded straight into speech starts loud at 0.0 by definition. The prototype's QA flagged it every time, and nothing can be cut before it.

### D15. Scene and backdrop agree

In the prototype, `bg: "dark"` on a scene without `dark: true` on the event drew white text on the cream backdrop. The engine can see both props, so it refuses the mismatch instead of rendering it.

## Risks / Trade-offs

- **Old locked edits fail.** Mitigation: the error states the fix, and `from`/`to` makes it a one-line change.
- **The restart marker misses some stumbles** (no ellipsis, no pause). Accepted: the product's preview QA re-transcribes the output and catches repeats; strict refusal of missed ones isn't possible without semantics.
- **The re-transcribe pass adds time**, about 1–3 s per implausible word on CPU. Usually 0–3 per take.
- **Contrast medians can be fooled** by text over a busy photo. The overlays here draw on solid fills, and footage-backed text (captions) isn't probed.

## Migration

The engine is tagged `v0.7.0`. Callers pin it. The product passes `strict: true` and teaches `from`/`to`.
