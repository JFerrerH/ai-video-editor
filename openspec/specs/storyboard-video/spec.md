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
`ListScene` and `ImageScene`. Each SHALL lay out inside the aspect's safe box, take colours from its
background tone (`light`, `dark`, `accent`, `none`), and take fonts from the brand. The 9:16 overlay
components SHALL be accepted as scene types only when the aspect is 9:16.

#### Scenario: Overlay component outside 9:16

- **WHEN** a 16:9 storyboard uses `RingStat` as a scene type
- **THEN** `check` reports an ERROR telling the user to use a scene primitive

#### Scenario: Unknown scene type

- **WHEN** a scene's `type` is neither a scene primitive nor an overlay component
- **THEN** `check` reports an ERROR listing the scene primitives

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
