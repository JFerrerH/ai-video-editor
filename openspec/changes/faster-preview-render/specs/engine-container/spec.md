# Spec Delta

## ADDED Requirements

### Requirement: Render concurrency follows the CPU quota
Every Remotion video render SHALL pass an explicit concurrency. By default it SHALL be derived from the CPUs the process may use (the cgroup CPU quota when one is set, else the CPU count), never above that number and never below 1. `ENGINE_RENDER_CONCURRENCY` SHALL override it with a positive whole number.

#### Scenario: Container limited to 4 CPUs on a larger host
- **WHEN** a short-form render (the Remotion stage) runs in the engine image with `docker run --cpus=4` on a host with more than 4 cores
- **THEN** the Remotion render command line carries a `--concurrency` value of at most 4

#### Scenario: Override
- **WHEN** `ENGINE_RENDER_CONCURRENCY=2` is set and a short-form or storyboard video render runs
- **THEN** each Remotion render command line carries `--concurrency=2`

#### Scenario: Invalid override
- **WHEN** `ENGINE_RENDER_CONCURRENCY` is `0`, negative or not a whole number
- **THEN** the render stops before starting Remotion with an error naming `ENGINE_RENDER_CONCURRENCY` and the value it got

#### Scenario: No quota
- **WHEN** a render runs with no cgroup CPU quota (a Mac, or a container without `--cpus`)
- **THEN** the default concurrency is derived from the machine's CPU count
