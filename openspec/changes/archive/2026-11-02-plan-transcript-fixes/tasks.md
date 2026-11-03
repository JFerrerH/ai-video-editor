## 1. Restarts

- [x] 1.1 `transcribe_local.mark_restarts`: the repeat comes at most 2 words after the abandoned phrase. Tests
- [x] 1.2 `edit_plan._mark_restarts`: the same rule. Tests

- [x] 1.3 `transcribe_local.audible`: a stretch more than 12 dB under the take's speech isn't listed as `untranscribed`. Tests

## 2. Plans

- [x] 2.1 `order` on `plan_ids` and `plan_build`. Tests
- [x] 2.2 `captions.fixes` in a plan. Tests
- [x] 2.3 SKILL.md: pacing text, `captions`
- [x] 2.4 The entrances error: two decimals, and the fix of starting the beat earlier

## 3. Verification

- [x] 3.1 Unit tests and `openspec validate`
- [x] 3.2 In `video-studio`, `scripts/replay_edits.py`: the approved launch plan passes on a fresh transcript, and the pilot false start is still refused
