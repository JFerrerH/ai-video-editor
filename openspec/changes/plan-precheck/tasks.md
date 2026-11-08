# Tasks

## 1. Module

- [x] 1.1 Tests first: an echo plan, an entrance that doesn't fit, a kept false start and a no-pause cut give the same errors from the precheck and from `plan_build`
- [x] 1.2 `tools/plan_precheck.py`: move the timing pass of `build` into `compile_times` and call it from `build` (D1)
- [x] 1.3 Echo as a pure function shared with `shortform` (D2)
- [x] 1.4 No-pause cuts from word times (D3)
- [x] 1.5 The import test (D4) and op `plan_precheck` in `run_job.py`

## 2. Docs

- [x] 2.1 `short-form-pro` SKILL.md and CLAUDE.md (op list)

## 3. Verification

- [x] 3.1 Full engine test suite; the precheck's time on a 50 s plan (target under 0.5 s)
- [x] 3.2 Under `footage/` (gitignored), on approved plans of real projects (no recorded hosted session was available): `plan_build` writes the same `short.json` as before the change, byte for byte, which renders and measures -14 LUFS; the precheck's timing errors can differ from the build's (word-time clock), which is why the build recomputes them from the audio (design D1)
