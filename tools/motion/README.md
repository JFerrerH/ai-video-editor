# Motion (Remotion)

Two compositions:

- **`Overlay`**: the transparent graphics layer (cards, phone mockups, captions, flashes) that `tools/shortform.py` composites over a cut. It's 1080x1920 at 30 fps, rendered as ProRes 4444 with alpha.
- **`Story`**: a full-frame video made from scratch. Scenes joined by transitions (`@remotion/transitions`), with global overlay events on top. Size, fps and length come from the props, written by `tools/storyboard.py` from `edit/storyboard.json`. Aspects: 9:16, 16:9, 1:1, 4:5 (`src/layout.ts`). Scene primitives live in `src/scenes/`. The craft rules and the props table are in `.claude/skills/motion-graphics/SKILL.md`.

```sh
npm i --loglevel=error          # once
```

Needs Node.js 18 or later. `node_modules` takes about 0.9 GB, most of it the Chrome Headless Shell that Remotion downloads to render. Remotion renders several frames in parallel (by default one Chrome tab per two CPU threads, a few hundred MB each). On an 8 GB machine, add `--concurrency=2` to manual `npx remotion` commands if renders run out of memory. The full machine requirements are in the [root README](../../README.md#requirements).

ProRes 4444 with alpha is large, roughly 0.5–1 GB per minute at 1080x1920, so keep free disk space in mind when you render long overlays.

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

The overlay components in `src/components/` assume vertical 9:16. The scene primitives in `src/scenes/` work in every aspect.

Remotion licensing: free for teams of up to 3; larger companies need a [company license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
