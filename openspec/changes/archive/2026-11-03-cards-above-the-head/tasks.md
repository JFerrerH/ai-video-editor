## 1. Head

- [x] 1.1 `_head_tops`: the head's top per second, from the person matte, with the take's box as the fallback. Tests
- [x] 1.2 `head_box` uses the highest top while the event is on screen; 40 px of air on top. Tests
- [x] 1.3 The whole card counts against the head; `PLACE_TOP` 100 px. Tests
- [x] 1.4 Every front-layer graphic is placed the same way; schemas mark exceptions with `x-place: own`
- [x] 1.5 The camera counts; `stage/camera.json` is the one source, for the picture and the check. Tests
- [x] 1.6 The head's columns come from the person's own head box

## 2. Reaching the video

- [x] 2.1 Save placements in `edit/overlay_placed.json` and apply them in later passes

## 3. Plans

- [x] 3.1 The hook gives way to the first graphic, and a graphic to the CTA. Tests
- [x] 3.2 `_shared_screen`: two graphics at once are refused, except a full-screen scene, which covers what's under it. Tests
- [x] 3.3 `ink_on_light`: cards are light, so `ink` is the dark colour of a kit's pair, also in a dark-mode kit. Tests
- [x] 3.4 The document card's percentage is measured against the fill it sits on, and a shadow doesn't count as card

## 4. Verification

- [x] 4.1 Unit tests and `openspec validate`
- [x] 4.2 The close-up demo through build, render and QA, from the same job's cache: the rendered events have their placement
- [x] 4.4 A matrix of source sizes and framings: close-up, wide, 720x1280, 4:5 and landscape through conform, a head cut off at the top
- [x] 4.3 In `video-studio`, the full replay and the image gates
