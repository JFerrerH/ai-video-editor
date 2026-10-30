# Tasks

## 1. Short-form spec loader and check

- [x] 1.1 Create `tools/short_spec.py` with the field validation from design §2 (unknown fields and wrong types are errors naming the field and index; take names, zoom kinds, looks, preset grades, overlay types from `storyboard.OVERLAY_TYPES`, SFX names from `assets/sfx/synth/`, brand slug exists, size limits, paths confined to the project or `assets/`); add `tools/tests/test_short_spec.py` covering unknown field, outside path, unknown brand, unknown overlay type, missing SFX and the 180 s / 120-segment limits; verify `uv run pytest tools/tests/test_short_spec.py` passes
- [x] 1.2 Add `load()` (validate → `Seg`s → `Project` → `refine_edges()` → resolve anchors → events/SFX, design §1 and §3), with word and segment anchors, offsets, `end` vs `duration`, and zoom `at` anchors; anchor errors name the event index, word and take; unit-test anchor resolution against a small synthetic transcript, checking that a word anchor equals `Project.word()` and a segment anchor equals `offsets()`; verify the tests pass
- [x] 1.3 Add `check` (timeline table, edge report, edge energy, echo and SFX warnings; returns `errors`, `warnings`, `duration`; writes no video) and the `tools/shortform.py` `__main__` (`check|stills|render [spec] [--preview] [--at …]`); verify on a pilot project that `check` exits 0 on a valid spec, non-zero on a spec with a bad SFX name, and no `.mp4`/`.mov` file is created by `check`
- [x] 1.4 Write `templates/short.json` (one source, one segment, one HookTitle, one SFX, neutral text) and make `tools/new_project.py --shortform` write it to `edit/short.json` with the brand filled in (`"none"` when unbranded); verify both `--brand none` and a branded run produce a parseable `edit/short.json` with the right `brand`, and that `edit/build.py` is still written as before

## 2. Source size in the engine

- [x] 2.1 In `tools/shortform.py`, probe each source once (size, aspect, transfer); for SDR 9:16 sources that aren't 1080x1920, prepend `scale=1080:1920` and scale the face centre by `1080/width`; reject landscape, non-9:16 and HLG/PQ sources with a message naming `conform` (design §4); verify a 2160x3840 copy of a pilot take (scaled with ffmpeg) gives a static-zoom still matching the 1080x1920 take's still (PSNR ≥ 35 dB), and that a 1920x1080 source fails `check` with the conform message
- [x] 2.2 Verify Mac parity: render an existing `build.py` pilot before and after 2.1 and confirm identical frame checksums at three cut points (`ffmpeg -ss T -frames:v 1 -f md5`)

## 3. Render and stills from the spec

