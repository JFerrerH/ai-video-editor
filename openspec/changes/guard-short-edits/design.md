# Design: edits that pass `check` must render correctly

## Context

See proposal.md for the evidence. The relevant current state:

- `tools/short_spec.py` validates the *shape* of `short.json`, builds a `shortform.Project`, calls `refine_edges()`, and resolves event `start`/`end` anchors. Event `props` are only checked as plain JSON (`_check_json`: depth, string length, file props). `check()` turns `refine_edges` WARN lines and `edge_energy` `<-- check` lines into warnings, never errors.
- `Project.refine_edges()` (`tools/shortform.py`) moves each segment's edges independently; it has no notion of neighbouring segments, so two contiguous cuts of one take can both widen into the same audio.
- Overlay components live in `tools/motion/src/components/` (registry in `Overlay.tsx`) and scene primitives in `tools/motion/src/scenes/` (`SCENES`). Their props are TypeScript types only; prop times (`lines[].at`, `items[].at`, `countStart`…) are passed straight to `sec()` and `interpolate()`, so a string or object becomes `NaN`. In the overlay layer, scenes draw no background unless the event has `full: true` (the `Backdrop`).
- `Project.stills()` composites one source frame, one Remotion still per layer and ffmpeg; `run()` raises `SystemExit("FAILED: <command>\n<stderr tail>")`. `run_job.py` already extracts the most specific error line (headless-jobs "Failures keep their cause").
- `Project.chunks()` breaks phrases on `[.,?!]$`, a ≥0.25 s gap, a segment change, or an emphasis boundary. `Captions.tsx` takes a fixed `top` (brand `captions.top`, default 1300).
- `tools/transcribe_local.py` passes `VERBATIM_PROMPTS.get(language or "en")`, so with no `--language` the English prompt goes to any audio. It never looks at the audio for holes.

## Goals / Non-Goals

**Goals:**
- Every fault in the evidence list is caught by `check`, `stills` or the transcriber, with a message a caller can act on without the tools.
- One schema per component, readable from Python without Node, and exportable as JSON.
- `build.py` projects keep working: the new rules raise errors only through `short_spec.check`/`load`; `Project` methods return data and the WARN-style report lines they return today.

**Non-Goals:**
- Full JSON Schema support. The validator implements the subset the components need.
- Rendering in `check`. Anything that needs pixels (legibility, caption collision) happens in `stills` and `render`.
- Changing what any component looks like.

## Decisions

### 1. Schemas: a JSON file beside each component, validated by a small stdlib module

Each component gets `<Name>.schema.json` next to `<Name>.tsx`, plus `tools/motion/src/event.schema.json` for the props the overlay layer reads on every event (`full`, `frame`, `behind`, `dark`, backdrop props). A new `tools/overlay_schema.py` loads them, validates props, walks annotated fields, and exports the bundle (`--export`).

Supported keywords: `type` (incl. a list of types), `enum`, `minimum`/`maximum`, `maxLength`, `items`, `properties`, `required`, `additionalProperties: false` (the default for every object), `oneOf` for the "number or anchor" case. Engine annotations:

| Key | On | Meaning |
|---|---|---|
| `x-time: "event"` | number field | seconds from the event's start; accepts anchors in a spec |
| `x-cues` | top level | list of `{path, default: {first, step} \| "even"`, `entrance: s \| {base, per_word, stagger_prop}}` |
| `x-text: true` | string field | shown to the viewer (probe + echo check) |
| `x-layout: "full" \| "float"` | top level | full-layout scene or floating element |

