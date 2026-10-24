# Motion (Remotion)

Four compositions:

- **`Overlay`**: the transparent graphics layer (cards, phone mockups, captions, flashes) that `tools/shortform.py` composites over a cut. It's 1080x1920 at 30 fps, rendered as ProRes 4444 with alpha.
- **`Story`**: a full-frame video made from scratch. Scenes joined by transitions (`@remotion/transitions`), with global overlay events on top. Size, fps and length come from the props, written by `tools/storyboard.py` from `edit/storyboard.json`. Aspects: 9:16, 16:9, 1:1, 4:5 (`src/layout.ts`). Scene primitives live in `src/scenes/`. The craft rules and the props table are in `.claude/skills/motion-graphics/SKILL.md`.
- **`PoseSheet`** and **`WidgetSheet`**: reference contact sheets of the explainer figure's poses and of the widgets in a given aspect. `tools/storyboard.py <edit> sheet poses|widgets [--aspect A]` renders them.

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

## Narrated explainer (`src/explainer/`)

`BeatScene` (`src/scenes/BeatScene.tsx`) composes one beat of a narrated explainer, in this order:

- `GridBg`: a light or dark grid background.
- Widgets, placed in slots (`slots.ts`: `main`, `side`, `figure`, laid out per aspect).
- `Figure`: the stick figure.
- `Headline`: on top.

The parts, file by file:

- `Headline.tsx`: draws the narration's words at their spoken times. `storyboard.py` injects them as `words`, with each word's time, emphasis and phrase. Emphasis words go in an accent pill.
- `Figure.tsx` + `poses.ts`: an SVG rig with joint-angle poses (`stand wave cheer point shrug slump think type push shout`). Poses spring from one to the next, with an idle sway. The props are `desk`, `megaphone` and `box`. The cap and shoes take the brand accent.
- `widgets/`: `Terminal`, `Checklist`, `Stamp`, `Badge`, `Counter`, `Gauge`, `Stopwatch`, `FunnelBars` and `TileGrid` on a shared `Card`. They're registered in `widgets/index.ts`. Every time prop is in seconds from the scene start; `storyboard.py` resolves `@word` cues to seconds before rendering.
- `ProgressBar.tsx`: an overlay event for the thin progress bar along the top, added when the storyboard sets `"progress": true`.

To add a widget or pose: keep times in seconds from the scene start, lay out inside the `box` you're given, take colours from the palette, register it, then check it on the sheet (`storyboard.py <edit> sheet widgets` or `sheet poses`) and add it to the skill's tables.

Remotion licensing: free for teams of up to 3; larger companies need a [company license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
