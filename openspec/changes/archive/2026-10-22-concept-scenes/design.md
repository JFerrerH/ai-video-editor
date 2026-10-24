# Design

## Context

Scenes live in `tools/motion/src/scenes/` and are registered in `SCENES`. `tools/storyboard.py`
reads that registry (`SCENE_TYPES`), resolves `@word` cues anywhere in a scene's `props` to seconds
before staging, and validates only `BeatScene` props in depth (`_check_beat`). Layout comes from
`useFrameLayout()` (safe box per aspect, short side always 1080), colour from `usePalette(bg)` and
`useBrand()`, motion from `anim.ts` (`enter`, `easeOut`, `easeInOut`). See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- Three scenes driven entirely by props and cues, rendering the same in all four aspects.
- State is a pure function of time, so stills at any frame are deterministic and `replay` is free.

**Non-Goals:**
- A general diagram or isometric engine. These are opinionated primitives with fixed looks
  (themed by brand colours and fonts).
- Editing tools or sheets for them beyond the normal `stills` contact sheet.

## Decisions

1. **One SVG per scene, frame-sized viewBox.** Nodes, spokes, packets, the floor and characters are
   SVG shapes. Labels are HTML on top (brand fonts, with crisp text at any size). This is the same
   approach as `Figure`, and it avoids canvas or WebGL, which Remotion renders less reliably.
   *Alternative:* HTML/CSS boxes with transforms. Rejected: isometric shapes and travelling packets
   along paths are much simpler in SVG.

2. **Shared optional top text.** `NetworkScene` and `IsoOffice` take `kicker` and `title` (with an
   `emphasis`), drawn at the top of the safe box. The diagram fills the rest. This keeps a promo
   readable on mute without a separate `BeatScene` headline. *Alternative:* reuse `BeatScene`
   slots. Rejected: the diagram needs the whole box and its own timing.

3. **NetworkScene geometry.** Ring radius = 0.36 × min(inner w, diagram h), with the hub at the
   diagram centre. Chaos positions come from a seeded hash of the node index (deterministic), plus
   slow sine drift. On `connect`, positions ease (easeInOut, 0.8 s, staggered 3 frames per node)
   to the ring. A packet's position is interpolated along node→hub→node over 0.9 s (half per leg),
   and its arrival flashes the target node. The log ticker sits under the ring in mono, with the
   newest line highlighted and older lines dimmed to 45%.

4. **IsoOffice coordinates.** The floor is a grid of `cols × rows` tiles (default 8×6) in
   floor units (u, v). Projection: `x = cx + (u − v)·tw/2`, `y = cy + (u + v)·th/2`, with tile
   width fitted to the safe box. Desks are `{id, u, v}`; an agent's position is a desk id
   (standing at its front) or `[u, v]`. Characters, desks and walls are depth-sorted by `u + v`.
   Characters are blocky (head, body, legs) for a pixel-art feel without raster art; while
   walking, the legs alternate.

5. **Virtual clock for replay.** `t(frame)` is the real time except inside `replay{at, dur, to}`:
   for the first 60% of `dur` it maps linearly from `at` back to `to`, and for the rest it eases
   forward from `to` back to `at`. After the replay it continues as `real − dur`. In other words,
   the scene's content time pauses for the length of the replay, so cues after it still line up
   with the narration. Every element derives from `t`, so walks and bubbles reverse with no extra
   code. The scrub bar (track, played portion, head, and a "⏪ replay" label) uses real time.

6. **EndCard.** The logo is `<Img>` of the given file, springs from 0.6 to 1 (damping 14), and
   has a soft radial glow in the tone's foreground colour at 15%. Title, tagline, button and URL
   rise in, staggered 6 frames. The button is a pill in `ink` on `accent`/`light`, and in `accent`
   on `dark`, with an SVG arrow so no font glyph is needed.

7. **Validation in Python.** Add `_check_network`, `_check_office` and `_check_endcard` next to
   `_check_beat`, dispatched by type. Icon names come from the existing `ICON_NAMES` registry.
   The scenes' text keys (`title`, `label`, `text`, `tagline`) are already counted by
   `TEXT_KEYS`, so reading-time checks keep working.

## Risks / Trade-offs

- [Isometric layout is hard to fit in both 9:16 and 16:9] → Fit tile width to the safe box per
  aspect, and check stills in 9:16, 16:9 and 4:5 before closing the change.
- [Too many props make the scenes hard to author] → Sensible defaults: desks auto-laid out if
  omitted, node colours cycle a neutral palette, everything optional except `nodes`/`agents`.
- [The replay clock surprises authors] → Document it in the skill: cues after a replay are written
  in narration time as usual. The engine shifts the content clock, not the cues.
