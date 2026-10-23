# Design

## Context

The rig (`explainer/Figure.tsx`, `poses.ts`) is a joint-angle table per pose, blended over 0.4 s,
with three props drawn relative to the rig (desk, megaphone, box) and centred in the `figure` slot.
Widgets are React components registered in `explainer/widgets/index.ts`. `storyboard.py` reads
pose, prop and widget names straight from those TypeScript files with regexes, so adding entries
there also teaches `check` about them. Cue strings (`"@word"`) are resolved to seconds anywhere in
`props` except display keys, so new time fields (`pressAt`, `moves[].at`, `tilts[].at`) get cues for free.

## Goals / Non-Goals

**Goals:**
- Every new pose, prop and widget is opt-in; existing storyboards render byte-for-byte the same layout.
- Widgets keep the existing card look (`Card`, `useCardColors`, `MIN_TEXT`), so they read as one family.

**Non-Goals:**
- Inverse kinematics, or walking between slots or out of frame.
- A generic animation timeline for widgets beyond their own cue fields.

## Decisions

- **Hand-held props attach to the front hand.** The rig already computes `arms[1].hand` per frame,
  so `book`/`phone`/`bag` are drawn at that point and kept upright (the phone at a fixed −14°).
  Upright props read more clearly on a stick figure than ones tilted with the forearm.
  Considered: fixed offsets per pose, like the current props. Rejected because the prop would
  detach during the 0.4 s blend.
- **`walk` is a pose plus a phase-driven overlay.** The base `walk` pose table holds the stride's
  midpoint, and while a move is active the leg and arm angles get a sinusoid (period ~0.5 s)
  layered on top. This reuses the blend and idle code instead of adding keyframed poses.
- **Moves are offsets of the figure's centre inside its slot.** `x` maps to
  `[box.x + halfWidth, box.x + box.w - halfWidth]`, using the widest extent of figure plus prop, so
  `x` 0–1 can never leave the slot. Moves ease in-out (`easeInOut`). `facing` flips to the
  direction of travel during a move and goes back to its spec value when it ends.
- **New widgets reuse `Card`/`useEntrance`.** The `ProductCard` button press is a 6-frame scale-down
  plus a colour change to `success`. `lockAt` dims the card to 45%. `out` uses the shared exit with
  a scale to 0.8 (the poof). `Calendar` flips with a rotateX on the page, one page per `pages[]`
  entry. `Balance` is SVG: a beam rotating ±12° with a spring (damping 14), with pans hanging
  vertically. `ThoughtBubble` draws three trailing dots towards the figure: the slot it sits in
  tells it which side the figure is on.
- **Icon validation in `check`.** The `IconKind` union in `components/icons.tsx` is parsed with
  the same regex approach as poses, and any `icon` key inside widgets is checked against it.
- **Sheets.** Add the new poses to the pose sheet automatically (it iterates `POSE_NAMES`), and
  add one sample each of the four widgets to `WIDGET_SAMPLES`.

## Risks / Trade-offs

- [A walk cycle on a stick figure can look mechanical] → keep the stride amplitude small, add a
  2–3 px vertical bob, and verify with stills at quarter-cycle offsets.
- [More widgets per beat can crowd 9:16] → the motion-graphics skill keeps the "one hero per
  scene" rule. Use `out` to sequence widgets in the same slot rather than stacking them.
- [Regex parsing of the TS registries is brittle] → the same pattern is already used for poses
  and widgets, and the new entries follow the existing formatting.
