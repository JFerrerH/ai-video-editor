# Design

## Context

- `ShortForm.render_stage` runs `remotion render Stage` for every short. It appends `--concurrency=<n>` only when `ENGINE_RENDER_CONCURRENCY` is set, and does not validate the value; with it unset, Remotion 4.0.535 picks its own default from the core count Node reports. On Linux that is the host's cores, not the container's cgroup quota.
- `storyboard.py` renders through `Storyboard._remotion` and passes no concurrency either.
- `storyboard.py` already imports `run`, `MOTION` etc. from `shortform.py`.
- Previews already render at exactly 720x1280 on the stage (`--scale=2/3`); there is no overlay file to resize or reuse (live-stage, v0.7.0).

## Goals / Non-Goals

**Goals:**
- Make render concurrency explicit, predictable inside a container, and tunable without a code change.

**Non-Goals:**
- Changing output pixels, codecs or preview sizes.
- Auto-tuning concurrency at run time: the default is a fixed rule, and measurement only informs it.

## Decisions

**D1. `render_concurrency()` lives in `shortform.py`, next to `run`.**
`storyboard.py` already imports from there. Rule:
1. If `ENGINE_RENDER_CONCURRENCY` is set, it must be an integer of 1 or more, else `ToolError` naming the variable and value.
2. Otherwise CPUs = cgroup v2 `/sys/fs/cgroup/cpu.max` quota÷period (rounded down, at least 1) when present and not `max`, else `os.cpu_count()`.
3. The default is `max(1, CPUs)`: the measurement below shows concurrency 3 and 4 within 2 s of each other on 4 CPUs, and 2 clearly slower, so no smaller share is worth a rule.

Only `remotion render` gets the flag (`render_stage`, `Storyboard._remotion` when its first argument is `render`). `remotion still` renders one frame, so concurrency does not apply.
*Alternative:* leave Remotion's default and only document the env var. Rejected: the cgroup blind spot is exactly the container case where previews are slow.

**D2. The measurement was taken in live-stage.**
68 s launch preview on the engine image, `docker run --cpus=4` (arm64 container on an M-series Mac):

| Concurrency | Render time |
|---|---|
| 2 | 165 s |
| 3 | 145 s |
| 4 | 143 s |
| native Mac | 101 s |

Peak memory at the default has not been measured: task 3.1 records it under `--memory=8g` and lowers the default share only if it exceeds 7 GiB. Timings on the hosted worker are measured later by the product that deploys the engine.

## Risks / Trade-offs

- [Too high a concurrency runs out of memory on 8 GiB] → task 3.1 records peak memory (`docker stats`); the default rule caps at the CPU count.
- [cgroup v1 hosts] → not parsed; they fall back to `os.cpu_count()`, and the env override covers them.
- [An invalid `ENGINE_RENDER_CONCURRENCY` that worked before] → `render_stage` accepted any string; it now stops with an error naming the variable and value, which is the point of the validation.

## Migration Plan

No data migration. Ship as a new engine tag; products pinning the engine bump the pin. Output is unchanged. Rollback: pin the previous tag.

## Open Questions

None. (The default share was an open question in the first draft; the live-stage measurement settles it.)
