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

### Requirement: Holds, time props and plan-made cuts

A beat SHALL hold from its word until the end of its `until` sentence (default its own), or of its `through` word in it, for at least 1.5 s and at most 6 s, and SHALL end 0.05 s before the next beat starts. A time prop of a device SHALL be given as `{"word": "…"}`, searched from the beat's word to the end of its hold; a list of entrances left without times SHALL come one after another. A punch-in's sentence and the `low` line SHALL be cuts of their own, and SHALL be refused when either side has less than 0.25 s of pause. A pause of 0.65 s or more inside a kept run SHALL be a jump cut whose frame size alternates.

#### Scenario: Punch-in on a run-on sentence boundary

- **WHEN** a beat has `punch` on a sentence that follows the previous one with 0.1 s of pause
- **THEN** `plan build` exits non-zero saying the cut needs a pause of 0.25 s and to punch in on a sentence that follows a pause

#### Scenario: Hold ends on a word

- **WHEN** a beat has `through` naming a word in a 29 s sentence
- **THEN** its event ends at that word's end, not 6 s after it starts
