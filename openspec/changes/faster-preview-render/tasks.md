# Tasks

## 1. Render concurrency

- [ ] 1.1 Add `render_concurrency()` to `tools/shortform.py` (design D1: `ENGINE_RENDER_CONCURRENCY` override validated to an integer of 1 or more, else `ToolError` naming it; cgroup v2 `cpu.max` quota; `os.cpu_count()` fallback). Verify with unit tests in `tools/tests/test_short_spec.py`: override `2` → 2; `0`, `-1` and `abc` → error naming the variable and value; a fake `cpu.max` of `400000 100000` → 4; `max 100000` and a missing file → `os.cpu_count()`.
- [ ] 1.2 Pass `--concurrency=<n>` from `render_concurrency()` on every `remotion render` call: replace the bare env read in `ShortForm.render_stage`, and add it to `Storyboard._remotion` when its first arg is `render`. Leave `remotion still` and `bundle` calls alone. Verify with tests that patch `run` and assert the flag on the stage and storyboard render command lines and its absence on still commands.
- [ ] 1.3 Print the render's seconds after "rendering the Remotion stage…" (`  stage: <s> s at concurrency <n>, <w>x<h>`). Verify the line appears in a local `shortform.py render --preview` run of a pilot short.
- [ ] 1.4 Document `ENGINE_RENDER_CONCURRENCY` (default rule and override) in CLAUDE.md "Linux / Docker" and the default rule in `tools/motion/README.md`. Verify the documented `docker run -e ENGINE_RENDER_CONCURRENCY=2 …` line puts `--concurrency=2` in the render command.

## 2. Verification

- [ ] 2.1 On the engine image with `docker run --cpus=4 --memory=8g`, render the launch-style pilot preview at the default and record peak memory (`docker stats`) in `design.md` D2. Lower the default in `render_concurrency()` (and the test from 1.1) only if peak memory exceeds 7 GiB.
- [ ] 2.2 Run the full test suite (`uv run python -m unittest discover tools/tests`) and `npx tsc --noEmit` in `tools/motion`; confirm a preview and a final of a pilot short still measure 720x1280 and 1080x1920 at -14 LUFS (±1), so concurrency changed no frame sizes.

## Workflow follow-up

- Confirm CLAUDE.md reflects the shipped behaviour, then archive the change.
- Tag a new engine release. The product that pins the engine bumps the pin and measures preview time on its hosted 4-vCPU worker.
