# Tasks

## 1. Shared audio envelope

- [x] 1.1 Move `Project._env` into `tools/audio_env.py` (`envelope()`, `speech_runs()`) and make `shortform.py` import it; verify `tools/tests/test_short_spec.py` still passes and `refine_edges` report lines are unchanged on a fixture take

## 2. Overlay schemas

- [x] 2.1 Write `tools/overlay_schema.py`: load `*.schema.json`, validate props (subset in design §1) with field-path messages, `time_fields()`, `cue_finish()`, `text_fields()`, `--export`; verify unit tests for each keyword, a string-for-number error (`"400.000"`) and an unknown key
- [x] 2.2 Add `tools/motion/src/event.schema.json` (shared event props: `full`, `frame`, `behind`, `dark`, backdrop props) and verify a `full: true` event validates on two different components
- [x] 2.3 Add `KineticType`, `ListScene` and `StatScene` schemas with `x-time`, `x-cues`, `x-text`, `x-layout`; verify pinned tests: ListScene default cues 0.5 s + 0.6 s steps, KineticType rise defaults 0.1 s + 0.35 s, StatScene `countStart`/`countEnd` marked as times
- [x] 2.4 Add schemas for every other component in `REGISTRY` and `SCENES` (except `Captions`); verify `--export` lists them all
- [x] 2.5 Add `tools/motion/scripts/prop_keys.mjs` (TypeScript compiler API) and a coverage test comparing declared prop keys with schema properties in both directions; verify it fails when a key is removed from one schema, then passes
- [x] 2.6 Run the validator over every local `footage/*/edit/short.json` events and `storyboard.json` scenes; fix schema mistakes it reveals (real props that are valid but rejected) and record the count of real prop errors found in the pilot notes

## 3. Spec validation in `short_spec`

- [x] 3.1 Replace `_check_json` on event props with schema validation (keep file-prop and length checks); accept anchors in `x-time` fields; verify tests for each wrong `at` form (output time, string `"0.5s"`, unknown key) and the string number
- [x] 3.2 Resolve prop time anchors to event-relative seconds in `load()` and write them into `overlay_props.json`; error with the hint when outside `[0, duration)`; verify the `18.2 → 0.7` message test and the word-anchor test (`items[1].at` = 1.3 in the written props)
- [x] 3.3 Check every cue's entrance finishes before the event ends; verify the late-last-item test on a 2.0 s ListScene with 4 default cues
- [x] 3.4 Carry each event's spec index (`ev["index"]`) through to the overlay props; verify the overlay still renders with the extra key (`npx tsc --noEmit` and one `stills` run)

## 4. Timeline integrity

- [x] 4.1 Add the optional `repeat` segment field and the original-range overlap error (both segments, seconds, transcript words); verify tests: overlap inside, deliberate `repeat`, different takes
- [x] 4.2 Add joins to `refine_edges` (both edges to the quietest frame between them, report `joined`) and the post-refinement overlap check; verify the touching-segments test (refined out ≤ next in) on a fixture take, and that a fixture without joins gives identical edges to before
- [x] 4.3 Return structured edge results from `refine_edges`/`edge_energy`; in `check`, error on an unlocked no-silence edge inside a word (with both boundaries) and on edge energy > 12 dB, warning when locked or 9–12 dB; drop `<-- check` from `check` output; verify tests for in-word in-point, locked in-word, loud head
- [x] 4.4 Update the ported-project test (`Render matches build.py`) expectations if joins apply to it, and verify it passes

## 5. Stills, failures, probe, caption placement

