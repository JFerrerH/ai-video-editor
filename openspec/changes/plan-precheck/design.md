# Design

## Context

In a measured hosted session, rounds refused by `plan_build` in 0.9–1.5 s of work waited 44–54 s each for a worker. The checks that refused them: echo (`Project` in `shortform.py`, from caption words and event texts), entrance fit (`edit_plan.build`, from word times and `overlay_schema.cue_finish`), and `validate_plan`. `edit_plan` and `overlay_schema` import only the standard library at module level; `short_spec` and `shortform` pull in numpy and the audio code.

## Goals / Non-Goals

Goals: one module a service can import without the engine image; the build and the precheck share code.

Non-goals: audio or render checks; the service side.

## Decisions

**D1. Extract, don't duplicate.** The timing pass of `build` (sentences → output times → beat holds and entrances) moves into `plan_precheck.compile_times`, which `build` calls. Output times come from word times with the edge refinement's `pre`/`post` air and the same dead-air splits. These are approximate: measured on four real plans, a cut is off by up to ~2 s and a whole short by 1–3.5 s, because Whisper stretches a word's stamp over the pauses beside it. The build therefore runs the timing-independent part of the precheck first and stops on it; the timing checks (entrance fit, echo, shared screen, pacing) run again in the build on the audio-measured cut with the same functions (`fit_beat`, `echo`, `shared_screen`, `pacing`), and the precheck reports the ones from its own clock under `timed_errors`.

**D2. Echo as a pure function.** `echo(events, caption_words, window)` takes plain lists (events as `type`/`start`/`duration`/`props` dicts, caption words as `text`/`start`); `Project.echo_check` builds them and calls it. The caption words in the precheck are the kept words with their output times and the plan's caption fixes; the echo rule only needs which words are said when, so `chunks` stays in `shortform`.

**D3. No-pause cuts from word times.** A cut the plan itself makes (a punch-in's sentence, the low line) that falls where the transcript's words run together is an error, as `build` already reported. A kept run that starts or ends where the gap to its neighbour is under `MIN_PAUSE` (0.06 s, the shortest quiet run the audio check calls a pause) is a warning with the sentence, not an error: Whisper stamps a word over the pause beside it, so a cut with a real pause can read as a zero gap (a real approved plan has two). The audio check in the build stays the authority and can only add findings.

**D4. A test enforces the import rule.** It imports `plan_precheck` in a subprocess with `-I` and a `sys.path` holding only `tools/`, after blocking `numpy`.

## Risks / Trade-offs

- **Times differ from the build's** by up to a couple of seconds on real footage. A timing check near its threshold can flip either way in the precheck (a false echo on an approved plan was found this way). So the build never stops on the precheck's timing errors; it decides from the audio. A service that refuses on the precheck's `timed_errors` alone accepts that a few plans are refused early that the audio would accept.

## Migration Plan

Engine release; the product can then import the module (its own change).

## Open Questions

None.