- [x] 3.1 Wire `render` (preview/final) to `load()` + `Project.build()`; port an existing pilot's `build.py` (under `footage/`, gitignored) to `edit/short.json`; verify both final renders match: duration within one frame, PSNR ≥ 40 dB on stills at each segment midpoint, both at -14 LUFS ±0.5
- [x] 3.2 Implement stills without a full render (design §8: one source frame through the segment's `_vf`, overlay still, composite; behind events with a one-frame matte); verify `stills` with no times writes one PNG per segment in `edit/stills/` (≥ 540x960), that no `final.mp4` is written, and that a still at a caption time shows the caption (Read the PNG)
- [x] 3.3 Update `.claude/skills/short-form-pro/SKILL.md`: `short.json` is how a short is described (shape, anchors, check → stills → preview → final); `build.py` is the escape hatch for one-off code; the source-size rule and when to conform; verify every command the skill shows runs as written on the pilot

## 4. Conform

- [x] 4.1 Create `tools/conform.py` (design §5: `.mov` with H.264 CRF 12 and PCM 48 kHz, autorotate, HLG/PQ tone-map, CFR 24/25/30, `9:16` scale-or-crop and `source` frames, `setpts` to zero, as-is detection, `edit/conformed/conform.json`) with a CLI; verify on an HDR or synthetic HLG 60 fps clip (make one with ffmpeg if no real one is at hand): output 1080x1920, `color_transfer=bt709`, 30 fps constant (`ffprobe` r_frame_rate = avg_frame_rate), duration within one frame, original's checksum unchanged
- [x] 4.2 Verify the transcript timeline survives conform: on a pilot take, the RMS onset of three words in the conformed file matches the original within 20 ms, and a 1080x1920 SDR 30 fps source is recorded `as_is` with no copy written
- [x] 4.3 Verify horizontal crop: conform a 1920x1080 talking-head clip with frame `9:16` using the suggested face; the output is 1080x1920 and a midpoint still (Read it) shows the face within 10% of the frame width from centre

## 5. Planner read-outs

- [x] 5.1 Create the face-centre suggestion (design §6) with a CLI; verify on a selfie take that it returns a point in the upper half of the person with confidence > 0.5 and the same values on a second run, and on a screen recording that it returns `null` with confidence 0
- [x] 5.2 Add source stills and contact sheet (≤ 24 times, ≤ 720 px long side, time label under each frame on the sheet, error on a time past the end); verify three stills plus a sheet appear under `edit/frames/` at the right size and that a past-the-end time fails naming the duration

## 6. Runner ops

- [x] 6.1 Add `conform`, `pack`, `frames`, `face` and `shortform` (`check|stills|render`) to `tools/run_job.py` with schemas per design §9, result fields (`face` centres/confidence, `errors`/`warnings`/`duration`, loudness/true peak on renders) and the docstring/help list; extend `tools/tests/test_run_job.py` for each schema's unknown-argument and outside-path rejection; verify the tests pass and `--help` lists every new op
- [x] 6.2 Add `cut` (`check|render`): EDL whitelist, preset-only grades, confined sources/overlays/subtitles, ranges within probed durations, ≤ 3 h; writes `edit/cut/edl.resolved.json` and calls the vendored `render.py` (design §7); test the raw-filter grade, absolute path and unknown-field rejections, checking that no ffmpeg process starts (monkeypatch `subprocess.run`); verify a three-range EDL from a 1920x1080 conformed take renders 1920x1080 with duration = sum of ranges ±1 frame per range, and that the result reports loudness
- [x] 6.3 Add the "data only" test: a project with `edit/short.json` and an `edit/build.py` that would write a marker file; a `shortform render` job renders and no marker appears; verify the test passes
- [x] 6.4 Check `tools/motion/src` for any HTML injection path (`dangerouslySetInnerHTML`, `eval`, dynamic `import()` driven by props); verify by grep and record the result in design.md's Risks section
- [x] 6.5 Update CLAUDE.md: routing table rows for conform, the validated `cut` op and `short.json`; the "Linux / Docker" section's op list and an example `shortform` job; note that `shortform.build` stays trusted-only while `shortform` is safe for untrusted specs; verify each documented command runs as written

## 7. End-to-end pilot

- [x] 7.1 On the Mac, run the full footage path through the runner only, on a new pilot under `footage/` (gitignored) from a phone-style upload (4K or HLG if available, else a scaled copy): `inventory → conform → transcribe → pack → face → frames → shortform check → stills → render preview → render final`; Read the stills at each cut, check the edge report has no unexplained WARN, and measure the final at -14 LUFS ±0.5 and ≤ -1 dBTP; record timings and numbers in design.md "Verification Notes"
- [x] 7.2 Repeat 7.1 inside the Docker image (`docker build` then `docker run … - < job.json` per step) and run `cut render` on a horizontal take; verify the same checks pass, `--self-check` still exits 0, and record the timings next to the Mac's

## Workflow follow-up

- `/opsx:verify`, then `/opsx:archive` once SKILL.md and CLAUDE.md match what shipped.
- PR to `main`, merge, tag the engine (e.g. `v0.3.0`), then bump the product repo's pin.
