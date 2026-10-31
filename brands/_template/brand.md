# Brand kit: <Brand name>

Copy `brands/_template/` to `brands/<slug>/`, fill in this file and `brand.json`, put new font and logo files in `incoming/`,
and run `uv run tools/brand_check.py brands/<slug>` to validate them into `fonts/` and `logos/` (invalid files are deleted).
Claude reads this before editing any project whose `project.md` names this brand, and only those.
Anything left blank falls back to the neutral defaults in the skills.

- Brand / channel: name, one-line description, URL, social handle.
- Colours (hex): background, ink/text, muted, two soft tints for backdrops, accent (warnings), success. Mirror them in `brand.json`.
- Typography: serif / sans / mono families and what each is used for. Font files in `fonts/`, listed in `brand.json` `fontFiles`
  (weight `400`, or a variable font's range like `"100 800"`, as `brand_check.py` reports it; fix any `warnings` it prints).
  A role left unset uses the kit's `sans`.
- Caption style: font, weight, size, case, placement, key-phrase treatment (`brand.json` `captions`: size, emphSize, emphColor, top).
- Hook rules: tone, what's off-limits.
- Look: grade, when B&W or other looks are allowed.
- Graphics: which get a full backdrop and which float; what they must never do.
- SFX and music: vocabulary, levels, licensed tracks.
- Intro / outro / CTA: end card, handle, call to action.
- Visual sources: own site/app (`tools/site_capture.py`), logos in `logos/`, B-roll in `broll/`, people photos (with permission).
- Default platforms and length.
- Rejected before: things the client said no to, so they don't come back.
