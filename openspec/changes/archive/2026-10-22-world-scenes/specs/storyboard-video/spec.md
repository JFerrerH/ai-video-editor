# Spec Delta

## MODIFIED Requirements

### Requirement: Scene primitives

The system SHALL provide the scene types `TitleCard`, `KineticType`, `StatScene`, `BarChart`,
`ListScene`, `ImageScene`, `BeatScene`, `NetworkScene`, `IsoOffice`, `EndCard` and `WorldScene`.
Each SHALL lay out inside the aspect's safe box, take colours from its background tone (`light`,
`dark`, `accent`, `none`), and take fonts from the brand. The 9:16 overlay components SHALL be
accepted as scene types only when the aspect is 9:16.

#### Scenario: Overlay component outside 9:16

- **WHEN** a 16:9 storyboard uses `RingStat` as a scene type
- **THEN** `check` reports an ERROR telling the user to use a scene primitive

#### Scenario: Unknown scene type

- **WHEN** a scene's `type` is neither a scene primitive nor an overlay component
- **THEN** `check` reports an ERROR listing the scene primitives

#### Scenario: BeatScene in every aspect

- **WHEN** a storyboard with a `BeatScene` (headline, figure, one widget) is checked at 9:16, 16:9, 1:1 and 4:5
- **THEN** `check` reports no ERROR for the scene in any of them

### Requirement: Contact sheet

`stills` SHALL render a frame of each scene once it has settled, plus the midpoint of each transition
(or the times given with `--at`), and write one labelled contact sheet to `edit/stills/contact.png`.
Beats of a world run SHALL each get their own settled frame, labelled with the beat's name, even
though the run renders as one scene.

#### Scenario: Default stills

- **WHEN** `stills` runs on a storyboard with 5 scenes and 4 transitions
- **THEN** `edit/stills/contact.png` holds 9 labelled frames

#### Scenario: World run beats

- **WHEN** `stills` runs on a storyboard whose only scenes are a world run of 4 beats
- **THEN** `edit/stills/contact.png` holds 4 frames labelled with the 4 beat names
