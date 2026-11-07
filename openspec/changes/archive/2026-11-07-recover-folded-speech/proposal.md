# Proposal

## Why

A speaker stopped mid-sentence, paused 2 s and said the sentence again. Whisper stretched one word over the pause and the retake, the retry's correct words were thrown away because they fell inside that stretched word, and the false start went unmarked. The plan was then refused with a fix it could not apply ("listen to it, or cut around it"): a plan can't listen and can't cut inside a sentence. The only way out was to cut the footage outside the engine and start again, which no unattended edit should need.

## What Changes

- A word stretched over a pause and speech is treated as implausible, even when speech fills under 60% of it, so its retry replaces it instead of being discarded.
- A word recovered by a retry starts where the speech starts, not in the silence before it.
- Restart detection finds an abandoned phrase that has short pauses inside it, such as after a comma.
- `transcribe` writes `breaks`: the times where a sentence must end, at each abandoned phrase's edges and each `untranscribed` range's edges. `edit_plan` splits sentences there, so a false start or a hole can be left out by sentence ID.
- Transcripts without `breaks` number exactly as before, so a saved plan on an already prepared project keeps its IDs.
- A plan refused for kept speech with no words names the sentences to change, in plan terms.

Out of scope: keeping speech with no words on purpose (strict edits still refuse it), `keep` by word instead of by sentence, a new transcription model, and any change to `shortform check` outside plans.

Tools: `tools/transcribe_local.py`, `tools/edit_plan.py`. Skill: `short-form-pro` (false starts and holes in plans). Workflows: `short-form-pro` and headless `plan_ids` / `plan_build`; `video-use` gets better `restarts` and no new step. No new models or dependencies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-transcription`: stretched words are repaired, recovered words start on speech, restarts span inner pauses, transcripts list `breaks`.
- `edit-plans`: sentences split at `breaks`; a refusal for speech with no words names a fix a plan can apply.

## Impact

`tools/transcribe_local.py`, `tools/edit_plan.py`, their tests, `short-form-pro` SKILL.md and CLAUDE.md. The transcript JSON gains one optional field. A hosted service must prepare footage again to get the new sentences.
