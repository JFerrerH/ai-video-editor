# Proposal

## Why

On a hosted service each `plan_build` waits for a worker before it starts. In one measured session, 5 of 9 plan rounds were refused by checks that need only the plan, the transcript and the component schemas (a false start kept, a graphic repeating the captions, entrances that don't fit before the next beat) and finished in about a second of work, but each cost close to a minute in the queue. Those checks live inside the compiler, next to steps that need the audio, so a service can't run them without a worker.

## What Changes

- `tools/plan_precheck.py`: every check that needs only the plan, the transcript JSON and the schemas, with the standard library only: `validate_plan`, schema limits, beat timing and entrance fit, a graphic echoing the captions, pacing, and cuts with no pause in the transcript's word times.
- `edit_plan.build` runs the precheck's timing-independent checks first and stops on their errors; the timing checks run again in the build on the audio-measured cut with the same functions, so the two report the same findings in the same words (the precheck's clock is word times, which are approximate).
- Echo matching becomes a pure function that both the precheck and `shortform check` call.
- New op `plan_precheck` in `run_job.py`, for local use and tests.

Out of scope: checks that need the audio or a render (edge refinement, loud edges, stills, contrast, preview QA), and how a service calls the module.

Tools: new `tools/plan_precheck.py`; `tools/edit_plan.py`, `tools/shortform.py` (echo), `tools/run_job.py`. Skill: `short-form-pro` (one line). No new dependencies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `edit-plans`: a precheck that answers without audio, and that the build runs first.

## Impact

`plan_build` starts with the precheck. The module and its inputs must stay standard-library only, which a test enforces.
