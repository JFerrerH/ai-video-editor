## ADDED Requirements

### Requirement: Two graphics never share the screen

The hook SHALL end before the first graphic starts, and a graphic before the CTA SHALL end before the CTA starts. A compiled plan with two floating graphics on screen at once SHALL be refused, naming both. A `Flash` doesn't count, and neither does a full-screen scene, which covers what is under it.

#### Scenario: A graphic two seconds in

- **WHEN** a plan's first graphic starts 2 s into the video and the hook would hold for 3 s
- **THEN** the hook ends before the graphic starts
