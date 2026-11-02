import type React from "react";
import { ramp, span, inOut } from "./fx";

/** Camera moves of a short (output seconds). No split screen: it was built and rejected as too invasive. */
export type CamMove = { kind: "push" | "pull" | "side" | "corner"; start: number; end: number; amount?: number };

export type Cam = {
  scale: number;
  ox: number; // transform origin, px of the 1080x1920 frame
  oy: number;
  tx: number;
  radius: number; // footage corner radius, px before scaling
  bg: "ink" | "tint"; // what shows around the footage
  shadow: number; // 0–1: white ring and shadow of the corner bubble
};

const CORNER = 0.3; // the speaker's scale in the corner bubble

/** The camera at `t` s. Moves don't overlap (the spec checks), each eases in over 0.45 s and out over 0.35 s;
 *  a push grows by `amount` (default 0.07) over its length. */
export const camera = (moves: CamMove[], t: number): Cam => {
  const w = (k: CamMove["kind"]) =>
    moves
      .filter((m) => m.kind === k)
      .map((m) =>
        k === "push"
          ? ramp(t, m.start, m.end - m.start, inOut) * (t < m.end + 0.01 ? 1 : 0) * (m.amount ?? 0.07)
          : span(t, m.start, m.end, 0.45, 0.35),
      )
      .reduce((a, b) => Math.max(a, b), 0);
  const pull = w("pull");
  const corner = w("corner");
  const push = w("push");
  const side = w("side");
  // side: zoom in and put the speaker in the left third, so the wall on the right is free for an object
  const scale = (1 - 0.2 * pull) * (1 - (1 - CORNER) * corner) * (1 + push) * (1 + 0.3 * side);
  const [ox, oy] = corner > 0 ? [1040, 1880] : pull > 0 ? [540, 760] : [540, 700];
  return {
    scale,
    ox,
    oy,
    tx: -170 * side,
    radius: Math.max(56 * pull, 130 * corner),
    bg: corner > 0 ? "tint" : "ink",
    shadow: corner,
  };
};

export const camStyle = (c: Cam): React.CSSProperties => ({
  transformOrigin: `${c.ox}px ${c.oy}px`,
  transform: `translate(${c.tx}px, 0px) scale(${c.scale})`,
});