- [x] 5.1 Make `stills` add one still per event at `start + min(1.2, 0.6 × duration)`, named `ev{NN}_{Type}_{t}.png`, and return entries with time/event/type; verify a test with `--at` times plus one event writes both kinds
- [x] 5.2 Add `ToolError` and the shared first-error-line helper (moved from `run_job.py`); wrap Remotion calls to name the failing event (isolate by rendering active events alone); verify a test that injects a NaN cue past validation gets `events[N] (<Type>) failed at <t> s: …`, and `test_run_job.py` failure tests still pass
- [x] 5.3 Add the legibility probe (event alone vs. text emptied, pixel diff, warning under the threshold) and cache measured content boxes in `edit/overlay_boxes.json`; verify the out-of-frame KineticType warns and the `at: 0.2` one doesn't
- [x] 5.4 Add `avoid` ranges to `caption_event()` from measured boxes and support them in `Captions.tsx`; `stills` warns when captions fit neither below nor above; verify with a StatScene whose label reaches the caption band: in its still no caption pixel is inside the label box, and `npx tsc --noEmit` passes
- [x] 5.5 Make `render` measure any missing full-layout box before rendering the overlay; verify a preview render of the same spec places captions as in the still (frame pulled at the event's still time)

## 6. Caption phrase breaks

- [x] 6.1 Break `chunks()` after `[;:…]` and at capitalised-after-lowercase joins, with the never-lowercase name rule and "I"; verify tests: "nuestro dinero Entonces te voy a" splits, "vivo en Lisboa desde" doesn't, English "and I think" doesn't

## 7. Transcription

- [x] 7.1 Detect language when `--language` is absent (first 30 s from the first speech run; faster-whisper `detect_language`, mlx no-prompt window) and record `language_detected`; verify with the Spanish synthetic take on the local backend
- [x] 7.2 Find uncovered speech stretches (word coverage capped at 1.5 s), re-transcribe each alone with no prompt, merge and rebuild spacing, discard hallucination-like patches, write `source.patched` and `untranscribed`, print warnings; verify unit tests on a backend result with words removed for 0–30 s and the stray-words case, using a stubbed backend
- [x] 7.3 Build the synthetic Spanish and English takes with `tools/gen/voice.py` (4–6 sentences, one false start, 5 s silence then a 20 s stretch) in a test fixture generator, and add the completeness test (≥ 95 % recall, sentence ends punctuated or followed by ≥ 0.25 s, empty `untranscribed`), skipped when the `gen` group is missing; verify it passes on the Mac (mlx) and in the container (faster-whisper)
- [ ] 7.4 Measure prompt candidates per backend × language on the synthetic takes plus ≥ 2 real takes per language under `footage/` (numbers only); write `tools/transcribe_prompts.md`; switch `VERBATIM_PROMPTS` to `PROMPTS[(backend, language)]` with a pointer to the table; verify the table has every candidate × take row and the chosen prompt has no holes on any take
- [x] 7.5 Update the local-transcription notes in CLAUDE.md ("Transcription: local first": detection, patches, `untranscribed`) and verify the documented command runs as written

## 8. Headless jobs

- [x] 8.1 Add the `schema` op (no project, no args) and list it in `--help`; verify `{"op": "schema", "args": {}}` returns `ok: true` with `KineticType`, `ListScene`, `StatScene` and empty `outputs`
- [x] 8.2 Return `language_detected`, `patched` and `untranscribed` from `transcribe`, and still entries plus warnings from `shortform stills`; verify `test_run_job.py` result-field tests
- [x] 8.3 Generate `tools/motion/overlay_schema.json` in the Dockerfile and report it in `--self-check`; verify `docker build` and `docker run --rm video-engine --self-check` list the file and its component count
- [x] 8.4 Update CLAUDE.md "Linux / Docker" op list with `schema` and the new result fields; verify every op named there exists in `run_job.py --help`

## 9. Skills

- [x] 9.1 Update `.claude/skills/short-form-pro/SKILL.md`: what `check` now enforces (overlaps, `repeat`, edges in words, loud edges), prop times are event-relative and accept anchors, per-event stills and probe warnings, caption avoidance; remove manual steps `check` now does; verify every rule it cites matches a `check` message
- [x] 9.2 Update `.claude/skills/motion-graphics/SKILL.md`: every new or changed component ships its `<Name>.schema.json` (annotations and the coverage test); verify the instructions by adding a throwaway prop to one component, seeing the coverage test fail, and reverting

## 10. Pilot verification

- [x] 10.1 Re-run `check` on every local `footage/*/edit/short.json`; list which now fail and why, and confirm each failure is a real fault (or fix the rule)
- [x] 10.2 Pilot under `footage/` (gitignored): a talking-head take with a spec reproducing evidence 1–8 (overlaps, late `at`, anchor props, string value, in-word edge, a StatScene label in the caption band); verify `check` reports each with the specified message, then fix the spec as the messages say and verify `check` passes
- [x] 10.3 Run `stills` on the fixed pilot; Read every PNG including each `ev*` still, confirm titles are legible and captions clear scene text, and that no warnings remain
- [x] 10.4 Render the pilot preview; pull a frame at each cut and each event's still time and Read them; listen-equivalent check: confirm no transcript word appears twice in the captions; measure loudness (-14 LUFS ±0.5, true peak ≤ -1 dBTP) and record numbers, edge energies and the measured thresholds (edge dB, probe pixels) in the pilot's `edit/project.md`
- [x] 10.5 Run the same pilot through the container (`shortform` check/stills/render jobs) and verify the result JSON fields and identical still names

## Workflow follow-up

- Run `/opsx:verify`, then `/opsx:archive` after review; confirm SKILL.md and CLAUDE.md match shipped behaviour before archiving.
- Bump the engine version (minor) and note the stricter `check` in the release notes.
