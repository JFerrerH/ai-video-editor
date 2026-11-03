## Why

Replaying the approved plans through a real worker, with transcripts made by this release, found three gaps. The engine's own tests used older transcripts that have no restart marks, so they didn't show.

1. **Real sentences are refused as false starts.** A phrase counts as abandoned after any pause without a full stop, and as restarted if its first two words come back within 6 s, even with whole sentences in between. In an approved video, an 8.4 s sentence and the next one were both flagged, the second only because the sentence after it opened with the same two common words. Plans can't keep a flagged sentence, so the approved plan is refused. Openings like "Y en" are common enough in Spanish that this would hit other videos.
2. **A misheard word can't be fixed in a plan.** A plan has no caption fixes, so a wrong brand name stays wrong in the captions.
3. **Sentence numbers don't follow the shoot.** Takes are numbered in file-name order. A hosted project names files by random ID, so F1 can be in the last take.

4. **A breath is refused as speech with no words.** A stretch counts as speech when it is above the room's floor. In the same video, 1.4 s after a sentence sits at -40 dB, against -24 dB for the speech and -52 dB for the floor. Whisper hears nothing there on either machine, and strict mode refuses a segment that keeps it. Measured on 5 real takes: their sentences sit at -8.8 dB or above relative to speech, these stretches at -16.5 dB or below.

## What Changes

- A restart needs the repeat right after the abandoned phrase: at most 2 words in between. Applies to the transcript's marks and to the plan's sentence flags.
- A stretch without words is listed as `untranscribed` only if it is within 12 dB of the take's speech: the same limit `preview_qa` uses at cuts.
- A plan can carry `captions: {"fixes": {"heard": "said"}}`.
- `plan_ids` and `plan_build` take an optional `order`: the take names in the order they were shot. Without it they keep name order.
- `short-form-pro` SKILL.md: pacing text matches what the code does (warns past 5 s, refuses past 8 s).
- The entrances error prints two decimals ("needs 1.5 s, only 1.5 s fit" says nothing) and names starting the beat earlier as a fix.

## Capabilities

### Modified Capabilities

- `local-transcription`: what counts as a restart.
- `edit-plans`: take order for sentence IDs; caption fixes in a plan.

## Impact

`tools/transcribe_local.py`, `tools/edit_plan.py`, `tools/run_job.py`, their tests, and the skill. Plans and jobs without the new fields behave as before, except that fewer sentences are flagged as false starts.
