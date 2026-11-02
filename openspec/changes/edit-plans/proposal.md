# Proposal

## Why

In the hosted pilot (2026-11-01/02), the user's Claude guessed cut times. The transcript it received only timed phrases, and a spec in seconds asks for precision that no conversation has. The cuts, the placement and the timing of every graphic are execution, not judgment. The judgment (which lines to keep, what each moment needs, what object carries the story) belongs to the Claude that wrote the edit.

A prototype compiler (`prototype/compile_plan.py`, 2026-11-02) took a plan in sentence IDs and "what to show" and produced a spec that `check` passed:
- its cuts matched the user's approved local edits on three videos: output silence 3.0 / 12.2 / 17.6 % vs 3.4 / 12.4 / 17.3 %;
- its QA (`prototype/qa.py`) caught a deliberately bad edit (energy −7.2 dB and +1.6 dB at two cuts, an unexpected "conversemos") that `check` had passed.

The live stage (`live-stage`) adds a camera and new devices. The plan is where Claude chooses them.

## What Changes

- **Numbered sentences.** `plan ids <project>` prints the transcript as numbered sentences (`F1`, `F2`, …). Each sentence shows its takes, its duration and the restart markers from `strict-edit-faults`. Claude refers to lines by these IDs, never by seconds.
- **The plan format** (`edit/plan.json`, validated, schema exported). It has:
  - `keep`: sentence IDs in order, or ranges;
  - `hook`;
  - `beats`: each one names a sentence and an optional word, a device (a stage component, a camera move, or both), the device's content (text, screens, asset paths), and an optional `object` id;
  - optional `low` (one sentence and its words);
  - `cta`;
  - `assets`.
  Nothing in it is in seconds.
- **`plan build`** compiles the plan into `edit/short.json`, using general rules only. No rule names a word, a time, a brand or a project.
  - **Segments:** `from`/`to` word anchors for the kept sentences, with dead air removed (the rules in `strict-edit-faults`).
  - **Timing:** every beat's time comes from its word, and it holds until the thought ends (≤ 6 s).
  - **Layers and placement:**
    - each device gets its default layer and camera move;
    - floating text is placed above the head box;
    - a beat that doesn't fit is refused with the fix.
  - **Sound effects** are sparse:
    - one per visible, important change, from a small table per device;
    - the brand's `rejected_sfx` is a hard rule;
    - `pluck` is never used.
  - **Restraint:**
    - at most two punch-ins beyond the hook;
    - at most one `low` look;
    - a pacing report: the longest stretch without a visual change, with a warning past 8 s (the median in the references is about 5 s).
  - **No quotas.** The compiler never adds a device the plan didn't ask for.
- **`preview_qa`.** After a render, it checks the preview against the plan:
  - it transcribes the preview;
  - it compares the words heard with the words the edit should play, each word owned by the segment that covers most of it;
  - it measures energy at each cut against the speech level, using the real clip durations, and refuses anything above −12 dB;
  - it reports clipped words, phrases repeated more often than the take says them, unexpected speech, and heard restarts.
  It returns errors naming the output time and the fix.
- **Headless ops.** `plan_ids`, `plan_build` and `preview_qa` join the fixed operation list.

Out of scope:
- Which device fits which line: the plan's author decides. The guide that teaches it lives in the product (`video-studio` change `edit-plans`).
- New components or camera moves: `live-stage`.
- Any call to a language model. Everything here is deterministic.

## Capabilities

### New Capabilities

- `edit-plans`: numbered sentences, the plan format, and the compiler's rules.
- `preview-qa`: the output check of a rendered preview.

### Modified Capabilities

- `headless-jobs`: `plan_ids`, `plan_build` and `preview_qa` in the operation list.

## Impact

- Code:
  - `tools/edit_plan.py` (new; from `prototype/compile_plan.py`, rewritten for the stage devices and word-anchored segments);
  - `tools/preview_qa.py` (new; from `prototype/qa.py`);
  - `tools/run_job.py`;
  - `tools/overlay_schema.py` (plan schema export).
- Tests: plan validation, compile on fixtures, and QA on a fixture preview with injected faults (the `xp-bad` control).
- Skills: `short-form-pro` SKILL.md gains "Edit by plan" as the preferred path. Writing specs by hand stays possible locally.
- Workflows: `short-form-pro` (new preferred path); `video-use` and `motion-graphics` are unaffected.
- No new dependencies. `preview_qa` uses the existing local Whisper, about 40 s for a 70 s preview on the Mac.
- Depends on `strict-edit-faults` (word anchors, restart markers, dead air) and `live-stage` (devices, camera).
