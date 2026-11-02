# Tasks

## 1. Render concurrency

- [ ] 1.1 Add `render_concurrency()` to `tools/shortform.py` (design D3: `ENGINE_RENDER_CONCURRENCY` override validated to an integer of 1 or more, else `ToolError` naming it; cgroup v2 `cpu.max` quota; `os.cpu_count()` fallback). Verify with unit tests in `tools/tests/test_short_spec.py`: override `2` → 2; `0`, `-1` and `abc` → error naming the variable and value; a fake `cpu.max` of `400000 100000` → 4; `max 100000` and a missing file → `os.cpu_count()`.
- [ ] 1.2 Pass `--concurrency=<n>` on every `remotion render` call: `ShortForm.render_overlay`, `ShortForm.render_behind`, and `Storyboard._remotion` when its first arg is `render`. Leave `remotion still` and `bundle` calls alone. Verify with tests that patch `run` and assert the flag on overlay, behind-layer and storyboard render command lines and its absence on still commands.
- [ ] 1.3 Print the overlay's render seconds after "rendering Remotion overlay…" (`  overlay: <s> s at concurrency <n>, <w>x<h>`). Verify the line appears in a local `shortform.py render --preview` run of a pilot short.
- [ ] 1.4 Document `ENGINE_RENDER_CONCURRENCY` (default rule and override) in CLAUDE.md "Linux / Docker". Verify the documented `docker run -e ENGINE_RENDER_CONCURRENCY=2 …` line puts `--concurrency=2` in the render command.

## 2. Preview overlay at preview size

- [ ] 2.1 In `ShortForm.build`, `render_overlay` and `render_behind`, render at `--scale=0.6666666666666666` when `preview`, write to `overlay_720.mov` / `overlay_behind_<k>_720.mov`, and keep the final's names (`overlay.mov` / `overlay_behind_<k>.mov`) at 1080x1920 (design D1, D2). After each overlay render, `ffprobe` the file and raise if it is not the expected size. Verify with tests patching `run`: preview commands carry the scale and the `_720` names, final commands carry neither.
- [ ] 2.2 Make `skip_overlay` reuse only the file for its own size. Verify with tests for the three spec scenarios: final after preview re-renders at 1080 and keeps `overlay_720.mov`; preview after final renders `overlay_720.mov`; preview after preview with `skip_overlay` runs no overlay render.
- [ ] 2.3 Update the `overlay.mov` comment in `build` and the `short-form-pro` SKILL.md lines that say ffmpeg scales the overlay for previews (around line 260), plus the files table (overlay files per size; a final never reuses a preview overlay). Verify by grepping SKILL.md and `tools/shortform.py` for "same 1080p render" and "scales it for previews": no matches remain.

## 3. Measurement and verification

- [ ] 3.1 Build the engine image for amd64 and render a pilot short under `footage/` (gitignored, at least 60 s, with captions, at least three overlay events and one `behind` event) as a preview with `docker run --cpus=4 --memory=8g`, at `ENGINE_RENDER_CONCURRENCY` 2, 3 and 4, and once on the previous engine tag (old default, 1080 overlay). Record overlay seconds, total render seconds and peak memory (`docker stats`) in a table in this change's `design.md`. Set the default rule in `render_concurrency()` to the fastest setting that stays under 7 GiB peak, and update the test from 1.1 to match.
- [ ] 3.2 On the same pilot, `ffprobe` the preview (720x1280), the preview overlay (720x1280) and the final (1080x1920), and measure the final at -14 LUFS (±0.5) with `loudness()`. Extract stills at each overlay event's still time from the new preview and from the previous tag's preview, compare the overlay area (PSNR ≥ 35 dB), and read the PNGs to check that captions and overlay text are legible. Record the numbers in `design.md`.
- [ ] 3.3 Render the final on the new and previous tags with the same concurrency and confirm the stills at each segment's midpoint match (PSNR ≥ 40 dB), so the final is unchanged. Run the full test suite (`uv run python -m unittest discover tools/tests`) and `npx tsc --noEmit` in `tools/motion` (no Remotion code changes expected, so it should pass as before).

## Workflow follow-up

- Confirm the `short-form-pro` SKILL.md and CLAUDE.md reflect the shipped behaviour, then archive the change.
- Tag a new engine release. The product that pins the engine bumps the pin, regenerates any byte-identical preview references, and measures preview time on its hosted 4-vCPU worker.
