# Tasks

## 1. Transcription

- [x] 1.1 Add tests in `tools/tests/test_transcribe_local.py` for the stretched word, the long word over silence, and the recovered word stamped in the pause
- [x] 1.2 Widen `implausible` to words hiding uncovered speech (D1), and check the existing `Holes` and `Implausible` tests still pass
- [x] 1.3 Move a recovered word's start to the next speech run (D2)
- [x] 1.4 Add a test for the pause inside the abandoned phrase, then change `mark_restarts` to find the repeat first and walk back (D3)
- [x] 1.5 Write `breaks` to the transcript JSON, with tests for the false start, the hole and the empty list

## 2. Plans

- [x] 2.1 Read `breaks` in `load_words`, and end a sentence before a word at a break in `sentences()`
- [x] 2.2 Add tests: false start after an unpunctuated line, and a transcript with no `breaks` keeping its IDs
- [x] 2.3 Rewrite the refusal (`_hole_hint`) for both cases, with tests that a hole between sentences and one inside a sentence name the right fix

## 3. Docs

- [x] 3.1 Update `short-form-pro` SKILL.md (false starts and holes in plans)
- [x] 3.2 Update CLAUDE.md, "Transcription: local first", for stretched words and `breaks`

## 4. Verification

- [x] 4.1 Run the full engine test suite
- [x] 4.2 Under `footage/` (gitignored), transcribe the take from the design's Context in the Linux image: no `untranscribed` left, one `restarts` entry, and the false start its own flagged sentence
- [x] 4.3 Compare the numbered sentences of two other real takes before and after: list every change and confirm none is a wrong restart
- [x] 4.4 Build and render a preview from a plan that keeps the sentences around the false start: read stills at each cut, `preview_qa` passes, the false start's words aren't in the preview, and loudness is -14 LUFS
