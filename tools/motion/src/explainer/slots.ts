import { Aspect, Safe } from "../layout";

export type Rect = { x: number; y: number; w: number; h: number };
export type SlotName = "main" | "side" | "figure";
export const SLOT_NAMES: SlotName[] = ["main", "side", "figure"];

/** Space the headline keeps at the top of the safe box (2 lines at its base size), per aspect. */
export const HEADLINE_H: Record<Aspect, number> = { "9:16": 220, "16:9": 200, "1:1": 180, "4:5": 190 };

/**
 * Where a BeatScene's slots sit, inside the safe box under the headline.
 *  9:16, 1:1, 4:5: stacked. `main` across the middle, `figure` bottom-centre; with a `side`
 *    widget, `side` takes the left of the bottom band and the figure moves to its right.
 *  16:9: `main` on the left two-thirds, `figure` on the right; `side` takes the top of the right
 *    column and the figure stands under it.
 */
export const slotRects = (aspect: Aspect, width: number, height: number, safe: Safe, sideUsed: boolean): Record<SlotName, Rect> => {
  const x0 = safe.left;
  const w = width - safe.left - safe.right;
  const y0 = safe.top + HEADLINE_H[aspect];
  const h = height - safe.bottom - y0;
  const gap = 32;
  if (aspect === "16:9") {
    const mw = Math.round(w * 0.62);
    const col = { x: x0 + mw + gap, y: y0, w: w - mw - gap, h };
    const side = { ...col, h: Math.round(h * 0.42) };
    return {
      main: { x: x0, y: y0, w: mw, h },
      side,
      figure: sideUsed ? { ...col, y: side.y + side.h + gap, h: h - side.h - gap } : col,
    };
  }
  const mh = Math.round(h * 0.55);
  const band = { x: x0, y: y0 + mh + gap, w, h: h - mh - gap };
  const half = Math.round((w - gap) / 2);
  return {
    main: { x: x0, y: y0, w, h: mh },
    side: { ...band, w: half },
    figure: sideUsed ? { ...band, x: x0 + half + gap, w: w - half - gap } : band,
  };
};
