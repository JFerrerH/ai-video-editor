# Design

## Context

Measured on a real 105 s take with `faster-whisper` large-v3-turbo, in the Linux image at `v0.8.3`. The speaker abandons a sentence at 96.5 s, is silent until 98.7 s, and says it again.

- One word runs 96.48–100.80. It has 3 letters and about half of it is speech, so `implausible` (60%) is false.
- `uncovered` reports 98.78–100.5. The retry of 98.3–101.0 returns the retake's words, but `fill_holes` drops each one because its middle falls inside the stretched word.
- A retry of the stretched word's own window (95.98–101.30) returns the retake, and its first word starts at 96.42, inside the silence.
- With those words merged by hand, `mark_restarts` still returns nothing and the 15.8 s sentence stays whole: the backward walk stops at a 0.5 s pause after a comma, and the line before has no final punctuation and a 0.72 s gap, under `SENT_GAP`.

Each step fails separately, so all of them change.

## Goals / Non-Goals

Goals: this take's false start reaches the plan as its own flagged sentence; a plan always has a fix it can apply; saved plans on prepared projects keep their IDs.

Non-goals: keeping wordless speech on purpose, `keep` by word, changing `SENT_GAP`.

## Decisions

**D1. Widen `implausible`, don't special-case the hole pass.** A word over the length limit that hides at least `MIN_HOLE` of uncovered speech goes down the existing replace path, which already retries its window and keeps the words inside it. Exempting stretched words from `solid` would keep the 98.3–101.0 retry, whose clipped window produced wrong words ("hacerlos más"). A long word over silence hides no speech and stays as it is.

**D2. Snap recovered starts to speech.** Whisper stamps the first word of a window early, and a false 2 s word hides the very pause restart detection needs. A recovered word starting outside a speech run moves to the next run's start, if that falls before its end. Only retried words move: original stamps stay as measured.

**D3. Find the repeat first, then walk back.** `mark_restarts` now takes the two words after the abandoned end and looks back for them, stopping at a sentence end or a pause of 0.8 s or more. The nearest phrase opening wins. The 6 s window still counts from the abandoned end (a real 6 s phrase needs it). Across a pause inside the phrase, two words could be a list ("de mi casa, de mi calle"), so the repeat must run three words or follow a wait of 1 s or more. The abandoned check and the filler limit don't change, so the two "not a restart" scenarios hold.

**D4. `breaks` in the transcript, not computed in `edit_plan`.** Splitting at holes and restarts inside `sentences()` from data old transcripts already hold would renumber them: `plan_build` would disagree with the IDs a hosted service stored at preparation. A field only new transcriptions write gives old transcripts identical IDs, with no version flag. Alternative rejected: lowering `SENT_GAP` renumbers every take.

**D5. The hint lives in `edit_plan` (`_hole_hint`).** `shortform check` keeps its message for people working by hand. `edit_plan` already rewrites check errors into plan terms, so it maps the range to sentences there.

## Risks / Trade-offs

- **A deliberate repetition with a pause may be marked as a restart.** D3 widens matching. The 6 s window, the two-word match and the sentence-end stop bound it, and the existing scenarios stay as tests. A wrong mark refuses one line, with a fix.
- **Lost line.** When a retry fails, leaving the sentence out loses speech. The plan can say so to the user, but it can't keep that speech. Accepted for now; see the proposal's scope.
- **Prepared projects don't improve until prepared again.** That's the price of D4, and the refusal says so.

## Migration Plan

Additive field; no migration. Old transcripts behave as today apart from the refusal text.

## Open Questions

None.
