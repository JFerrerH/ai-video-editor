---
name: character-video
description: Make videos in which a brand's own characters (mascot stills the brand supplies) act in one shared set, with real motion from a paid image-to-video model, a camera move in every shot, cut to narration, at a known and capped cost. Use when the user wants their mascots or characters to move, act or "come alive", wants a reel or explainer starring the brand's characters, or wants to reuse or extend a brand's clip library. Not for cut-out puppet animation or stick figures (motion-graphics), and not for talking-head footage (video-use / short-form-pro).
---

# Character video

The brand's characters, animated by an image-to-video model on fal.ai and cut to a narration.
Captions, cards, SFX and loudness come from the short-form engine. This is the workspace's one
**paid** path. It's opt-in: it only runs when the user has put `FAL_API_KEY` (and, for cloud
narration, `ELEVENLABS_API_KEY`) in `vendor/video-use/.env`. Everything else stays local.

Read the brand's `brand.md` and `brands/<slug>/library/README.md` before planning. Characters,
world text, prompts, voices and clips live only in the brand kit or the project. Never copy them
into a tracked file (tools, skills, templates, specs).

## Pipeline (order matters: it's what keeps the cost down)

| Step | Command | Cost |
|---|---|---|
| 0. project | `uv run tools/new_project.py acme-tips --brand acme --type generated --characters --platforms reels --language en` | – |
| 1. script → `edit/shots.json` | one shot per narration line; map lines to **library clips first** (below) | – |
| 2. narration | local (below) or `uv run tools/gen/voice_cloud.py <edit> --voice <id>` → `audio/vo/<id>.wav` | free / ElevenLabs chars |
| 3. timeline | `uv run tools/shotcut.py <edit> --plan` → `timeline.json` (each shot = line + 0.15 lead + 0.25 tail, ≥ 2 s) | – |
| 4. keyframes | `uv run --group cloud tools/gen/keyframes.py <edit> [--n 2]` → `keyframes/`, `verify/keyframes_sheet.png` | ~$0.04/image |
| 5. **approval** | show the contact sheet; pick candidates (`cp <id>_2.png <id>.png`) | – |
| 6. animate | `uv run --group cloud tools/gen/animate.py <edit> --dur fit` → `shots/<id>.mp4`, `verify/<id>_strip.png` | $0.015/s default |
| 7. base take | `uv run tools/shotcut.py <edit>` → `base.mov` (+ music, end card from `cut` in shots.json) | – |
| 8. captions etc. | `uv run tools/transcribe_local.py <edit>/base.mov --edit-dir <edit> --language <code>` then `uv run <edit>/build.py --preview`, then final | – |

`uv run --group cloud` installs `fal-client`. `uv run` does an inexact sync, so it leaves the `gen`
group (local voice) installed. Every paid tool takes `--dry-run` (print the plan and the estimate,
send nothing) and `--budget` (default $2 per run). It also prints the plan and estimate before
the first request and appends one line per request to `edit/gen_spend.jsonl`.
`uv run tools/gen/fal.py total <edit>` prints the project's spend.

**Local narration** (free, the default): one Kokoro clip per shot line, same sidecar contract:

```bash
uv run --group gen python - footage/<p>/edit en <<'EOF'
import json, sys; from pathlib import Path
sys.path.insert(0, "tools/gen"); import voice
edit, lang = Path(sys.argv[1]).resolve(), sys.argv[2]
sl = json.loads((edit / "shots.json").read_text())
voice.synthesize_many([voice.Job(edit / "audio/vo" / f"{s['id']}.wav", voice.spoken(s["line"], sl.get("pronounce")), lang)
                       for s in sl["shots"]])
EOF
```

## Cost discipline (from the first pilot: ~$10 for one reel, under $1 redone this way)

- **Library first.** `uv run tools/gen/library.py <slug> list --cast hero --mood happy` (or
  `--use payoff`). Point shots at clips with `"library": "<id>"`. A clip can serve 2–3 times: full
  frame, a punch-in crop (≤ 1.3x on 768 px clips), or mirrored (not with text or signs in frame).
  Generate only what the script lacks. A reel built from a library costs ~$0.10–0.30.
- **Measure the narration before animating.** `--dur fit` generates each clip at exactly its cut
  length + 0.2 s, so nothing is generated at 5/10 s and then trimmed. Fixed-duration models
  (Kling) round up to the next allowed length; check `fal.py models`.
- **A/B one shot before a batch** when changing model or prompt style:
  `animate.py <edit> s03 --model kling-2.5-turbo --suffix _k25`, then compare the two frame strips. Never
  run a whole batch on an untested model.
- Retakes are the expensive part. Get keyframes approved before animating, and fix a weak clip by
  editing its `motion`/`camera` text and rerunning only that shot (`--redo`).
- Report spend to the user at each step: the printed estimate before, the `fal.py total` after.
  The numbers are listed prices ("estimated"), not the bill. Point to the fal.ai dashboard for that.

## Craft rules

- **Every shot has a camera move** (`camera` text). The tools refuse an empty one. Vary them
  across shots (push in, arc, crane, dolly, tilt); a locked-off camera reads as a still.
- **Group shots via `base`.** Approve a keyframe with one or two characters, then add the rest with
  `"base": "keyframes/<id>.png"` and only the new characters in `cast`. Sending 3–4 references in one
  request drifts characters off-model.
- **Never ask the image model for empty bands or space "for text"**: it pads the frame with blurred
  bars. Place the characters in the `frame` text instead ("in the lower half of the frame").
  Captions and cards go on top later, in the safe zone.
- `world` text is shared by every keyframe: one set, one light, one lens. Character `desc` names
  what must not change (colours, clothes, props). If a character keeps changing (a colour or a
  feature drifts), add the correction to its `desc` in the project or kit, never to the tools.
- `motion` = what the character does, in one or two actions that fit the line's length. Long
  chains of actions get skipped or rushed.
- Default model `minimax-h3-turbo` (768P, any duration, cheapest that held characters). Use
  `kling-2.5-turbo` / `kling-3-pro` per shot for hard acting or 1080p close-ups, after an A/B.
- 768p clips are upscaled to 1080x1920 in the base take; keep punch-in crops ≤ 1.3x.
- The build template uses `grade="null"`: the generator's look is the grade.

## Verify before presenting

- Read `verify/keyframes_sheet.png` before animating, and each `verify/<id>_strip.png` before
  cutting: on-model characters, the camera actually moves, no text, no morphing, no extra limbs.
  Note per-clip quirks (a prop that vanishes after 1 s, a frame to cut before) in the library README.
- `shotcut.py` stops if a clip is shorter than its shot and names the fix (`animate --dur fit --redo`).
- Pull a frame at every cut from the final (`ffmpeg -ss T -i final.mp4 -frames:v 1 f.png`) using
  `timeline.json` starts, and Read them.
- Compare the `timeline.json` durations with the narration sidecars (shot = line + 0.40 s, or 2.0 s).
- Final: 1080x1920, -14 LUFS ± 1, true peak ≤ -1 dBTP (the engine prints both). Report them, plus
  the spend total.

## Licences and delivery

- Generated clips follow fal.ai's and the model provider's commercial terms. Mention this when
  delivering for a brand.
- **ElevenLabs free plan has no commercial licence** (and can't use shared-library voices through
  the API). `voice_cloud.py` warns on every run. Repeat the warning at delivery and don't present a
  free-plan voice as ready to publish for a brand. Local Kokoro narration (Apache-2.0) has no such limit.
- After delivery, offer to import the project's good new shots into the library:
  `uv run tools/gen/library.py <slug> import <project> <shot> --as <id> --mood … --use …`.
