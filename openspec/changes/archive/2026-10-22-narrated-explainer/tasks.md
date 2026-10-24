# Tasks

## 1. Dependencies

- [x] 1.1 Add `[dependency-groups] gen = ["mlx-audio==<latest stable, pinned>"]` to `pyproject.toml`; verify `uv sync --group gen` succeeds, a plain `uv sync` does not install `mlx-audio`, and `uv.lock` is updated
- [x] 1.2 Confirm licences against the sources (Kokoro-82M weights Apache-2.0, `mlx-audio` licence, `misaki`, `espeak-ng` GPL-3.0, bundled in `espeakng-loader`) and record the model repo id and licence in `tools/gen/voice.py`'s docstring; verify the repo id resolves with `huggingface_hub`
- [x] 1.3 Pin the spaCy `en_core_web_sm` wheel in the `gen` group; verify a non-English line phonemises with the bundled `espeak-ng` (no Homebrew install) and record the total new disk use (`du -sh` of the HF cache entries + any spaCy model) for the skill

## 2. Voice (`tools/gen/voice.py`)

- [x] 2.1 Create `tools/gen/__init__.py` and `voice.py` with the lang→Kokoro code table, preset-prefix validation, default presets, `pronounce` substitution and sidecar helpers (standard library only at module top level); verify `from gen import voice` works on a default install and `--help` lists model id, licence and languages
- [x] 2.2 Implement `synthesize_many(jobs, force)` (one model load), RMS silence trim to ≤ 50 ms, 24 kHz mono WAV + sidecar, missing-group and missing-phonemiser messages; verify with the CLI: an `en` line gives a 1–4 s WAV with ≤ 50 ms edge silence, speed 1.5 is ≥ 20% shorter, a re-run says cached (mtime unchanged), `de` and a wrong-language preset exit non-zero without writing
- [x] 2.3 Synthesise the same two sample lines with 3 English and 2 Spanish presets into the scratchpad and record the warm seconds per clip; the user listens and picks the default preset per language (design open question)

## 3. Narration timing in the engine

- [x] 3.1 Add the `voice` block, `narration_audio`, `tail`, per-scene `speed` and the `voice` command to `tools/storyboard.py` (clips under `edit/audio/narration/<scene>.wav`); verify 6 narrated scenes give 6 clips + sidecars and a second run reports all cached
- [x] 3.2 Word timing: batch `transcribe_local.py` over clips lacking a fresh `<clip>.words.json`, align to the script (difflib + interpolation, first word clamped to the measured onset), cut phrases (`.?!`, `|`, 7 words); verify "Ship it in *one day.*" yields 5 words with the emphasis flag on the last two and strictly increasing times, and that deleting one word from the Whisper output in a test fixture still yields all 5
- [x] 3.3 `resolve()`: auto durations (`transitionIn + clip + tail`, frame-rounded), `voiceStart`, cue resolution (`@word`, `#n`, `+/-offset`) in props, pose lists and `sfx`; verify `check` prints 2.40 s for a 2.10 s clip on a hard cut, errors on a too-short fixed duration, on `@revenue` not in the narration, on a missing/stale clip (says run `voice`), on unsupported `lang`/preset, and on `audio.voice` + narrated clips together
- [x] 3.4 Narration track in `render`: clips placed at `voiceStart` into `edit/audio/narration_track.wav` and used as the voice in `mix()`; verify each clip's onset (first sample above -40 dBFS) is within 1 frame of its `voiceStart`, and a storyboard without a `voice` block renders exactly as before (same duration and loudness as the engine before this change; `storyboard.py` isn't on `main` yet)
- [x] 3.5 Update the `storyboard.py` docstring for the new fields and commands

## 4. Headline, grid background, progress bar

- [x] 4.1 `explainer/GridBg.tsx` (light/dark from the palette, grid ≤ 6% luminance contrast, vignette, grain); verify by sampling a dark still: grid line vs background luminance difference is > 0 and ≤ 6%
- [x] 4.2 `explainer/Headline.tsx`: words from the injected `words`, phrase switching, 3-frame rise-in per word, accent pill with spring pop for emphasis, wrapping with `measureText` to the safe box (max 2 lines), sizes by short side; verify with stills 0.1 s before and after a word's time (absent / present), a phrase break still, and an emphasis still (white on accent pill, no asterisks)
- [x] 4.3 `ProgressBar` overlay event + `"progress": true` storyboard flag; verify a still at half the duration shows the bar at 50% ±1% of the width
- [x] 4.4 Run `npx tsc --noEmit` and `npm run lint` in `tools/motion`; both pass

