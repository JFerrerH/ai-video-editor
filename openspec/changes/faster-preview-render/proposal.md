# Proposal

## Why

A short-form preview takes about 4–5× the video's length to render on a 4-vCPU Linux worker, and almost all of that is the Remotion render. Remotion picks its own render concurrency, and inside a CPU-limited container it may count the host's cores instead of the CPUs the container is actually allowed to use.

Since `live-stage` (v0.7.0), shortform draws every frame on the Remotion `Stage`, and previews already render at exactly 720x1280 (`--scale` of 2/3). The overlay-size half of this change's first draft is gone with the overlay files it targeted; the concurrency half remains.

## What Changes

- Every Remotion video render passes an explicit `--concurrency`: the short-form stage render (`ShortForm.render_stage`, which today reads `ENGINE_RENDER_CONCURRENCY` without validating it and has no default) and the storyboard renders (`Storyboard._remotion`).
- By default the value comes from the CPUs the process is allowed to use: the cgroup CPU quota on Linux, else the CPU count. `ENGINE_RENDER_CONCURRENCY` overrides it and is validated (a whole number of 1 or more).
- The default rule is set from a measurement already taken in `live-stage` (the 68 s launch preview on the engine image with `--cpus=4`: 165 s at concurrency 2, 145 s at 3, 143 s at 4; native Mac 101 s), plus one peak-memory check.

Out of scope:
- Preview overlay size and overlay-file reuse: dropped. Shortform writes no `overlay.mov` or `overlay_behind_*.mov` since v0.7.0, and the stage already renders previews at 720x1280.
- Final (1080x1920) output quality and pixels.
- Stills (`stills`, storyboard stills): concurrency does not apply to one frame.
- Storyboard preview size.
- GPU rendering and infrastructure sizing (that lives in the product that runs the engine).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engine-container`: adds a requirement that Remotion renders use a concurrency bounded by the container's CPU quota, overridable by `ENGINE_RENDER_CONCURRENCY`.

## Impact

- Code: `tools/shortform.py` (`render_concurrency()`, `render_stage`), `tools/storyboard.py` (`_remotion` render calls). Tests in `tools/tests/test_short_spec.py` (command lines, no rendering).
- Docs: CLAUDE.md "Linux / Docker" section (`ENGINE_RENDER_CONCURRENCY`); `tools/motion/README.md` already mentions the variable and needs the default rule.
- Workflows: `short-form-pro` previews may get faster inside CPU-limited containers; `motion-graphics` only gets the concurrency flag. `video-use` is unaffected.
- Output pixels are unchanged: concurrency does not change frames.
- No new dependencies, models or paid services.
