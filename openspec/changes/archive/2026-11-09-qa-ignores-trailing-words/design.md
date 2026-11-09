# Design

## Context

Reproduced 2026-11-09 on a local render, with the worker's transcriber (faster-whisper) in the engine container: expected 196 words, heard 196, opcodes `replace clientes/agentes`, `delete hoy`, `replace quizas/quiza`, `insert paris` at 52.30 s, with the last expected word ending at 52.31 s. The audio at 52.3 to 52.5 s sits at -23 dB against a speech level of -12 dB, so it is the decay of the last word, not silence. The preview passes QA with the Mac's MLX backend, so the fault is the transcriber's, not the edit's.

## Decisions

**D1. Position, justified by the render.** The end tail (`edit-faults` "The video ends with a tail") ends the last clip's audio before the next source word's onset, so a word after the last kept word is never speech from the edit's source. A first attempt measured silence under the heard word and found none, so it was dropped: the decay of the last word is above the silence threshold.

**D2. Only inserts after the last expected word.** The difflib opcode is an `insert` at the end of the expected words. A `replace` of the last word keeps the existing mishearing test.

## Risks / Trade-offs

- **A hand-made spec with no tail** could leak the next word at the very end; the tail applies to every spec at load, and the cut-energy check still measures the last cut.

## Migration Plan

Engine release; no data migration.

## Open Questions

None.
