# edit-plans Specification

## Purpose
An edit is planned in sentence IDs and words, never seconds: the transcript is numbered, a validated plan says which lines stay and what each moment needs, and a deterministic compiler turns it into a short-form spec that passes strict checks, adding nothing the plan didn't ask for.

## Requirements

### Requirement: Numbered sentences

`plan ids <project>` SHALL print the project's transcript as numbered sentences `F1…Fn`. Each SHALL show its take, start, duration and text, and SHALL be flagged when it is the abandoned half of a likely restart. A sentence SHALL also end before a word that starts at one of the transcript's `breaks`. A transcript with no `breaks` field SHALL be numbered as if the list were empty. Takes SHALL be numbered in the given `order` (any others after them), else in name order. IDs SHALL be the same for the same transcript and order.

#### Scenario: Restart flagged

- **WHEN** a take says "En esa tesis… en esa tesis hablaba de crear" with a 0.5 s pause after the first "tesis"
- **THEN** the abandoned sentence is printed with a restart flag and the next sentence starts at the second "En"

#### Scenario: Sentences that open alike

- **WHEN** a sentence is followed after a pause by a whole other sentence, and then by one with the same first two words
- **THEN** no sentence is flagged

#### Scenario: Take order

- **WHEN** `order` is `["zeta", "alfa"]`
- **THEN** F1 is the first sentence of `zeta`, in `plan_ids` and in `plan_build`

#### Scenario: False start after an unpunctuated line

- **WHEN** a take says "I kept it in a drawer for years" and, 0.7 s later with no punctuation, a phrase it abandons and says again, and `breaks` holds the phrase's start and the restart
- **THEN** the drawer line, the abandoned phrase and the restart are three sentences, only the abandoned one is flagged, and a plan can keep the other two

#### Scenario: Transcript from before breaks

- **WHEN** a transcript has no `breaks` field
- **THEN** its sentence IDs are the same as before this change

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

### Requirement: The build runs the strict stills

Unless told not to, `plan build` SHALL also run `stills --strict` on the compiled spec and leave the stills in `edit/stills`. Any finding the strict stills report (text that doesn't read against the frame, text over the face, text under 28 px) SHALL be an error naming the beat, and `edit/short.json` SHALL NOT be written. An entrance SHALL stay on screen at least 0.3 s before its event ends.

#### Scenario: Text that doesn't read

- **WHEN** a `BehindWord` beat has a colour within 1.3:1 of the wall behind it
- **THEN** the engine gives it the first of the brand's ink, white and black that reads on what is behind it, for the stills and the render. If none does, `plan build` exits non-zero with an error naming the beat and its contrast

### Requirement: Pacing is enforced, never filled

`plan build` SHALL measure the longest stretch with no visual aid on screen (no event and no camera move; cuts don't count) and SHALL report it. Past 5 s it SHALL warn; past 8 s it SHALL be an error naming the stretch, and `edit/short.json` SHALL NOT be written. The compiler SHALL NOT add anything to fill a stretch.

#### Scenario: Nothing to look at

- **WHEN** a plan keeps 18 s of speech and has no beats
- **THEN** `plan build` exits non-zero saying no graphic or camera move is on screen for the whole stretch, and that nothing was added

### Requirement: Caption fixes in a plan

A plan MAY have `captions: {"fixes": {"heard": "said"}}`, which the compiled spec SHALL carry. Anything else under `captions` SHALL be an error, because the other caption fields use seconds.

#### Scenario: Misheard brand

- **WHEN** a plan has `captions: {"fixes": {"Akme": "Acme"}}`
- **THEN** `edit/short.json` has those fixes under `captions`

#### Scenario: Seconds in a caption fix

- **WHEN** a plan has `captions: {"word_fixes": [{"at": 12.4, "text": "x"}]}`
- **THEN** `plan build` exits non-zero naming `plan.captions`

### Requirement: Two graphics never share the screen

The hook SHALL end before the first graphic starts, and a graphic before the CTA SHALL end before the CTA starts. A compiled plan with two floating graphics on screen at once SHALL be refused, naming both. A `Flash` doesn't count, and neither does a full-screen scene, which covers what is under it.

#### Scenario: A graphic two seconds in

- **WHEN** a plan's first graphic starts 2 s into the video and the hook would hold for 3 s
- **THEN** the hook ends before the graphic starts

### Requirement: Kept speech with no words names a plan fix

When `plan_build` is refused because a kept run holds a range of `untranscribed` speech, the error SHALL name the sentences on either side of that range and say to leave one out of `keep`. It SHALL NOT ask for listening or for a cut a plan can't express. When the range sits inside one sentence (a transcript with no `breaks`), the error SHALL say to run the footage's preparation again.

#### Scenario: Hole between two sentences

- **WHEN** a plan keeps F7 and F8 and an `untranscribed` range sits between them
- **THEN** the build is refused with an error naming F7, F8 and the range, saying to leave F7 or F8 out of `keep`, and keeping only F7 passes that check

#### Scenario: Hole inside a sentence of an older transcript

- **WHEN** a plan keeps F7, the transcript has no `breaks`, and an `untranscribed` range sits inside F7
- **THEN** the error names F7 and the range and says to prepare the footage again
