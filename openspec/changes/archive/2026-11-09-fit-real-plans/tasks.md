# Tasks

## 1. Captions and the head

- [x] 1.1 Update the caption test: a head-crossing band is taken with a `caption_head` warning, strict makes no error of it; a band that clears both is still preferred
- [x] 1.2 `_caption_moves` (D1)

## 2. Limits at real use

- [x] 2.1 `tools/tests/real_use_floors.json` with the 13 maxima, and the schema test that limits are at or above them (fails first)
- [x] 2.2 Raise the 13 limits to their floors
- [x] 2.3 Run the layout matrix on the components and several seeds; fix every overflow through the shared fitting (D3): of the 8 components with a raised limit only `BarChart` overflowed (4 bars with a long title took 1327 px against the 1246 of the safe box, and a wide value wrapped its row); its values now shrink instead of wrapping and the block scales to the safe height from the real line counts (`lineCount` in the theme). 0 findings with seeds 11 and 12

## 3. Docs

- [x] 3.1 `short-form-pro` SKILL.md: captions over the head are a warning; limits and their floors

## 4. Verification

- [x] 4.1 Engine suite (541 passed) and the full matrix on fresh seeds: seed 447991 found a 1 px overlap of a placed NameTitle with the head (rounding of scale and translate), so the face check now tolerates `INSIDE_TOL` like the containment rule (`overlaps`, tested); the real-use scan also missed fields inside lists of objects at first (`HookTitle.lines[].text` 20 to 26, `ListScene.items[].text` 19 to 24), added after the replay showed it
- [x] 4.2 The replay cases that failed on `v0.8.5` (the drawer plans, the four old specs, the session plans) now reach the faults they were kept for or pass: 11 of 11 on a local image with this branch's `tools/` (both drawer plans render, QA passes, -14.0 and -14.1 LUFS; the four old specs and the echo plans reach their faults). one replay case (preview QA hears a word the edit doesn't contain) is a separate investigation
