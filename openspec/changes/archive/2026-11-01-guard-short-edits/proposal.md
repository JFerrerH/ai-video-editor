# Proposal: edits that pass `check` must render correctly

## Why

`edit/short.json` exists so an edit written by a caller who can't run the tools (a queue worker's client) is safe *and* correct. Today it is only safe: `check` passes edits that render with repeated audio, invisible titles and glued captions, and it lets props through that crash Remotion minutes later. Each of these is a check the `short-form-pro` skill tells a human to do by hand ("refined out ≤ the next in", "read every warning", "verify before presenting"); an edit-as-data caller can't do them, so `check`, `stills` and the transcriber have to.

Evidence, reproduced on engine v0.5.0 (linux/arm64) with one 109.6 s Spanish talking-head take:

1. **Repeated audio.** Same-take segments `26.62–33.92` then `33.16–39.07` (and two more pairs) pass `check`; the render plays and captions "Entonces te voy a" twice. `short_spec.py` has no overlap rule.
2. **Invisible kinetic type.** `KineticType` (`style: rise`) with `lines[].at` = `18.2` (output time) in a 4 s event, `{"word": …}` or `"0.5s"`: every word stays under its mask. No error, no warning.
3. **Crashes after `check`.** `ListScene` `items[].at: {"word": …}` → `inputRange must contain only finite numbers … [NaN,NaN]` during `stills`; also `Frame NaN is not finite`. 4 of 7 failed caller rounds were these.
4. **Silent wrong values.** `StatScene` `value: "400.000"` renders `$400`.
5. **Transcript holes, glued captions.** faster-whisper large-v3-turbo drops 0–30 s of speech with no `--language` (English prompt) and again with a punctuated Spanish prompt; with the current Spanish prompt it loses sentence punctuation, so `chunks()` (breaks only on `[.,?!]$` or a ≥0.25 s gap) glues "nuestro dinero Entonces te" into one caption. mlx-whisper hit the same hole on the Mac.
6. **Cut inside a word.** In-point 57.50 inside "empezar" (57.28–57.64): `check` prints `WARN no silence before onset` and `head +20.9 dB <-- check`, then renders.
7. **Overlays nobody looked at.** `stills` covers segment midpoints or the caller's `--at` times only; a broken title at 17.5–20.5 s was never stilled.
8. **Caption over a scene's text.** A `StatScene` label sits in the brand's caption band, and the caption prints over it.

## What Changes

- **Timeline integrity (errors in `check`).** Same-take segments whose source ranges overlap, before or after edge refinement, are an error naming both segments, the seconds and the repeated words. `refine_edges` never widens an edge past a source-contiguous neighbour's; it locks both at the deepest dip between them. A new per-segment `"repeat": true` allows a deliberate repeat. An unlocked edge refinement can't move to silence and that falls inside a transcript word is an error naming the word and the nearest boundaries. Edge energy above +12 dB over the take's floor joins that error; below stays a warning, in words instead of `<-- check`. **BREAKING** for specs that relied on these passing.
- **Typed overlay props.** Every overlay component and scene ships a props schema next to its source. `check` validates event props against it (unknown keys, types, enums, ranges, required keys) with field paths. Time fields inside props are seconds from the event's start, also accept the event anchors (`word`, `seg`), are resolved before `overlay_props.json` is written, and must land inside the event with the entrance finished before it ends; an out-of-range value gets a "did you mean" hint. A test fails if a component has no schema. **BREAKING** for specs with ill-typed props.
- **Schema export.** A new `schema` op in `run_job.py` (and a fixed file in the image) returns every component's schema, so a hosted guide can be generated from it.
- **Stills that cover every overlay, failures that name the event.** `stills` always adds one still per overlay event once its entrance has finished, named by event index and type. A Remotion failure in `stills` or `render` names the event index, type, output time and the first Remotion error line. A legibility probe warns when a text-bearing event shows almost no text in its still.
- **Captions.** Phrase breaks also at `[;:…]` and at a capitalised word following an unpunctuated lowercase one (a Whisper segment join), except words the transcript capitalises mid-sentence elsewhere. Captions move above or below a full-layout event's measured content when they would cover it, or `stills` warns when they can't.
- **Transcription completeness.** No `--language` → detect it first and use that language's prompt (or none), recording `language_detected`. Speech runs (from the same RMS envelope as `refine_edges`) of ≥1.5 s with no words are re-transcribed alone and merged, recorded in `source.patched`; still-empty runs go in `untranscribed` and in the `transcribe` op's result. The per-backend, per-language prompt is chosen by a recorded measurement.
- **Tests.** A synthetic Spanish and English take built with the local voice tool (known sentences, a false start, 5 s of silence before a 20 s stretch), plus `short_spec` unit tests for every evidence item. No client footage.

## Out of scope

New overlay components, music, GPU paths, a new `short.json` version (all additions are backwards compatible except that overlapping or ill-typed specs now fail, on purpose). Validating `storyboard.json` scene props against the new schemas (the schemas make it possible; wiring `storyboard.py check` to them is a follow-up). Speaker diarization. Changing caption styling or the Captions component's look.

## Capabilities

### New Capabilities
- `overlay-schema`: per-component props schemas for overlay components and scene primitives: the schema files, time-field and reveal-cue semantics, text and content annotations, coverage test and export.

### Modified Capabilities
- `shortform-spec`: `check` gains overlap, edge-in-word and edge-energy errors, the `repeat` field, schema validation and resolution of event props; `stills` gains per-event stills, the legibility probe and caption-collision warnings; render failures name the event; captions break on segment joins and avoid scene content.
- `local-transcription`: language detection before choosing a prompt, gap re-transcription with `source.patched` / `untranscribed`, measured prompt choice per backend and language.
- `headless-jobs`: new `schema` op; `transcribe` reports `untranscribed` and `language_detected` as result fields; `shortform stills` reports per-event stills and probe warnings.

## Impact

- **Tools:** `tools/short_spec.py` (validation, prop resolution), `tools/shortform.py` (`refine_edges`, `edge_energy`, `stills`, `chunks`, `caption_event`, Remotion failure reporting), `tools/transcribe_local.py`, `tools/run_job.py`, new `tools/overlay_schema.py` (loader + validator, standard library only).
- **Motion:** one `<Name>.schema.json` beside each component in `tools/motion/src/components/` and `tools/motion/src/scenes/` (~38 files); `Captions.tsx` gains an `avoid` range prop. No component behaviour changes otherwise.
- **Skills / docs:** `short-form-pro` SKILL.md (what `check` now enforces, `repeat`, prop times are event-relative, per-event stills), `motion-graphics` SKILL.md (schema beside every new component), CLAUDE.md headless op list.
- **Workflows:** `short-form-pro` (stricter `check`, more stills); `video-use` unaffected except through better transcripts; `motion-graphics` / storyboards unaffected at runtime.
- **Dependencies:** none new. Language detection uses the Whisper models already installed (faster-whisper `detect_language`, mlx-whisper's decoder language probe). Gap re-transcription adds roughly one short model call per hole (a few seconds each on a 32 GB M-series Mac; ~4× real time on CPU in Docker).
- **Compatibility:** previously accepted specs with overlapping same-take segments, edges inside words, or ill-typed props now fail `check` with a message saying how to fix them.
