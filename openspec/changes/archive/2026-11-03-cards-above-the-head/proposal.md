## Why

A hosted short from a phone close-up was refused 31 times over, and the engine's only suggestion was full-screen scenes. The owner's style is cards above the head, and looking at the frame there was plenty of room. Four things were wrong:

1. **One height for a whole take.** The head box is a median from five samples, so a card is judged against a head that isn't there at that moment.
2. **A top limit that was never measured.** Floating graphics reused the 290 px of caption placement. Published Reels guides say [220](https://www.designer-daily.com/social-media-video-dimensions-a-complete-reference-guide-2026-230163) to [270 px](https://www.revid.ai/instagram-reels-safe-zone), with no official spec. In a close-up that leaves about 90 px.
3. **Only text was compared with the head.** A card's body could cover the hair with no finding.
4. **A placement didn't reach the video.** `stills` computed it and kept it in memory, and `short.json` has no `frame`. A render in the same job found the boxes cached and never placed the card, so the stills and the video disagreed.

Also, the hook kept its 3 s even when the first graphic came in at 2 s, and a graphic before the CTA held over it, so two cards shared the space.

## What Changes

- The top of the head is measured at each second of the take, and a graphic is judged against the highest it gets while the graphic is on screen.
- A floating graphic can go up to 100 px. The owner chose this after watching it, knowing it enters the zone the guides reserve for the top bar.
- The whole card counts against the head, with 40 px of air on top.
- A placement is saved in `edit/overlay_placed.json` and applied again by the render.
- Every graphic on the front layer is placed the same way, stage components too. A schema marks the exceptions with `x-place: own` (`PhonePanel`, `StageDrawer`), not a list in code.
- The placement takes the camera into account: a move that holds over a graphic goes by where it puts the head. Its values live in `stage/camera.json`, read by the picture and by the check.
- The head's columns come from that person's own head box, so a close-up and a wide shot are measured alike.
- `ink` is the dark colour of a kit's `ink` and `bg` pair, so a dark-mode kit doesn't write cream on white cards.
- The hook and any graphic before the CTA end before the next card starts. Two floating graphics at once are refused, naming both; a full-screen scene covers what is under it.

## Capabilities

### Modified Capabilities

- `edit-faults`: the head is measured per moment, the whole card counts, and placements reach the render.
- `edit-plans`: two graphics never share the screen.
- `brand-theme`: a dark-mode kit stays readable on cards.

The rule stays in terms of the speaker and the 1080x1920 stage, which every take is scaled to, so it adapts to any source size and framing.

## Impact

`tools/shortform.py`, `tools/edit_plan.py`, their tests. The first build of a take adds about 15 s per 100 s of footage for the head track, on the Mac. A person's raised hand doesn't count, but a floating card may overlap the head for a moment if they lean within a second.
