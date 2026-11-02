# Design

## Context

- `ShortForm.build(preview, skip_extract, skip_overlay)` renders one `edit/overlay.mov` for both preview and final ("same 1080p render for preview and final"). It then scales the file to the output size with `scale={w}:{h}:flags=lanczos` in the composite filter. `skip_overlay` reuses whatever `overlay.mov` exists, whatever size it was drawn at.
- `render_behind` does the same for each `props.behind` event (`overlay_behind_<k>.mov`, 1080x1920, scaled in the composite). Mattes are already made at the base size.
- No Remotion call passes `--concurrency`. Remotion 4.0.535 picks its own default from the core count Node reports. On Linux that is the host's cores, not the container's cgroup quota.
- `storyboard.py` imports `run`, `MOTION` etc. from `shortform.py`, and renders through `Storyboard._remotion`.

## Goals / Non-Goals

**Goals:**
- Cut the preview overlay's Remotion work by drawing about 2.25× fewer pixels per frame (720x1280 instead of 1080x1920).
- Make sure a final can never pick up a preview-sized overlay.
- Make render concurrency explicit, predictable inside a container, and tunable without a code change.

**Non-Goals:**
- Changing the final's pixels, the overlay codec, or storyboard preview sizes.
- Auto-tuning concurrency at run time: the default is a fixed rule, and measurement only informs it.

## Decisions

**D1. Preview overlay via Remotion `--scale=2/3`, not a second composition size.**
The Overlay composition stays 1080x1920. Layout, safe boxes, caption placement and `measure_events` boxes all keep their current coordinates. Remotion's `--scale` renders the same layout at 720x1280. The value is passed as the exact ratio string `--scale=0.6666666666666666`, and the render checks the result with `ffprobe` (720x1280, else it raises). The composite still runs `scale={w}:{h}`, which is a no-op at the same size and keeps the filter graph unchanged.
*Alternative:* a separate 720x1280 composition. Rejected: it duplicates layout constants and risks a preview whose layout differs from the final.

**D2. Overlay files named by height.**
Final: `overlay.mov` and `overlay_behind_<k>.mov` (unchanged names, so existing projects' finals still reuse their files). Preview: `overlay_720.mov` and `overlay_behind_<k>_720.mov`. `skip_overlay` looks only at the name for its own size, so a size can never be crossed (spec: "Overlay reuse stays within one size").
*Alternative:* one file plus an `ffprobe` size check before reuse. Rejected: a final followed by a preview would throw away the 1080 file every time, and back-and-forth `build.py` iteration would re-render on every switch.

**D3. `render_concurrency()` lives in `shortform.py`, next to `run`.**
`storyboard.py` already imports from there. Rule:
1. If `ENGINE_RENDER_CONCURRENCY` is set, it must be an integer of 1 or more, else `ToolError` naming the variable and value.
2. Otherwise CPUs = cgroup v2 `/sys/fs/cgroup/cpu.max` quota÷period (rounded down, at least 1) when present and not `max`, else `os.cpu_count()`.
3. The default is `max(1, CPUs)`, unless measurement (task 3) shows a smaller share is faster, in which case the rule becomes that share and the measured table goes in the SKILL.md note.

Only `remotion render` gets the flag. `remotion still` renders one frame, so concurrency does not apply.
*Alternative:* leave Remotion's default and only document the env var. Rejected: the cgroup blind spot is exactly the container case where previews are slow.

**D4. Measurement on the engine image, not on any hosted worker.**
`docker run --cpus=4 --memory=8g` (amd64) reproduces the CPU quota of a 4-vCPU worker. A pilot short (gitignored, under `footage/`) is rendered as a preview at concurrency 2, 3 and 4 and at the old Remotion default. The overlay render seconds come from the existing timing print. The pilot's numbers on the actual hosted worker are measured later by the product that deploys the engine.

## Risks / Trade-offs

- [Text at 720 draws slightly different anti-aliasing than 1080 scaled down with lanczos] → Previews are no longer byte-identical to earlier versions. Verification compares preview stills at each overlay event against a 1080-rendered, lanczos-scaled reference and requires PSNR ≥ 35 dB on the overlay area, plus a visual read of the stills for caption legibility.
- [Remotion `--scale` rounding gives 720x1279 or similar] → the post-render `ffprobe` check raises with the size it got. D1's exact ratio string avoids rounding in practice.
- [Old projects have a 1080 `overlay.mov` and a preview with `skip_overlay`] → the preview renders a fresh 720 file once (D2), which is correct, just not reused.
- [Too high a concurrency runs out of memory on 8 GiB with ProRes 4444] → the measurement records peak memory (`docker stats`), and the default rule caps at the CPU count.
- [cgroup v1 hosts] → not parsed; they fall back to `os.cpu_count()`, and the env override covers them.

## Migration Plan

No data migration. Ship as a new engine tag. Products pinning the engine bump the pin. Any byte-for-byte preview comparison against older outputs must regenerate its reference. Rollback: pin the previous tag. Files named `overlay_720.mov` are ignored by older versions.

## Open Questions

- The exact default share of CPUs (all of them, or fewer) is settled by task 3's numbers. It changes only one constant and the SKILL.md note, not the specs.
