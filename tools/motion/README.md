# Motion overlay (Remotion)

This renders the transparent graphics layer (cards, phone mockups, captions, flashes) that `tools/shortform.py` composites over the cut. One composition, `Overlay`, is 1080x1920 at 30 fps, rendered as ProRes 4444 with alpha.

```sh
npm i --loglevel=error          # once
```

## Input

`shortform.py` writes `<edit>/overlay_props.json` and stages assets into `<edit>/motion_public/`:

```json
{
  "durationInSeconds": 60,
  "brand": { "colors": {"bg", "tint1", "tint2", "ink", "muted", "accent", "success"},
             "fonts": {"serif", "sans", "mono"},
             "fontFiles": [{"family", "url", "weight", "style"}] },
  "events": [{ "type": "HookTitle", "start": 0, "duration": 3, "props": {} }]
}
```

`brand` comes from `brands/<slug>/brand.json` via `tools/brand.py`. If there's no brand, `defaultBrand` in `src/theme.ts` gives a neutral look. Fonts are loaded from the public dir, and the render fails if one doesn't load.

## Preview and render

```sh
npx remotion studio --props=<edit>/overlay_props.json --public-dir=<edit>/motion_public
npx remotion still Overlay out.png --props=<edit>/overlay_props.json --public-dir=<edit>/motion_public --frame=90 --scale=0.5
```

You usually don't render by hand: `Project.build()` and `Project.overlay_stills()` do it for you.

## Components

They live in `src/components/` and are registered in `REGISTRY` in `src/Overlay.tsx`. The table of props is in `.claude/skills/short-form-pro/SKILL.md`. To add a component:

- Drive all motion with `useCurrentFrame()` + `interpolate`/`spring` (no CSS transitions).
- Take colours and fonts from `useBrand()`. Never hardcode a brand.
- Respect `SAFE` in `src/theme.ts`.
- Add a row to the skill's table.

Known gap: layouts and safe zones assume vertical 9:16. 16:9 and 1:1 need their own compositions.

Remotion licensing: free for teams of up to 3; larger companies need a [company license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
