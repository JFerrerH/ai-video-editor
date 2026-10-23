# Tasks

## 1. Rig: poses, props, moves

- [x] 1.1 Add poses `read`, `wait`, `reach`, `scared`, `walk` to `poses.ts`, and props `book`, `phone`, `bag` to `PROP_NAMES` with `read` → `book` as its default prop. Verify: `storyboard.py <edit> sheet poses` shows 15 labelled poses.
- [x] 1.2 Draw the hand-held props at the front hand in `Figure.tsx`, following the forearm angle. Verify: two stills of a `stand` → `reach` blend holding `phone` show the phone at the hand in both.
- [x] 1.3 Implement `moves: [{x, at, dur}]`: slot-clamped travel, a walk cycle while moving, facing the travel direction. Verify: stills at 0.9 s and 2.0 s of a 0.2 → 0.8 move show the figure further right, inside the slot.

## 2. Widgets and icons

- [x] 2.1 Add the line icons `book`, `cart`, `heart`, `brain`, `moon` to `components/icons.tsx`. Verify: they render on the widget sheet.
- [x] 2.2 Add the `ProductCard` widget (icon, name, price, `pressAt`, `lockAt`, `out` poof). Verify: the stills from the spec scenario show a pressed button and then no card.
- [x] 2.3 Add the `Calendar` widget (`pages[{label, at}]`, page flip). Verify: stills read "Hoy" before the cue and "Mañana" after it.
- [x] 2.4 Add the `Balance` widget (`left`, `right`, `tilts[{to, at}]`). Verify: a still 0.8 s after a `right` tilt shows the right pan lower.
- [x] 2.5 Add the `ThoughtBubble` widget (icon or text, trailing dots towards the figure). Verify: the widget sheet sample sits inside the safe box at all 4 aspects.
- [x] 2.6 Register the four widgets and add samples to `WIDGET_SAMPLES`. Verify: `sheet widgets --aspect` for 9:16, 16:9, 1:1 and 4:5 reports every widget inside the safe box.

## 3. Engine checks

- [x] 3.1 `storyboard.py check`: validate `moves` (x in 0–1, no overlaps) and widget `icon` names. Verify: storyboards with an overlapping move and with `icon: "rocket"` each produce the expected ERROR. A storyboard without the new fields produces the same output as before.
- [x] 3.2 Typecheck: `cd tools/motion && npx tsc --noEmit` passes.

## 4. Docs

- [x] 4.1 Update the `motion-graphics` SKILL.md "Narrated explainer" tables (poses, props, moves, the four widgets, icons) and the "Picture" guidance (act the script out: a prop or move per beat where the words suggest one). Verify: the tables list every name that `check` accepts.

## 5. Verification pilot

- [x] 5.1 Re-render the existing pilot narrated reel under `footage/` with the new acting (every beat with at least one pose change on a cue word, and moves/props/new widgets where the script suggests them). Run `check`, `stills` and `render --preview`. Read the contact sheet and the frames pulled at each beat, and report the duration and the LUFS / true peak.

## Workflow follow-up

- `/opsx:verify`, then `/opsx:archive` once SKILL.md reflects the shipped behaviour.
