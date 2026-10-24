# Proposal

## Why

A product-promo pilot built from a website came out as screenshots with a slow pan plus a stick
figure in every terminal beat, and the user rejected it: a promo should *animate what the product
does*. The storyboard engine has no primitive for the most common SaaS mechanisms: things
connecting through a hub and messages flowing between them, a team of workers visibly doing tasks,
or a branded end card that moves. So every such beat falls back to `ImageScene` captures.

## What Changes

- **`NetworkScene`** (new scene type): labelled nodes (each with a colour and optional line icon)
  and an optional central hub. Cued phases: `chaos` (nodes drift, tangled messages and error flashes),
  `connect` (nodes ease into a ring around the hub, spokes draw), per-node `chips` (a small label
  pill, such as "ID"), `messages` (a packet, optionally showing a lock, travels from one node through
  the hub to another), and a `log` ticker that prints a line per cue. Every time accepts `@word` cues.
- **`IsoOffice`** (new scene type): an isometric room drawn in flat vector shapes (floor grid,
  walls, desks with monitors), with `agents` (a block-built character with a colour and a mono label)
  that appear, `walks` between positions, `bubbles` (live status text or an icon above an agent,
  with an `until`), `carry` (an agent holds a document while walking, for a handoff), and `replay`
  (a scrub bar appears and the scene's clock runs backwards and then forwards again, so walks and
  bubbles reverse).
- **`EndCard`** (new scene type): logo image (SVG/PNG from the brand kit) springs in with a soft
  glow, then title, tagline, a CTA pill with an arrow, and a URL, in reading order. On `accent`,
  `dark` or `light`.
- `check` validates the new scenes' props: node and agent ids referenced by messages, walks and
  bubbles exist; icon names are known; replay windows sit inside the scene.
- **Skill:** `motion-graphics` gains the three rows in its primitive table and a craft rule: *a
  promo animates the product's mechanism. Screenshots are at most a short proof beat, and the stick
  figure is a rare accent, not a per-beat fixture.* CLAUDE.md routing mentions the new scenes for
  promos.
- **Out of scope:** pixel-art raster rendering, more than one room or floor, camera moves
  inside `IsoOffice` beyond a gentle drift, physics or pathfinding (walks are straight lines in
  floor coordinates), 3D, interactive output, and any change to existing primitives, widgets or the
  short-form overlays.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `storyboard-video`: the "Scene primitives" requirement adds `NetworkScene`, `IsoOffice` and
  `EndCard`. New requirements describe their cue-driven behaviour and the `check` validation.

## Impact

- `tools/motion/src/scenes/`: three new files and their registration in `SCENES`. They reuse
  `anim.ts`, `layout.ts`, `Bg`, `usePalette`, `useBrand` and `components/icons.tsx`.
- `tools/storyboard.py`: a validator per new type, called from `check`. Timeline, mix and render are
  unchanged.
- `.claude/skills/motion-graphics/SKILL.md` and `CLAUDE.md` routing table.
- Workflows: `motion-graphics` (from-scratch videos) gains the scenes. `short-form-pro` and
  `video-use` are unaffected.
- No new dependencies or models. The render cost is comparable to `BeatScene`.
