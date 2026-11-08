## ADDED Requirements

### Requirement: Precheck without audio

`plan_precheck.check(plan, transcripts, order, schemas, brand)` SHALL return every error and warning that needs only the plan, the transcript JSON, the take order, the component schemas and the brand's rejected sounds: plan shape and sentence IDs, false starts, schema limits, beat timing and entrance fit, echo, pacing, and cuts with no pause in the word times.

#### Scenario: Echo found without audio

- **WHEN** a plan's hook title holds three words the captions say in its first second
- **THEN** the precheck returns the echo error with the event and the words, in under a second, with no audio or render

### Requirement: The precheck needs only the standard library

The precheck module SHALL import only the Python standard library and modules that do.

#### Scenario: Imported alone

- **WHEN** the precheck module is imported with only the Python standard library available
- **THEN** the import succeeds

### Requirement: The build runs the precheck first

`plan_build` SHALL run the precheck's checks that do not depend on when anything plays (plan shape, false starts, schema of the plan, cuts the plan makes) before compiling, and stop on their errors with the same messages.

#### Scenario: Same errors both ways

- **WHEN** a plan has an entrance that doesn't fit before the next beat
- **THEN** `plan_precheck` and `plan_build` return the same error, naming the same beat and fix (a measured time may differ by hundredths)

### Requirement: The build measures the timing checks from the audio

`plan_build` SHALL compute the timing checks (entrances that fit, echo, graphics sharing the screen, pacing) with the precheck's own functions on the audio-measured cut, so a plan the audio accepts is never refused for a time only the word-time clock got wrong.

#### Scenario: The word-time clock is only approximate

- **WHEN** the precheck's times (from the transcript's word times) differ from the audio's
- **THEN** `plan_build` still accepts a plan the audio accepts, and the precheck lists the errors that came from timing under `timed_errors`