- **Why JSON files, not TS objects or zod:** Python must read them without Node (check runs before any Remotion call, and in the container's Python-only paths), and zod would add a runtime dependency to every component. A JSON file is diffable and is the export format.
- **Why not the `jsonschema` package:** the subset is ~150 lines; error messages must name the field path and say "must be a number, got the string \"400.000\"" in our wording. No new dependency.
- **Drift guard:** a Node script (`tools/motion/scripts/prop_keys.mjs`, using the `typescript` package already installed) prints each component's declared prop keys. The coverage test compares them with the schema's `properties` (both directions), ignoring `durationInFrames`. Cue defaults and entrance lengths are copied by hand from the component; unit tests pin them for `KineticType`, `ListScene` and `StatScene`, and the motion-graphics skill says to update the schema with the component.

### 2. Prop validation and time resolution in `short_spec`

`validate()` replaces `_check_json` on event props with `overlay_schema.validate(type, props)`; file-prop and length checks stay. Time fields accept a number or a word/segment anchor (same shapes as `_check_time`); a string is a type error. In `load()`, after event `start`/`duration` resolve, `overlay_schema.time_fields(type, props)` yields `(path, value)` for every `x-time` field; anchors resolve through the existing `_out_time()` minus the event start; the resolved number is written back into the props copy that goes to `overlay_props.json`. A value outside `[0, duration)` is an error; if `start ≤ v < start + duration` the hint is `v − start`.

Then `overlay_schema.cue_finish(type, props, fps)` computes each cue's finish time from explicit or default cues and the entrance length; any finish ≥ duration is an error. Events keep their spec index in `ev["index"]` so later messages (stills, failures) use the caller's numbering; the overlay layer ignores the extra key.

### 3. Overlaps and contiguous edges

Both live in `short_spec` with one helper in `Project`:

1. **Original overlap** (before refinement): for each pair of same-take segments where neither the later one (in output order) has `repeat: true`, `a.in < b.out and b.in < a.out` → error with the overlap length and the transcript words whose midpoint lies inside it.
2. **Joins:** pairs with `0 ≤ b.in − a.out ≤ 0.6` (either output order) are passed to `refine_edges(joins=[(i, j)])`. Refinement first moves every edge on its own; only when a's refined out would pass b's refined in does it set both edges to the lowest-energy 5 ms frame in `[a.out − 0.05, b.in + 0.05]` and report `joined` (a locked side wins: the other stops at it). Joining every pair (the first version of this design) undid pauses the editor had trimmed between two cuts of one take: +0.4 s on the ported project. Joining only on a crossing keeps those trims and still never plays audio twice.
3. **Refined overlap:** the same overlap test after refinement catches anything a locked edge or a non-join still pushes together.

`repeat` is a new optional boolean segment field; nothing else reads it.

### 4. Edges inside words and loud edges

`refine_edges` keeps its report lines but also returns structured results (`[{seg, edge, tag, t}]`) through a new `refine_edges(..., detail=True)`; `edge_energy` likewise returns `{seg, head_db, tail_db}`. `short_spec.check` decides severity:

- unlocked edge tagged "no silence" whose time lies inside a word (`start + 0.02 < t < end − 0.02`) → error naming the word and its two boundaries; locked → warning.
- edge energy > 12 dB on an unlocked edge → error ("segments[7] starts in the middle of sound: +20.9 dB over the room tone at 57.50"); 9–12 dB or locked → warning. The `<-- check` suffix stays in `Project.edge_energy()`'s text report for `build.py` users but is never forwarded by `check`.

12 dB is the proposed threshold; the pilot (task 9) records the edge energies of every edge in a few clean shorts and the threshold moves if a clean edge exceeds it.

### 5. Stills per event

`Project.stills()` takes the event list into account: after the requested (or midpoint) times it adds, per event, `t = start + min(1.2, 0.6 × duration)`, or one frame after its last reveal cue finishes when that is later (found in the pilot: at 1.2 s a list with late cues showed one item of four), clamped inside the event and `< total − 1 frame`, written as `ev{index:02d}_{type}_{t:06.2f}.png`. It returns `[{path, t, event?, type?}]` so `run_job` can report entries. Midpoint stills keep their `short_<t>.png` names.

### 6. Failures that name the event

`run()` raises a `ToolError(cmd, output)` (subclass of `SystemExit`, so existing callers and `run_job`'s message handling still work). Remotion calls go through one wrapper that catches it and:

- for a still: the active events at `t` are the suspects; if there is more than one, render each alone at `t` and blame the first that fails;
- for the full overlay render: take the frame from the Remotion output when it names one, else render each event alone at its own still time until one fails (only on failure, so the cost is acceptable).

The raised message is `events[N] (<Type>) failed at <t> s: <first Remotion error line>`, with the full output kept below it for stderr. The first-error-line logic moves from `run_job.py` into a shared helper both use.

### 7. Legibility probe and measured content boxes

For every event, `stills` renders the event alone (props with `full: false`, transparent background) at its still time. For events with `x-text` fields it renders a second still with those strings emptied (`lines[].text`, `items[].text`, `label`…). Both PNGs decode through ffmpeg to RGBA arrays (numpy, already a dependency); changed pixels = any channel differing by > 16. Below 0.05 % of the frame (≈ 1,000 px at 1080x1920, scaled with the still) → warning. Cost: two extra Remotion stills per text event, ~1–2 s each on the Mac.

The event-alone still also gives the content box (bounding box of alpha > 0). Boxes for `x-layout: full` events are cached in `edit/overlay_boxes.json`, keyed by a hash of the event JSON and brand, and reused by `render` (which measures any missing box first).

- **Why measure instead of declaring a box in the schema:** scenes centre their content; its height depends on text length, font and wrap. A declared box would be a guess and would either miss the reported 1270 px label or move captions needlessly. This deviates from the request's "scenes declare their content box"; the measured box answers the same question exactly. `check` therefore reports nothing about caption placement.

### 8. Caption placement

`caption_event()` adds `avoid: [[a, b, top]]` to the Captions props: for each full-layout event whose measured box bottom reaches the caption band (`top − 60`), captions in `[start, end)` move to `box.bottom + 60` if two caption lines (~180 px at the brand size) still end above 1536 px (bottom 20 % safe zone), else to `box.top − 60 − 180` if that is below 290 px (60 px, not 40: the caption shade's soft edge reaches ~46 px above the line, measured in the test still), else they stay and `stills` warns. `Captions.tsx` reads `avoid` and uses the range's `top` while the current time is inside it. No change for events without a measured box (floating elements, `build.py` projects that never ran `stills`).

### 9. Phrase breaks

`chunks()` breaks after `[.,?!;:…]$` and before a capitalised word whose predecessor is lowercase without trailing punctuation, unless that word (normalised) never appears lowercase in any take's transcript, or is "I". The name set is computed once per project from all transcripts.

### 10. Transcription

- **Shared envelope:** `Project._env` moves to `tools/audio_env.py` (`envelope(path) -> (db, floor)`, 5 ms hop / 20 ms window, 10th-percentile floor) and `speech_runs(db, floor, above=9, min_gap=0.3)`. `shortform` and `transcribe_local` both import it. No behaviour change for `refine_edges`.
- **Language detection:** when `--language` is absent, cut the first 30 s starting at the first speech run, run the backend's detection (faster-whisper `WhisperModel.detect_language`; on mlx, a no-prompt `mlx_whisper.transcribe` of that window, reading `language`), and continue with that language. Store `language_detected`.
- **Holes:** a word covers `[start, min(end, start + 1.5)]` padded by 0.3 s. Speech minus coverage gives uncovered stretches; each ≥ 1.5 s is cut out with 0.5 s padding, transcribed alone with no prompt in the same language, words offset back and kept only inside the padded stretch, then merged and the spacing entries rebuilt. A patch whose words are all from a known hallucination list ("Subtítulos…", "Thanks for watching") or average probability < 0.3 is discarded and the stretch reported as `untranscribed`. The model is loaded once per run, not per patch.
- **Prompt choice:** candidates per backend × language: current verbatim prompt, no prompt, a plain punctuated sentence. Metrics per take: word recall against a reference text, sentence-end punctuation count, seconds of speech uncovered before patching. Test set: the two synthetic takes plus at least two real takes per language kept under `footage/` (gitignored; only numbers are recorded, never names or text). Pick the candidate with no holes and the best recall; ties go to more punctuation. Results go in `tools/transcribe_prompts.md`; `VERBATIM_PROMPTS` becomes `PROMPTS[(backend, language)]` with a comment pointing there. Starting evidence for faster-whisper/es (one real take): verbatim prompt 333 words, 11 marks, no hole; no prompt 324 words, 13 marks, no hole; punctuated prompt 235 words, 30 s hole. Expected outcome is "no prompt" for es on faster-whisper, to be confirmed.

### 11. Schema op and image

`run_job.py` gains `schema` (no project, no args) returning `{"schema": bundle}`. The Dockerfile runs `uv run tools/overlay_schema.py --export > tools/motion/overlay_schema.json` at build time; `--self-check` reports that file and its component count. Project-less ops are new to the runner, so `schema` is special-cased before the project-name check.

## Risks / Trade-offs

- [Existing specs under `footage/` now fail `check`] → messages say exactly what to change (which word boundary, the hint value, `repeat`, `lock_in`); the skill documents the new rules; the pilot task re-checks every local `short.json` and lists what fails before merging.
- [Schema drifts from the component] → key-level drift is caught by the TS key test; cue defaults by pinned tests for the three evidence components; the skill makes "update the schema" part of changing a component.
- [Legibility probe false positives on tiny text (a small chip) or false negatives on a component whose panel changes with text] → the diff isolates text pixels; threshold is a warning, never an error; per-component minimum can be added later if the pilot shows noise.
- [Gap re-transcription inserts hallucinated words] → no prompt, discard by known-phrase list and low probability, record every patch so a caller can see and skip it; never patch outside detected speech.
- [Join logic changes cut points of existing `build.py` projects] → joins are only applied for pairs within 0.6 s in source, the case where independent widening was a bug; report lines show `joined`, and the ported-project test (`Render matches build.py`) runs on a project without joins.
- [12 dB edge-energy error is too strict for noisy rooms] → locked edges downgrade to a warning; `edges.above_floor` already adapts the floor; threshold recorded and revisited in the pilot.
- [Extra stills slow `stills`] → ~2–4 s per event on the Mac; acceptable next to a failed render. Probe stills run at 0.5 scale in preview.

## Migration Plan

1. Before the new rules ship as errors, run `check` over every local `short.json` (and the schemas over every local `storyboard.json`) and list what would fail, to catch schema mistakes against real props.
2. Ship as errors with the `short-form-pro` and `motion-graphics` skills and the CLAUDE.md op list updated in the same branch.
3. Bump the engine version (minor) and note the stricter `check` in the changelog; callers that hit new errors get the fix in the message.

Rollback: revert the branch; `short.json` files written for the new engine stay valid on the old one except for the `repeat` field and anchors in prop times.

## Open Questions

- Exact legibility threshold and caption line-height constant: set from the pilot's measurements.
- Whether `storyboard.py check` should adopt the schemas (proposal lists it as a follow-up).
