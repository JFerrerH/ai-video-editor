# storyboard-video Specification

## Purpose

Make a video with no footage from one data file, `edit/storyboard.json`: scenes rendered by the
Remotion `Story` composition, joined by transitions, with a mixed and loudness-normalised soundtrack,
in any delivery aspect. Engine: `tools/storyboard.py`. Craft rules: the `motion-graphics` skill.

## Requirements

### Requirement: Aspect-aware frame

The system SHALL render a storyboard at the frame size of its `aspect` (`9:16` → 1080x1920,
`16:9` → 1920x1080, `1:1` → 1080x1080, `4:5` → 1080x1350) and its `fps` (default 30). It SHALL reject
any other aspect.

#### Scenario: Wide storyboard

- **WHEN** a storyboard has `"aspect": "16:9"` and is rendered
- **THEN** the output video is 1920x1080 at the storyboard's fps

#### Scenario: Unknown aspect

- **WHEN** a storyboard has `"aspect": "3:2"`
- **THEN** `tools/storyboard.py` exits with an error naming the allowed aspects

### Requirement: Transition-aware timeline

A scene's `transition` SHALL lead into that scene and overlap both neighbouring scenes. Scene `i`
SHALL start at `start(i-1) + frames(i-1) - transitionFrames(i)`. The total SHALL be the sum of scene
frames minus the sum of transition frames. The Python engine and the Remotion composition SHALL
compute the same frames.

#### Scenario: Rendered duration matches the plan

- **WHEN** a storyboard is rendered
- **THEN** the rendered MP4's duration equals the total that `check` prints, to the frame

#### Scenario: Transition longer than a neighbour

- **WHEN** a transition is as long as, or longer than, either neighbouring scene
- **THEN** `check` reports an ERROR and `stills`/`render` refuse to run

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

### Requirement: Craft checks

`check` SHALL print the timeline (start, duration, type, tone, transition per scene) and warn when:
on-screen text needs more than the scene's duration to read (0.8 s + 4 words/s), narration needs more
than the scene's duration (2.6 words/s), a scene is longer than 7 s, two SFX are less than 0.3 s apart
(typing excepted), or an event runs past the end. It SHALL report an ERROR for a missing asset, voice,
music file or SFX.

#### Scenario: Text too long for its scene

- **WHEN** a 2.0 s scene shows 12 on-screen words
- **THEN** `check` prints a WARN with the reading time it needs

#### Scenario: Missing image

- **WHEN** an `ImageScene` `src` exists neither under the edit dir nor under the repo root
- **THEN** `check` reports an ERROR naming the path

### Requirement: Asset staging

Asset paths in scene and event props SHALL be resolved relative to the edit dir first, then the repo
root, and copied into `edit/motion_public/` at the same relative path, together with the brand's font
files.

#### Scenario: Shared asset

- **WHEN** a scene references `assets/…/image.png` that exists only under the repo root
- **THEN** the file is staged to `edit/motion_public/assets/…/image.png` and renders

### Requirement: Contact sheet

`stills` SHALL render a frame of each scene once it has settled, plus the midpoint of each transition
(or the times given with `--at`), and write one labelled contact sheet to `edit/stills/contact.png`.

#### Scenario: Default stills

- **WHEN** `stills` runs on a storyboard with 5 scenes and 4 transitions
- **THEN** `edit/stills/contact.png` holds 9 labelled frames

### Requirement: Soundtrack and loudness

`render` SHALL mix the voice (offset by `voice_start`), the music bed (looped, faded, and ducked under
the voice unless `duck` is false) and attack-aligned SFX (scene SFX relative to the scene start, audio
SFX absolute). When there is voice or music, it SHALL normalise to `lufs` (default -14) with a true
peak ≤ -1.5 dBTP, and print the measured integrated loudness and true peak. With no audio sources, the
output SHALL carry a silent track.

#### Scenario: Music-only video

- **WHEN** a storyboard has a music bed and SFX but no voice
- **THEN** the output measures -14 ±0.5 LUFS integrated, and `render` prints the loudness numbers

### Requirement: Preview and delivery

`render --preview` SHALL write `edit/preview.mp4` scaled to 720 px on the short side. `render` without
`--preview` SHALL write `edit/final.mp4` at full resolution, from a ProRes intermediate with the
delivery H.264 settings and a 1 s GOP at the storyboard's fps. `--export <platform>` SHALL copy the
result to `exports/<project>_<platform>_<YYYYMMDD>.mp4`.

