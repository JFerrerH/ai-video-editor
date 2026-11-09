# Tasks

## 1. QA

- [x] 1.1 Tests: a word heard after the last kept word is not a fault; a stumble inside still is
- [x] 1.2 `compare` skips inserts after the last expected word (D1, D2)

## 2. Docs

- [x] 2.1 `short-form-pro` SKILL.md: one line

## 3. Verification

- [x] 3.1 Engine suite: 544 passed
- [x] 3.2 The local render that was refused passes QA with the worker's transcriber, and a case where a word the edit doesn't contain sounds inside it is still refused: replay on a local image with these tools, 3 of 3 as expected (the refused preview now passes, the control with a foreign word inside the edit is still refused, and the drawer plan renders)