## 5. Character

- [x] 5.1 `explainer/Figure.tsx` + `poses.ts`: FK rig, 10 poses, spring blending, idle sway/breath, `facing`, `slot`, `scale`, ground shadow, accent on cap and shoes; props `desk`, `megaphone`, `box` attached to joints
- [x] 5.2 `PoseSheet` composition + `storyboard.py sheet poses`; render it, read the sheet, and tune angles until every pose reads clearly at thumbnail size; verify 10 labelled poses and the accent on cap and shoes
- [x] 5.3 Verify the motion checks with stills: `stand`→`cheer` on a cue (arms down 0.1 s before, raised 0.5 s after), and two stills 1 s apart in a held pose differ (mean abs diff over the figure box > 0.5); unknown pose/prop gives a `check` ERROR listing valid ones; tsc + lint pass

## 6. Widgets

- [x] 6.1 Shared `Card` shell + `Terminal`, `Checklist`, `Stamp`, `Badge`; verify with stills: terminal typing mid-line, checklist with one struck item, stamp over a checklist 0.5 s after its cue
- [x] 6.2 `Counter` (with sparkline), `Gauge`, `Stopwatch`, `FunnelBars`, `TileGrid`; verify the counter stills read 0 / strictly between / 1200 before, during and after its range
- [x] 6.3 `WidgetSheet` composition + `storyboard.py sheet widgets --aspect A`; render all four aspects, read them, verify every widget sits inside the safe box and no widget text is under 28 px; tsc + lint pass

## 7. BeatScene

- [x] 7.1 `scenes/BeatScene.tsx` (GridBg → widgets in slots → figure → Headline), slot geometry per aspect, registered in `SCENES`; `check` validates widget types and slots; verify a storyboard with headline + figure + one widget checks clean at 9:16, 16:9, 1:1 and 4:5, and `stills` for each aspect show nothing outside the safe box
- [x] 7.2 Add `templates/storyboard_explainer.json` (voice block, `progress: true`, 4 neutral BeatScenes using cues, emphasis, poses and widgets) and make `new_project.py --type generated` mention it; verify `check` on a fresh project reports only the "run `voice`" errors, and passes after `voice`

## 8. Skill and routing

- [x] 8.1 Update `.claude/skills/motion-graphics/SKILL.md` with a "Narrated explainer" section:
  - Writing: one idea per beat, beats of 2–4 s, mixed sentence length, `*emphasis*` at most once per phrase, `|` for a forced break, `pronounce` for names.
  - Picture: the figure reacts to every beat; numbers move while they're said; a stamp for a negation; light/dark switch when the mood flips; hard cuts by default; progress bar on.
  - Reference: the widget and pose tables, the `voice` → `check` → `sheet` → `stills` → `render` workflow, and the measured speeds from 1.3/2.3.

  Verify the documented commands run as written
- [x] 8.2 Update CLAUDE.md: routing row for narrated explainers (motion-graphics + `voice`), transcription note that `voice` reuses local Whisper, Gotchas for `uv sync --group gen`; verify no client, brand, creator or private project is named in any tracked file this change touches (`git diff main` + grep)

## 9. Pilot verification

- [x] 9.1 `uv run tools/new_project.py demo-explainer-pilot --brand none --type generated --platforms reels --language en`, then write a ~30 s, 9:16 storyboard of 8–10 BeatScenes on a neutral topic, using every pose family and at least 6 widget types, cues, emphasis, one dark beat, a music bed and a few cue-timed SFX; run `voice`, `check`, `sheet poses`, `stills`, and read every contact sheet and still
- [x] 9.2 `render --preview`, then full `render`; verify the duration equals `check`'s total to the frame, frames pulled at 3 word cues show the cued word and widget action on time, loudness is -14 ±0.5 LUFS with true peak ≤ -1.5 dBTP, and record voice/whisper/render timings in the pilot's `edit/project.md`; the user listens to the voice and approves or picks another preset
- [x] 9.3 Make a Spanish copy (`--language es`, Spanish preset, translated narration) and a 16:9 copy; run `voice` + `check` + `stills` on each and verify alignment counts, layout inside the safe box, and that the Spanish clips phonemise through the bundled `espeak-ng`

## Workflow follow-up

- Run `/opsx:verify`, confirm SKILL.md and CLAUDE.md reflect the shipped behaviour, then `/opsx:archive`.
- Update the from-scratch roadmap memory: Phase 2 is now "narrated explainer kit + local voice"; image generation is shelved unless a project needs it.