#### Scenario: Vertical preview

- **WHEN** a 9:16 storyboard is rendered with `--preview`
- **THEN** `edit/preview.mp4` is 720x1280

### Requirement: Narration voice

When a storyboard has a `voice` block (`lang`, `preset`, optional `speed`), every scene with
`narration` and no `narration_audio` SHALL get a synthesised clip under `edit/audio/narration/`,
made by a `voice` command. A scene's `narration_audio` (a recorded clip) SHALL be used as is. Without
a `voice` block, `narration` SHALL stay a planning field, as today.

#### Scenario: Clips per scene

- **WHEN** `voice` runs on a storyboard with a `voice` block and 6 narrated scenes
- **THEN** 6 WAV clips with sidecars exist under `edit/audio/narration/`, and a second run reports all 6 as cached

#### Scenario: No voice block

- **WHEN** a storyboard without a `voice` block has `narration` text
- **THEN** `check`, `stills` and `render` behave as before and no narration clip is made

### Requirement: Narration-driven duration

A narrated scene whose `duration` is omitted or `"auto"` SHALL last its transition-in time plus its
clip's duration plus a tail (`tail`, default 0.3 s). Its clip SHALL start when the scene's
transition-in ends. A fixed `duration` shorter than that SHALL be a `check` ERROR.

#### Scenario: Auto duration

- **WHEN** a scene with a hard cut has a 2.10 s clip and no `duration`
- **THEN** `check` prints a duration of 2.40 s for it

#### Scenario: Fixed duration too short

- **WHEN** a scene fixes `duration: 1.5` and its clip is 2.1 s
- **THEN** `check` reports an ERROR naming the scene and the 2.4 s it needs

### Requirement: Narration track

`render` SHALL place every narration clip at its scene's voice start on one track and use it as the
voice in the existing mix (ducking, SFX, loudness). A storyboard with both narration clips and
`audio.voice` SHALL be a `check` ERROR.

#### Scenario: Clips on time

- **WHEN** a narrated storyboard is rendered
- **THEN** the onset of each clip in `edit/audio/narration_track.wav` (first sample above -40 dBFS) is within 1 frame of its scene's voice start printed by `check`

#### Scenario: Two voice sources

- **WHEN** a storyboard sets `audio.voice` and also has a `voice` block with narrated scenes
- **THEN** `check` reports an ERROR asking for one voice source

### Requirement: Word timing

For every narration clip the engine SHALL produce word times (seconds from the scene start) whose
words are exactly the script's words in order, with `*` and `|` marks stripped but punctuation kept.
The times SHALL come from local speech recognition aligned to the script. They SHALL be cached per
clip, and `check` SHALL print the number of words aligned per scene.

#### Scenario: Script words preserved

- **WHEN** a clip for "Ship it in *one day.*" is timed
- **THEN** its word list is `Ship`, `it`, `in`, `one`, `day.` (emphasis flagged on the last two), with strictly increasing times inside the clip's span

#### Scenario: Recogniser misses a word

- **WHEN** speech recognition drops or misspells one word of a line
- **THEN** that word still appears in the list, with a time between its neighbours' times

### Requirement: Word cues

Any time value in a scene's props, pose list or `sfx` SHALL accept `"@word"` (first occurrence of
that word in the scene's narration, case- and punctuation-insensitive), `"@word#n"` (its n-th
occurrence) or `"@word+0.2"` (plus an offset in seconds). The engine SHALL resolve cues to seconds
before rendering. A cue that matches no word SHALL be a `check` ERROR naming the scene and the
cue.

#### Scenario: Widget on a cue

- **WHEN** a widget has `"at": "@users"` and "users" is spoken 1.12 s after its scene starts
- **THEN** the props written for the render have `at: 1.12`

#### Scenario: Missing cue word

- **WHEN** a scene uses `"@revenue"` and its narration does not contain that word
- **THEN** `check` reports an ERROR naming the scene and `@revenue`

### Requirement: Voice checks

`check` SHALL report an ERROR when the `voice` block's language isn't supported or its preset doesn't
belong to that language, and when a narrated scene's clip is missing or stale (its sidecar no longer
matches the text or voice). Each such ERROR SHALL say to run `voice`.

#### Scenario: Edited line

- **WHEN** a narration line is edited after `voice` ran
- **THEN** `check` reports an ERROR for that scene saying to run `voice`, and `stills`/`render` refuse to run

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
