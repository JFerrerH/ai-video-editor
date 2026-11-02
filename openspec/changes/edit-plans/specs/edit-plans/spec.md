## ADDED Requirements

### Requirement: Numbered sentences

`plan ids <project>` SHALL print the project's transcript as numbered sentences `F1…Fn`. Each SHALL show its take, start, duration and text, and SHALL be flagged when it is the abandoned half of a likely restart. IDs SHALL be the same for the same transcript.

#### Scenario: Restart flagged

- **WHEN** a take says "En esa tesis… en esa tesis hablaba de crear" with a 0.5 s pause after the first "tesis"
- **THEN** the abandoned sentence is printed with a restart flag and the next sentence starts at the second "En"

### Requirement: Plans contain no seconds

`edit/plan.json` SHALL be validated against the exported plan schema. It SHALL refer to lines only by sentence ID and word. A time in seconds anywhere in it SHALL be an error naming the field.

#### Scenario: Seconds in a beat

- **WHEN** a beat has `"start": 12.4`
- **THEN** `plan build` exits non-zero naming the beat and saying to use a sentence ID and a word

### Requirement: The compiler only executes the plan

`plan build` SHALL produce `edit/short.json` containing:
- the kept sentences as `from`/`to` segments;
- each beat's device at its word's time, with its default layer and camera;
- placement;
- sound effects from the device table.

It SHALL NOT add any event, camera move or look that the plan doesn't ask for. A brand's rejected sound effects and `pluck` SHALL never appear. The result SHALL pass `check --strict`, or `plan build` SHALL fail with `check`'s errors.

#### Scenario: Brand rejects a sound

- **WHEN** the brand notes say "Rejected before: pluck, ding (use click instead)" and a beat's device defaults to a click
- **THEN** the spec uses click, and contains no pluck or ding

#### Scenario: No quota

- **WHEN** a plan has 4 beats in 60 s
- **THEN** the spec has exactly those 4 events plus the hook and CTA, and the pacing report warns about the longest stretch without a visual change

### Requirement: Restraint caps

A plan SHALL be refused when it asks for any of these:
- more than two punch-ins besides the hook;
- more than one `low` look;
- a `low` look in the first 3 s;
- a `low` line longer than 3 s.
The message SHALL name the cap and where the plan exceeds it.

#### Scenario: Two low moments

- **WHEN** a plan has `low` on two sentences
- **THEN** `plan build` exits non-zero saying the low look is used at most once
