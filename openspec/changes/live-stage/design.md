## Context

`shortform.build` today:
1. extracts and concatenates the segments in ffmpeg (`base_*.mov`, with zoom and look per segment);
2. renders the Remotion overlay as a transparent ProRes 4444;
3. for `behind` events, renders an extra layer and a person matte for those windows;
4. stacks them in ffmpeg.

Remotion never sees the footage, so no component can move it.

The 2026-11-02 prototype (`prototype/Live.tsx`; the two plans contain the user's footage text and are kept in the private product repo, `video-studio/openspec/changes/edit-plans/prototype-plans/`) puts the base video inside a Remotion composition. It applies one camera transform to the footage and to the speaker cut-out, and draws `panel`, `behind` and `front` layers around them. It reuses the engine's existing `OverlayLayer` for the old components and `Captions`.

## Goals / Non-goals

Goals:
- Graphics that move the speaker.
- One composited frame.
- The old components unchanged.
- The same output loudness.

Non-goals: choosing devices (`edit-plans`), split screen, b-roll.

## Decisions

### D1. ffmpeg cuts, Remotion composes

The base stays an ffmpeg product: cuts, zoom expressions, looks, conform. ffmpeg already does that well, and `check` reasons about it. Remotion receives `base_preview.mov` (or `base_final.mov`) plus the mix, and renders the final frames.

*Alternative*: move cutting into Remotion as well. Rejected: it would duplicate the zoom and look code and lose ffmpeg's frame-exact trims.

### D2. The camera vocabulary and its numbers

These values come from the prototype, as the user approved them:

| Move | Transform (1080x1920) | Background shown | Use |
|---|---|---|---|
| `push` | scale 1 → 1 + `amount` (≤ 0.08) over the move, ease in-out, origin (540, 700) | none | stakes, serious lines, before a turn |
| `pull` | scale 0.8, origin (540, 760), radius 56 px | brand ink | a `behind` word that needs room |
| `side` | scale 1.3, translateX −170 px | none (the zoom covers the frame) | a `front` object on the free wall |
| `corner` | scale 0.3, origin (1040, 1880), radius 130 px (pre-scale), white ring and shadow | brand gradient + `panel` events | real screens or pages that need most of the frame |

Every move eases in over 0.45 s and out over 0.35 s. The cut-out speaker gets the same transform, so `behind` text stays registered.

### D3. No split screen

It was built: the footage clipped to the top 55 % and the panel below. The user called it too invasive and preferred `corner` and the reframe in `side`. It is not in the vocabulary.

### D4. Layers and the cut-out

- **Order.** `panel` → footage → `behind` → speaker cut-out → `front` → old overlay events → captions.
- **The cut-out.** It is the base with the person matte as alpha (ProRes 4444), mounted only inside each `behind` window with 0.1 s pre-roll.
- **The matte.** Windows come from the cut base, not the take, so one matte call per window covers several segments.

### D5. Recurring objects

`object: "<id>"` on events of the same component means "the same thing again". `check` errors when two events with one id disagree on the identifying props: `kicker`, `title` and `italic` for `DocCard`. The timeline lists each object's appearances. A story thread is a device, not a rule: nothing requires an object.

### D6. The low look is made in the base and the mix

Black and white and the freeze have to hold the speaker's frame, which ffmpeg already extracts. So `look: "low"` is handled per segment in `_vf`: `hue=s=0,eq=contrast=1.15:brightness=-0.02` and `tpad` for the freeze. The mix applies `highpass=f=220,lowpass=f=2400,aecho=0.85:0.6:40|80:0.22|0.1,volume=1.6dB` to that segment's span, and pads the freeze with silence.

The values come from `prototype/post.py` after the user's correction. The first version used two low-passes at 1.1 kHz and removed the consonants (2–4 kHz).

### D7. The echo rule and word-synced devices

The ECHO rule refuses a graphic that restates the line being spoken (Blitzreels: a title card that repeats the voice gets cut). Two devices are emphasis, not restatement, and are exempt:
- `Stickers` and `BehindWord`, when each item is ≤ 3 words appearing on its own spoken word (kinetic typography: Envato, Takes);
- `Notice`, when it quotes speech the speaker reports.

### D8. Captions follow the camera

The stage knows the camera, so it computes caption `avoid` and `lightRanges`:
- during `corner`, ink captions sit above the bubble;
- elsewhere they stay where they are today.

Emphasis is dropped on words that a word-synced device is already showing. This avoids the doubled "SIN ESTUDIAR NADA DE TECNOLOGÍA" seen in the prototype.

### D9. Stills and the probe see the real frame

`stills` renders stage frames, so the legibility probe and the never-list checks of `strict-edit-faults` measure text over the actual footage. That is what that change's D5 builds by compositing.

## Risks / Trade-offs

- **Linux render time is unknown.** The Mac takes 59 s for 68 s, but every frame now decodes video in Chromium. Measured in task 5.1 before release. If it is much slower than today's overlay path, the fallback is to render the stage only where a camera move or a `behind` event is active, and to concatenate.
- **Matte edges.** Hair against a busy wall, worse with MediaPipe on Linux than with Vision on the Mac. A `behind` word is kept to the band above the shoulders, where the matte is clean.
- **Disk.** ProRes 4444 at 720p is about 30 MB/s. Windows only, deleted after render.
- **Breaking file outputs.** `overlay.mov` and `overlay_behind_*.mov` disappear. The product's worker doesn't read them (it reads `preview.mp4` and `final.mp4`).

## Migration

Specs without `camera` or `layer` render as before: all events `front`, no camera. Only the render path changes underneath. Output is not byte-identical to v0.6 (compositing order and text edges), so `compare_pools`-style checks re-baseline.
