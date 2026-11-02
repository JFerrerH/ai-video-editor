## ADDED Requirements

### Requirement: Plan and QA operations

The fixed operation list SHALL include `plan_ids`, `plan_build` and `preview_qa`, each with validated arguments (the project, and the plan file for `plan_build`). They SHALL return their result as JSON like the other ops: sentences, the build's spec path plus `check` result and pacing report, or QA errors.

#### Scenario: QA through a job

- **WHEN** a job runs `preview_qa` on a project whose preview has a clipped word
- **THEN** the job result has `ok: false` and an `errors` list naming the output time and the fix
