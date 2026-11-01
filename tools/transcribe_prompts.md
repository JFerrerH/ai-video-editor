# Transcription prompts: measured choice per backend and language

`tools/transcribe_local.py` uses `PROMPTS[(backend, language)]`, chosen from the numbers below
(measured 2026-11-01 with `tools/tests/measure_prompts.py`: mlx on an M-series Mac, faster-whisper in the
linux/arm64 container; Whisper large-v3-turbo on both).

**Candidates:** `verbatim` (the disfluent prompt that keeps fillers), `none` (no prompt), `plain` (one plain,
punctuated sentence in the language).

**Takes:** the synthetic take per language (`tools/tests/synthetic_takes.py`: known script, a false start,
5 s of silence then ~20 s of speech) and real talking-head takes kept on the measuring machine (only
numbers are recorded). Spanish: synthetic + 3 real (110 s, 116 s, 20 s; all with fillers). English:
synthetic + 1 real (29 s); a second real English take is still to be added.

**Metrics:** words; recall (against the script for synthetic takes, against the fullest candidate on the
same backend for real takes, which have no script); sentence-end marks; holes = seconds of speech no word
covers before patching (`uncovered()` in the transcriber).

**Rule:** fewest hole seconds over all takes, then best mean recall, then more sentence marks, then more
words (a prompt that keeps disfluencies helps the edit).

## Choice

| backend × language | verbatim (holes s / mean recall) | none | plain | chosen |
|---|---|---|---|---|
| mlx × en | 0.0 / 1.000 | 0.0 / 1.000 | 0.0 / 1.000 | **verbatim** |
| mlx × es | 23.1 / 0.916 | 1.9 / 0.986 | 1.9 / 0.997 | **plain** |
| faster-whisper × en | 0.0 / 1.000 | 0.0 / 1.000 | 0.0 / 1.000 | **verbatim** |
| faster-whisper × es | 23.2 / 0.918 | 6.8 / 0.997 | 23.2 / 0.918 | **none** |

- **Spanish, both backends:** the verbatim prompt makes Whisper skip ~21 s of speech in real take A (110 s), on
  mlx and on faster-whisper. On faster-whisper the plain prompt does too, so that backend uses no prompt; on mlx
  plain and none tie on holes and plain has the better recall.
- **The 1.9–2.0 s left in real take B** appear under every candidate on both backends: sound at speech level
  between two sentences that gets no words even when transcribed alone. The transcriber reports it as
  `untranscribed`. **faster-whisper/es with no prompt** still leaves a 4.8 s hole in take A; the hole check
  re-transcribes it.
- **English:** every candidate scores the same; verbatim keeps the false start ("I was- I was").

## All rows

| backend | take | candidate | words | recall | sentence marks | holes (s) |
|---|---|---|---|---|---|---|
| mlx | en synthetic A (31 s) | verbatim | 92 | 1.000 | 6 | 0 |
| mlx | en synthetic A (31 s) | none | 91 | 1.000 | 6 | 0 |
| mlx | en synthetic A (31 s) | plain | 91 | 1.000 | 6 | 0 |
| mlx | es synthetic A (34 s) | verbatim | 89 | 0.989 | 6 | 0 |
| mlx | es synthetic A (34 s) | none | 89 | 0.989 | 6 | 0 |
| mlx | es synthetic A (34 s) | plain | 89 | 0.989 | 6 | 0 |
| mlx | es real A (110 s) | verbatim | 234 | 0.677 | 10 | 21.2 |
| mlx | es real A (110 s) | none | 323 | 0.955 | 10 | 0 |
| mlx | es real A (110 s) | plain | 331 | 1.000 | 12 | 0 |
| mlx | es real B (116 s) | verbatim | 359 | 1.000 | 12 | 1.9 |
| mlx | es real B (116 s) | none | 359 | 1.000 | 12 | 1.9 |
| mlx | es real B (116 s) | plain | 359 | 1.000 | 12 | 1.9 |
| mlx | es real C (20 s) | verbatim | 72 | 1.000 | 2 | 0 |
| mlx | es real C (20 s) | none | 72 | 1.000 | 2 | 0 |
| mlx | es real C (20 s) | plain | 72 | 1.000 | 1 | 0 |
| mlx | en real A (29 s) | verbatim | 95 | 1.000 | 9 | 0 |
| mlx | en real A (29 s) | none | 95 | 1.000 | 9 | 0 |
| mlx | en real A (29 s) | plain | 95 | 1.000 | 9 | 0 |
| faster-whisper | en synthetic A (31 s) | verbatim | 92 | 1.000 | 6 | 0 |
| faster-whisper | en synthetic A (31 s) | none | 91 | 1.000 | 6 | 0 |
| faster-whisper | en synthetic A (31 s) | plain | 91 | 1.000 | 6 | 0 |
| faster-whisper | es synthetic A (34 s) | verbatim | 89 | 0.989 | 6 | 0 |
| faster-whisper | es synthetic A (34 s) | none | 89 | 0.989 | 6 | 0 |
| faster-whisper | es synthetic A (34 s) | plain | 89 | 0.989 | 6 | 0 |
| faster-whisper | es real A (110 s) | verbatim | 235 | 0.685 | 12 | 21.2 |
| faster-whisper | es real A (110 s) | none | 302 | 1.000 | 12 | 4.8 |
| faster-whisper | es real A (110 s) | plain | 234 | 0.685 | 12 | 21.2 |
| faster-whisper | es real B (116 s) | verbatim | 359 | 1.000 | 13 | 2.0 |
| faster-whisper | es real B (116 s) | none | 359 | 1.000 | 13 | 2.0 |
| faster-whisper | es real B (116 s) | plain | 359 | 1.000 | 13 | 2.0 |
| faster-whisper | es real C (20 s) | verbatim | 72 | 1.000 | 2 | 0 |
| faster-whisper | es real C (20 s) | none | 72 | 1.000 | 2 | 0 |
| faster-whisper | es real C (20 s) | plain | 72 | 1.000 | 2 | 0 |
| faster-whisper | en real A (29 s) | verbatim | 95 | 1.000 | 9 | 0 |
| faster-whisper | en real A (29 s) | none | 95 | 1.000 | 9 | 0 |
| faster-whisper | en real A (29 s) | plain | 95 | 1.000 | 9 | 0 |
