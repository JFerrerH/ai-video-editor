# Tasks

## 1. NetworkScene

- [x] 1.1 Add `tools/motion/src/scenes/NetworkScene.tsx` (nodes, hub, chaos, connect, chips, messages with lock, log ticker, optional kicker/title) and register it in `SCENES`; verify `npx tsc --noEmit` passes in `tools/motion`
- [x] 1.2 Add `_check_network` to `tools/storyboard.py` (unknown node ids in messages, unknown icons); verify `check` reports an ERROR for a message to a missing node in a scratch storyboard

## 2. IsoOffice

- [x] 2.1 Add `tools/motion/src/scenes/IsoOffice.tsx` (floor grid, walls, desks, block characters with labels, walks, carry, bubbles, replay with the virtual clock and scrub bar, optional kicker/title) and register it; verify `npx tsc --noEmit` passes
- [x] 2.2 Add `_check_office` (unknown agent or desk ids, unknown icons, replay ending after the scene); verify `check` ERRORs on a walk by a missing agent

## 3. EndCard

- [x] 3.1 Add `tools/motion/src/scenes/EndCard.tsx` (logo spring and glow, title, tagline, CTA pill with an SVG arrow, url, staggered) and register it; verify `npx tsc --noEmit` passes and a missing logo is reported by `check` as a missing asset

## 4. Docs

- [x] 4.1 Update `.claude/skills/motion-graphics/SKILL.md`: three rows in the primitive table, a props reference, the replay clock note, and the promo craft rule (animate the mechanism; screenshots only as brief proof; stick figure as a rare accent). Verify the rows exist
- [x] 4.2 Update the `CLAUDE.md` routing row for videos from scratch to mention the promo scenes; verify with grep
- [x] 4.3 Sync the scene list in `openspec/specs/storyboard-video` through this change's delta (done at archive)

## 5. Verification

- [x] 5.1 Render a pilot under `footage/` (gitignored) using all three scenes at 4:5, plus stills of the same storyboard at 9:16 and 16:9. Read the contact sheets and check the spec scenarios: ring after chaos, packet on spokes, walk start/end positions, bubble gone mid-replay and back after, end card at 0.2 s vs 1.5 s, everything inside the safe box. Report the loudness from `render --preview`
