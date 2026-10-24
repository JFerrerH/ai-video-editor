# Clip library

Reusable animated shots of this brand's characters in one shared set. New videos map their lines
to these clips first and only pay to generate what a script lacks. The whole kit, this folder
included, is gitignored: clips, prompts and character descriptions never go in a tracked path.

Read this before planning any video with the brand's characters. Workflow and craft rules:
`.claude/skills/character-video/SKILL.md`.

## Layout

```
library/
  README.md          this file: what the cast is, which clips have quirks
  spec.json          prompts for the clips made here (world, cast, entries under "clips")
  index.json         every clip with its tags, also those imported from projects
  clips/<id>.mp4     the clips (every one has a camera move)
  keyframes/<id>.png their first frames
  keyframes_sheet.png, verify/   contact sheet and frame strips from the last run
  gen_spend.jsonl    one line per paid request (estimated cost at listed prices)
```

## spec.json

Same shape as a project's `edit/shots.json`; reference stills are relative to this folder.

```json
{
  "world": "A small, warmly lit room with a wooden table and a window. Cinematic lighting.",
  "style": "",
  "aspect": "9:16",
  "cast": {
    "hero": {"ref": "../assets/hero.png", "desc": "the hero character, exactly as in its reference still"}
  },
  "clips": [
    {"id": "hero_idle", "cast": ["hero"], "mood": "neutral", "use": "intro, listening, any line",
     "frame": "HERO stands in the lower half of the frame, looking at the camera.",
     "motion": "The hero breathes gently, blinks and tilts its head.",
     "camera": "The camera slowly pushes in.", "dur": 5}
  ]
}
```

## index.json fields

| Field | Meaning |
|---|---|
| `id` | name used in shot lists: `"library": "<id>"` |
| `file` | `clips/<id>.mp4` |
| `cast` | characters in the clip (list) |
| `mood` | one word: `neutral`, `happy`, `confused`, `thinking`… |
| `use` | which lines it fits: `"intro, payoff, any line"` |
| `action` | what happens in it |
| `camera` | the camera move |
| `dur` | measured length in seconds (ffprobe) |
| `source` | `library`, or the project it was imported from |

## Reuse workflow

1. Map each narration line to a clip: `uv run tools/gen/library.py <slug> list --cast hero --mood happy`
   (or `--use payoff`). One clip can serve 2–3 times: full frame, a punch-in crop (≤ 1.3x on 768 px
   clips before it gets soft), or mirrored (not on shots with text or a sign).
2. In the project's `shots.json`, point those shots at the clips: `{"id": "s04", "line": "…", "library": "hero_happy"}`.
3. Generate only what is missing. Either add an entry to `spec.json` here and run
   `uv run --group cloud tools/gen/library.py <slug> keyframes <id>` → check the PNG →
   `… library.py <slug> clips <id>`, or make the shot in the project and import it afterwards.
4. After a project is finished, import its good new shots:
   `uv run tools/gen/library.py <slug> import <project> s05_reveal --as reveal_doorway --mood warm --use "reveal, payoff"`.

Note per-clip quirks here as you find them (a prop that vanishes after 1 s, a frame to cut before),
so the next video doesn't rediscover them.
