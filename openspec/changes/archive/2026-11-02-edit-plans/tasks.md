## 1. Fixtures first

- [x] 1.1 Plans for `xp-launch` and `xp-habilidades` in the new format, equivalent to the approved prototype renders (kept privately in `video-studio/openspec/changes/edit-plans/prototype-plans/`); the `xp-bad` control as a QA fixture. Failing tests for each scenario in `specs/`

## 2. Plan

- [x] 2.1 `tools/edit_plan.py ids`: sentences, restart flags (D1)
- [x] 2.2 Plan schema with export; no seconds anywhere
- [x] 2.3 `build`: segments by `from`/`to` (needs `strict-edit-faults`), beats to timed events with layers and camera (needs `live-stage`), placement, SFX table with brand bans (D4), caps, pacing report (D5); the result passes `check --strict`

## 3. QA

- [x] 3.1 `tools/preview_qa.py` from `prototype/qa.py` (D6), using real clip durations and the speech level
- [x] 3.2 `run_job.py`: `plan_ids`, `plan_build`, `preview_qa` with validated args

## 4. Docs

- [x] 4.1 `short-form-pro` SKILL.md: "Edit by plan" with the launch and habilidades plans as worked examples; devices are choices, none is required

## 5. Verification

- [x] 5.1 Compile and render the two approved plans: frame-compare with the prototype renders; `preview_qa` passes; the `xp-bad` control is refused with its three faults
- [x] 5.2 A third held-out project (`xp-cea`), planned from `plan ids` alone: `check --strict` and `preview_qa` pass. Record the time and rounds

### Results (2026-11-02)

- 5.1 (corrected): both plans first passed only `check --strict`, not `stills --strict`; after the review they were reworked (components fixed, plans adjusted) and now pass both, render, and `preview_qa`. Original note: both approved plans compile in the new format and pass `check --strict`. Against the approved renders, every event appears in the same order on the same lines (launch: 18 of 18 events, camera moves of the same kind within 0.5 s; tutorial: 20 of 21, the screenshot flash left out because the sound table has no shutter), at 67.6 s against 68.2 s and 85.4 s against 85.4 s. `preview_qa` passes on both; the `xp-bad` control is refused with its three faults (cut at -7.2 dB, cut at +1.6 dB, a kept word clipped at a cut).
- 5.2: `xp-cea`, planned from `plan ids` alone: 7 plan versions, about 24 minutes from the sentence list to a passing preview, three preview renders. What each round fixed: a `low` line that began without a pause; a cut that ended on a breath (keep the neighbouring sentence); two graphics that echoed spoken words; a `Gauge` whose stamp had no run-up (failed in the render, not in `check`); then `preview_qa` found a cut through a word (-8.1 dB) and a word heard that the transcript had stamped late.

