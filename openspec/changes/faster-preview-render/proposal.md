# Proposal

## Why

A short-form preview takes about 4–5× the video's length to render on a 4-vCPU Linux worker (340–386 s for a 76 s short), and most of that time goes to the Remotion overlay. The overlay is always rendered at 1080x1920 in ProRes 4444 with PNG frames, even for a 720x1280 preview, where ffmpeg then scales it down. On top of that, Remotion picks its own render concurrency, and inside a CPU-limited container it may count the host's cores instead of the CPUs the container is actually allowed to use.

## What Changes

- `tools/shortform.py render --preview` renders the Remotion overlay, and every behind-the-speaker layer, directly at the preview size (720x1280, Remotion `--scale` of 2/3) instead of 1080x1920. The final render stays at 1080x1920, unchanged.
- Overlay files are kept per size. A preview never reuses a 1080 overlay it would have to scale down, and, more importantly, a final never reuses a 720 overlay it would have to scale up (`skip_overlay` in `build.py` / `templates/shortform_build.py` / `templates/character_build.py` keeps working, per size).
- Every Remotion video render (`shortform.py` overlays and `storyboard.py` renders) passes an explicit `--concurrency`. By default it comes from the CPUs the process is allowed to use: the cgroup CPU quota on Linux, else the CPU count. `ENGINE_RENDER_CONCURRENCY` overrides it.
- A timing measurement on the engine Docker image limited to 4 CPUs (`docker run --cpus=4`) compares concurrency 2, 3 and 4 on a pilot short, and its result sets the default.

Out of scope:
- Final (1080x1920) output quality and pixels: unchanged.
- Preview stills (`stills`, already 540x960 via `--scale=0.5`) and storyboard stills.
- Storyboard (`motion-graphics`) preview size: only its concurrency changes.
- Codec choices for the overlay intermediate (ProRes 4444 / PNG stay as they are). A lighter intermediate is a possible later change.
- GPU rendering and any infrastructure sizing (that lives in the product that runs the engine).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shortform-spec`: adds requirements that the preview overlay is rendered at the preview size and that overlay reuse never crosses sizes. "Render matches build.py" (preview 720x1280, final 1080x1920, −14 LUFS) still holds as written.
- `engine-container`: adds a requirement that Remotion renders use a concurrency bounded by the container's CPU quota, overridable by `ENGINE_RENDER_CONCURRENCY`.

## Impact

- Code: `tools/shortform.py` (`render_overlay`, `render_behind`, `build`), `tools/storyboard.py` (`_remotion` render calls), a small shared helper for the concurrency value. Tests in `tools/tests/test_short_spec.py` (command lines and cache naming, no rendering).
- Skills and docs: `short-form-pro` SKILL.md (overlay files per size, preview vs final), CLAUDE.md "Linux / Docker" section (`ENGINE_RENDER_CONCURRENCY`).
- Workflows: `short-form-pro` previews get faster. `video-use` is unaffected. `motion-graphics` only gets the concurrency flag.
- Preview output is no longer byte-identical to previews from earlier engine versions (text edges are drawn at 720 instead of being scaled down from 1080). Final output is byte-identical apart from concurrency, which does not change frames.
- No new dependencies, models or paid services.
