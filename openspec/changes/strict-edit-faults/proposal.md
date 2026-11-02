# Proposal

## Why

A hosted pilot short passed `check` and rendered a preview with three faults a viewer notices at once:
- two cuts inside words: the edges were locked, which turns the error into a warning;
- a kept false start: Whisper had folded "phrase A… phrase A again" into one 3.7 s "word", the gap patch threw away the re-transcribed words because they fell inside that word, and the hole was too short to be reported;
- a pale accent stamp on a white card: the legibility probe counts changed pixels, not contrast.

Each fault has a way through today. The engine must make these faults impossible or blocking, and must not just describe them.

## What Changes

- **Cuts by words.** A segment can be given as `from` / `to` word anchors (`{"word", "after"}`, as in event anchors) instead of `in` / `out` seconds. The engine places each edge in the pause on the outward side of that word. Where there is no pause, it uses the quietest point between the two words. Seconds stay accepted.
- **No edge inside a word, ever.** An edge inside a transcript word is an error, locked or not. A lock may still cut on sound *between* words (music, a breath).
- **Strict mode** for callers that run untrusted edits (`strict: true` job arg, `--strict` on the CLI):
  - `lock_in`, `lock_out` and `keep_restart` are errors;
  - warnings that describe a viewer-visible fault become errors: loud edges, untranscribed speech kept, low-contrast text.
  - Local use without the flag behaves as described above.
- **Transcripts that don't hide speech:**
  - **Implausible words.** A word longer than its letters allow (`max(1.0, 0.12 s × letters + 0.4)`) is re-transcribed in its own window, and the result *replaces* that word. Today the result is discarded.
  - **Smaller holes.** Uncovered speech holes down to 0.6 s are re-transcribed (today 1.5 s).
  - **Untranscribed speech kept.** Speech still without words stays in `untranscribed`. `check` reports a segment that keeps an untranscribed stretch: a warning normally, an error in strict mode.
- **Restarts are marked and refused.**
  - **Detection.** Transcription marks a likely false start: an abandoned phrase (ellipsis, or a trailing word followed by a ≥ 0.3 s pause), followed within 6 s by the same opening ≥ 2 words. It is written as `restarts: [{"abandoned": [a, b], "again": c}]` and shown in the packed transcript.
  - **Check.** `check` refuses a segment that plays both the abandoned phrase and its restart. The error names the cut that removes it. `keep_restart: true` on the segment opts out in local use only.
- **Contrast, measured.**
  - **The probe.** The legibility probe measures the WCAG contrast between text pixels and the same pixels with the text emptied. It warns under 3:1, and in strict mode that is an error.
  - **Accent as text.** Components that draw the brand accent as text or as a text border on a fixed fill use one theme helper, `accentOn(fill)`. When the accent is too close to the fill, it returns a darker accent derived from the brand (same hue) or `ink`. The known case is the receipt total stamp.
  - **Render test.** A test renders every overlay and scene with a pale-accent and a dark-accent fixture brand and runs the probe on each.
- **Contrast against what's really behind the text.** The probe composites the event over the source frame at its still time and measures each text element against the pixels behind it, footage included. Today it draws the event alone on a transparent canvas. Bare text floating over a bright wall is measured as what it is.
- **The never-list, each item a check.** A second hosted preview showed the anti-pattern this list is named after: a stat floating with no card, its big white number across the speaker's face, a pale kicker and suffix on a light wall, and the captions stacked under it. Every item below has a check that is an error in strict mode, and a fixture that reproduces it:
  1. **Text over the face.** An overlay text box that intersects the speaker's head box (from the face step, plus a 6% margin).
  2. **Unreadable text over footage**: composite contrast under 4.5:1 for text under 48 px tall, or under 3:1 for larger text.
  3. **Captions stacked on overlay text**: the caption box intersects any overlay text box while both are on screen. Today this is only checked for full-screen scenes, and only warns.
  4. **Text too small**: a rendered text element under 28 px tall at 1080 wide (the tiny tracked kicker).
  5. **Cut inside a word**, locked or not.
  6. **False start kept**, or untranscribed speech kept.
  7. **Same source audio twice** (exists).
  8. **Graphic that echoes the words being spoken** (exists as ECHO; becomes an error in strict mode).
  9. **Accent text on a fill it doesn't read on.**
  10. **Hand placement in strict mode.** `frame` is refused there.
- **Placement is the engine's job.** A floating overlay is placed in the free band above the head: between the top safe margin and the head box. It is scaled down to fit, never below the minimum text size. When it can't fit, `check` refuses with the fix (`"full": true`, or fewer words). Today the caller moves graphics by hand with `frame`.
- **Silence measured against the speech, dead air removed.** The pause search uses the take's own speech level, not only the noise floor, and merges room-noise flicker. A `from`/`to` segment drops its inner pauses of 0.30 s or more. Measured in the 2026-11-02 prototype: output silence within 0.4 points of the user's approved local edits on three videos.
- **Two false alarms and one silent fault from the prototype.** An in-point at source time 0 is clean. A dark scene on a light backdrop is an error.
- **Head box from the face step.** The face step returns the head box it already measures (the top 30% band of the person matte) next to the centre, as `head: [x0, y0, x1, y1]` in source pixels.

Out of scope:
- Render speed: that is `faster-preview-render`.
- Judging *which* take of a phrase is better. Claude chooses, and the engine only refuses keeping both.
- Paid transcription. Everything stays local Whisper.

## Capabilities

### New Capabilities

- `edit-faults`: strict mode, the never-list and its checks, and engine placement of floating overlays.

### Modified Capabilities

- `shortform-spec`: segments by word anchors; "No edge inside a word" without the lock exemption; restarts and untranscribed speech kept; contrast in the "Legibility probe".
- `local-transcription`: implausible words re-transcribed and replaced; smaller holes; restart markers.
- `brand-theme`: accent drawn as text reads on its fill.
- `footage-prep`: the face step also returns the head box.

## Impact

- Code:
  - `tools/short_spec.py`: validation, word-anchored edges, edge rules, restarts, strict;
  - `tools/shortform.py`: the probe contrast; `strict` passed through;
  - `tools/run_job.py`: the `strict` arg;
  - `tools/transcribe_local.py`;
  - `tools/motion/src/theme.ts` and the components that draw accent text (at least `Receipt`);
  - `tools/overlay_schema.py`, if the segment schema is exported.
- Tests: `tools/tests/test_short_spec.py`, `tools/tests/test_transcribe_local.py`, and a component contrast test.
- Skills: `short-form-pro` SKILL.md (cut by words; locks never excuse a word cut; restarts), and CLAUDE.md routing for `--strict`.
- Workflows: `short-form-pro` is affected (word anchors preferred; some old locked edits now fail). `video-use` and `motion-graphics` are not.
- **BREAKING** for edits that relied on a lock to keep an edge inside a word. They now fail `check`, and the message gives the fix.
- No new models, dependencies or paid services. Re-transcribing implausible words adds a few seconds per take.
