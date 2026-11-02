# Proposal

## Why

Every short-form edit, the user's approved local ones included, ends up as cards floating above the speaker's head. The cause is the render path. `shortform` builds the speaker footage in ffmpeg, and Remotion only paints a transparent overlay on top. So a graphic can never move, shrink, reframe or cut out the speaker.

Those are exactly the motion-graphics moves published talking-head catalogues are built on:
- text behind the person while the shot pulls back;
- the speaker moving aside for a screen;
- a card over the shoulder;
- a layout that changes with the story.

Sources: Takes' 28-effect library, Envato's short-form motion guide, and VibeRoll's b-roll guide (`video-studio/docs/editing-references.md`).

A prototype on 2026-11-02 put the footage inside the Remotion composition and drove it from a data plan. It was run on two of the user's videos (a product-launch story and a skills explainer) with the same components and no per-video code. The user approved the result: "ahora sí".

## What Changes

- **The shortform frame is composed in Remotion.** ffmpeg still cuts and concatenates the footage (`base`) and mixes the audio. The composition then draws everything in one place: the base video, a cut-out of the speaker, the events and the captions. It writes the output frames directly. The separate overlay and behind-the-speaker intermediates go away for shortform.
- **A camera in the spec.** `camera: [{kind, start, end, amount?}]`, with times in seconds or word anchors. There are four moves:
  - `push` (slow push-in, ≤ 8 %);
  - `pull` (the shot shrinks to 80 % on a dark backdrop, with rounded corners);
  - `side` (zoom 1.3× with the speaker reframed to the left third, leaving the wall free on the right);
  - `corner` (the speaker shrinks to a 30 % bubble at the bottom right while a panel takes the frame).
  Moves don't overlap.
  **No split screen.** It was built and shown, and the user rejected it: cutting the speaker in half to give a component half the frame is too invasive.
- **Layers.** Every event gets a `layer`:
  - `front` (today's overlays);
  - `behind` (drawn between the footage and the speaker's cut-out, so the speaker covers it);
  - `panel` (under the footage, shown by a `corner` move).
- **Nine components**, with schemas:
  - `Stickers`: key words popping in on their spoken beat;
  - `BehindWord`: a large word rising behind the head, optionally struck through;
  - `DocCard`: a recurring story object with fill, tag and pulse;
  - `StageDrawer`: a card falling into a drawer at the bottom of the frame (named apart from the engine's existing `Drawer`, which is unchanged);
  - `PhonePanel`: real screens in a phone, for `side` and `corner`;
  - `CodePanel`: a code window typing itself, placeable behind the speaker;
  - `Gauge`: a dial whose needle slams to red, with a stamp;
  - `Stuck`: a progress bar that stalls;
  - `Notice`: a phone notification quoting what the speaker reports.
- **Recurring objects.** Events can share an `object` id. The engine keeps their content identical, and `check` lists where each object appears. In the launch video, the thesis card comes back four times as the thread of the story.
- **The low moment as a segment look.** `look: "low"` makes one short segment black and white with added contrast, and an optional freeze of 0.3–0.5 s. The voice gets one low-pass at about 2.4 kHz, a high-pass at about 220 Hz, a light short echo and a level make-up. That segment's `zoom` is static. It is optional, and at most one per video.
  The first prototype stacked two 1.1 kHz low-passes. The user rejected it as unclear and too muffled, so the voice must stay intelligible.
- **Captions place themselves.** While a `corner` move is on, captions turn ink and move above the bubble. Emphasis is dropped for words that a `Stickers` or `BehindWord` event already shows.
- **Speaker cut-out only where it's needed.** The person matte is made for the `behind` events' windows only, plus 0.1 s on each side (windows that touch are merged).

Out of scope:
- Deciding which device fits which line: that's `edit-plans` (the plan compiler) and, above it, the user's or operator's Claude.
- Render speed beyond what this change measures. `faster-preview-render` stays a separate change: its concurrency half still applies, but its overlay-size half has no overlay to resize once shortform renders on the stage.
- Split screen (rejected), stock b-roll and generated b-roll.

## Capabilities

### New Capabilities

- `live-stage`: the composed frame, the camera, the layers, the cut-out speaker, and recurring objects.

### Modified Capabilities

- `shortform-spec`:
  - `camera` and event `layer` in the spec;
  - the `low` look;
  - render produces the frame from the stage;
  - caption placement follows the camera.
- `overlay-schema`: the nine components and their schemas, and the `layer` and `object` shared event props.
- `person-matte`: mattes for windows of the cut base, not only for full takes.

## Impact

- Code:
  - `tools/shortform.py`: render path, matte windows, removal of the overlay and behind compositing for shortform;
  - `tools/short_spec.py`: camera, layers, objects and the low look, validated;
  - `tools/motion/src/`: a `Stage` composition and the nine components, from `prototype/Live.tsx`;
  - `tools/overlay_schema.py`;
  - `tools/person_matte.py`.
- Tests:
  - `tools/tests/test_short_spec.py`: camera validation and overlap, layers, the low look;
  - a stage render smoke test on a 5 s fixture.
- Skills: `short-form-pro` SKILL.md (camera and layers, what each device is for, and that none is required). CLAUDE.md: shortform renders on the stage.
- Workflows: `short-form-pro` changes render path; `video-use` and `motion-graphics` are unaffected (`Story` keeps its own composition).
- **Render time.** On the 32 GB M-series Mac, the 68 s launch preview rendered in 59 s at concurrency 6 (720x1280). In the engine image with `--cpus=4`, the same preview took 165 s (concurrency 2), 145 s (3) and 143 s (4); native on the Mac, 101 s.
- **Disk.** The speaker cut-out is ProRes 4444 with alpha, about 30 MB per second at 720p. It is written for `behind` windows only.
- No new dependencies. `remotion`'s `OffthreadVideo` is already in the pinned 4.0.535; the licence is unchanged (company licence still needed before charging, as today).
- **BREAKING** for callers that read `overlay.mov` or `overlay_behind_*.mov` after a shortform render: those files are no longer written.
- Depends on `strict-edit-faults` (the never-list exempts `behind` text that the speaker covers).
