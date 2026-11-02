## 1. Fixtures first

- [ ] 1.1 Plans for `xp-launch` and `xp-habilidades` in the new format, equivalent to the approved prototype renders (kept privately in `video-studio/openspec/changes/edit-plans/prototype-plans/`); the `xp-bad` control as a QA fixture. Failing tests for each scenario in `specs/`

## 2. Plan

- [ ] 2.1 `tools/edit_plan.py ids`: sentences, restart flags (D1)
- [ ] 2.2 Plan schema with export; no seconds anywhere
- [ ] 2.3 `build`: segments by `from`/`to` (needs `strict-edit-faults`), beats to timed events with layers and camera (needs `live-stage`), placement, SFX table with brand bans (D4), caps, pacing report (D5); the result passes `check --strict`

## 3. QA

- [ ] 3.1 `tools/preview_qa.py` from `prototype/qa.py` (D6), using real clip durations and the speech level
- [ ] 3.2 `run_job.py`: `plan_ids`, `plan_build`, `preview_qa` with validated args

## 4. Docs

- [ ] 4.1 `short-form-pro` SKILL.md: "Edit by plan" with the launch and habilidades plans as worked examples; devices are choices, none is required

## 5. Verification

- [ ] 5.1 Compile and render the two approved plans: frame-compare with the prototype renders; `preview_qa` passes; the `xp-bad` control is refused with its three faults
- [ ] 5.2 A third held-out project (`xp-cea`), planned from `plan ids` alone: `check --strict` and `preview_qa` pass. Record the time and rounds
