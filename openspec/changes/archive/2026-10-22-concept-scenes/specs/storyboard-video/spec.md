# Spec Delta

## MODIFIED Requirements

### Requirement: Scene primitives

The system SHALL provide the scene types `TitleCard`, `KineticType`, `StatScene`, `BarChart`,
`ListScene`, `ImageScene`, `BeatScene`, `NetworkScene`, `IsoOffice` and `EndCard`. Each SHALL lay out
inside the aspect's safe box, take colours from its background tone (`light`, `dark`, `accent`,
`none`), and take fonts from the brand. The 9:16 overlay components SHALL be accepted as scene types
only when the aspect is 9:16.

#### Scenario: Overlay component outside 9:16

- **WHEN** a 16:9 storyboard uses `RingStat` as a scene type
- **THEN** `check` reports an ERROR telling the user to use a scene primitive

#### Scenario: Unknown scene type

- **WHEN** a scene's `type` is neither a scene primitive nor an overlay component
- **THEN** `check` reports an ERROR listing the scene primitives

#### Scenario: BeatScene in every aspect

- **WHEN** a storyboard with a `BeatScene` (headline, figure, one widget) is checked at 9:16, 16:9, 1:1 and 4:5
- **THEN** `check` reports no ERROR for the scene in any of them

## ADDED Requirements

### Requirement: Network scene

`NetworkScene` SHALL draw labelled nodes (each with a colour and optional line icon) and an
optional central hub. It SHALL support these cue-driven behaviours, each timed in seconds from the
scene start or by an `@word` cue:
- `chaos` until a time: nodes drift, with crossing message lines and error marks.
- `connect` at a time: nodes ease into a ring around the hub, and a spoke draws to each node.
- `chips`: a short label pill per node, at a time.
- `messages[{from, to, at, lock}]`: a packet travels from node `from` through the hub (when there is
  one) to node `to`.
- `log[{text, at}]`: lines added to a ticker, newest last, keeping only as many lines as fit.

Node labels and log text SHALL be at least 28 px at 1080 px short side.

#### Scenario: Chaos resolves into a ring

- **WHEN** a 4:5 `NetworkScene` has 6 nodes, a hub, `chaos` until 1.0 s and `connect` at 1.0 s, and stills are taken at 0.5 s and 2.5 s
- **THEN** the 0.5 s still shows nodes off the ring with crossing lines, and the 2.5 s still shows 6 nodes evenly spaced around the hub with a spoke to each, all inside the safe box

#### Scenario: Message travels through the hub

- **WHEN** a message from node A to node B is cued at 3.0 s with `lock: true`
- **THEN** a still shortly after 3.0 s shows a packet with a lock icon on the spoke from A, and a later still shows it on the spoke to B

### Requirement: Isometric office scene

`IsoOffice` SHALL draw an isometric room in flat vector shapes (floor grid, back walls, desks
with monitors). It SHALL place `agents[{id, label, color, at, pos}]` as block-built characters with a
mono label, move them along `walks[{agent, to, at, dur}]` in straight lines on the floor, show
`bubbles[{agent, text|icon, at, until}]` above the agent, draw a carried document while a walk
has `carry: true`, and, for `replay{at, dur}`, show a scrub bar while the scene's clock runs
backwards to an earlier point and then forwards again. All times accept `@word` cues.

#### Scenario: Agent walks to a desk

- **WHEN** an agent at desk 1 walks to desk 3 from 1.0 s over 1.0 s, and stills are taken at 0.9 s and 2.2 s
- **THEN** the agent is at desk 1 in the first still and at desk 3 in the second

#### Scenario: Replay reverses the floor

- **WHEN** a bubble appears at 1.0 s and a `replay` runs from 3.0 s for 1.5 s, rewinding to before 1.0 s
- **THEN** a still in the middle of the rewind shows the scrub bar and no bubble, and a still after the replay shows the bubble again

### Requirement: End card scene

`EndCard` SHALL show a logo image from a file path, then `title`, `tagline`, a CTA pill
(`button`) with an arrow, and `url`, entering in that order, on the scene's tone. The logo SHALL
spring in. A missing logo file SHALL be a `check` ERROR (like any asset).

#### Scenario: End card settles in reading order

- **WHEN** an `EndCard` with logo, title, tagline, button and url is rendered and stills are taken at 0.2 s and 1.5 s
- **THEN** the 0.2 s still shows the logo but no button, and the 1.5 s still shows all five elements inside the safe box

### Requirement: Concept scene validation

`check` SHALL report an ERROR when a `NetworkScene` message names a node id that doesn't exist,
when an `IsoOffice` walk, bubble or carry names an agent id that doesn't exist, when an icon name
is unknown, or when a `replay` window ends after the scene does.

#### Scenario: Message to an unknown node

- **WHEN** a `NetworkScene` message goes to node `"deploy"` and no node has that id
- **THEN** `check` reports an ERROR naming the scene and the missing id, and `stills`/`render` refuse to run
