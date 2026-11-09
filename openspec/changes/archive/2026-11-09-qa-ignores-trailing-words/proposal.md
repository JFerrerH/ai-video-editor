# Proposal

## Why

Preview QA refused a preview that was right: with the worker's transcriber it heard one word, "paris", 0.1 s after the last word of the edit. The heard and expected counts were equal (196 and 196), the audio there is not silence (the decay of the last word, 11 dB under the speech level), and the same word at the same second refused a hosted session's preview, costing a round of about five minutes. Whisper adds a word at the end of audio now and then. The render guarantees nothing but the edit can sound there: the last clip's audio ends before the next source word's onset, in the held tail.

## What Changes

- A heard word that comes after every word the edit keeps is not reported as unexpected speech. Words inside the edit, at a cut or in a pause, are checked as before.

Out of scope: any other QA rule, and the transcription backend.

Tools: `tools/preview_qa.py`. Skill: `short-form-pro` (one line). No new dependencies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `preview-qa`: nothing heard after the last kept word is unexpected speech.

## Impact

Fewer false refusals at the end of a short. A leak at a cut inside the edit is as visible as before.
