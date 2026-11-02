## 1. Spec and validation

- [x] 1.1 `short_spec.py`: `camera` (kinds, no overlap, `push` ≤ 0.08, word-anchored times), event `layer`, `object` identity check, `look: "low"` with `freeze`, and its limits. Failing tests first, one per scenario in `specs/`
- [x] 1.2 `overlay_schema.py`: the nine component schemas and the shared props; `--export` updated

## 2. Components

- [x] 2.1 Port `prototype/Live.tsx` into `tools/motion/src/stage/`: the camera function, `Stage` composition, layers, and the components under `components/` with `*.schema.json`. Brand colours and fonts come from `useBrand`. `npx tsc --noEmit` clean
- [x] 2.2 Contrast matrix (from `strict-edit-faults` D7) extended to the nine components

## 3. Render path

- [x] 3.1 `shortform.py`: render the `Stage` composition from base and mix (preview at 720x1280, final at 1080x1920). Stop writing `overlay.mov` and `overlay_behind_*.mov` for shortform
- [x] 3.2 `person_matte.py`: matte windows on the cut base (padded, merged); the cut-out as ProRes 4444 alpha, deleted after render
- [x] 3.3 `look: "low"` in `_vf` and the mix (D6), replacing `prototype/post.py`
- [x] 3.4 Caption `avoid`/`lightRanges` from the camera; emphasis dropped under word-synced devices (D8)
- [x] 3.5 `stills` renders stage frames, so the probe and never-list checks see the real frame (D9)

## 4. Docs

- [x] 4.1 `short-form-pro` SKILL.md: camera, layers and objects; what each device suits; split screen not available and why; no device is required. CLAUDE.md: shortform renders on the stage

## 5. Verification

- [x] 5.1 Timing on the engine Docker image with `--cpus=4`: the launch preview (68 s), concurrency 2, 3 and 4. Record the times here and in the proposal's Impact
  - Measured (arm64 container on the M-series Mac, `ENGINE_RENDER_CONCURRENCY`): 165 s at 2, 145 s at 3, 143 s at 4 (2.1–2.4x real time); the Mac itself, native: 101 s (launch) and 108 s (habilidades, 85 s).
- [x] 5.2 Re-render `footage/xp-launch` and `footage/xp-habilidades` from their prototype plans, written as specs: compare frame by frame with the approved prototype renders; −14 ±1 LUFS; the low line recognised by re-transcription
- [x] 5.3 Full test suite green; tag the release
