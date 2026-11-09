import { measureText } from "@remotion/layout-utils";
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { FIT_WRAP, MIN_TEXT, SAFE, SAFE_WIDTH, fitSize, readable, useBrand } from "../theme";

type Bar = { value: number; label: string; at: number; highlight?: boolean };

const LABEL = 44; // px: a label's size when it fits its column
const PAD = 44; // px: the card's side padding
const GAP = 24; // px between columns
const COL_MIN = 120; // px: the narrowest column, a bar and a short label

/** Ratio bars (×1 / ×2 / ×3): age gaps, multiples. Each bar grows at `at` (s). Floats above the head.
 *  Columns are as wide as their longest label needs, up to an equal share of the safe width; a label that still
 *  doesn't fit shrinks to the minimum size and wraps (theme `fitSize`), and the card grows to hold it. */
export const AgeBars: React.FC<{ durationInFrames: number; bars: Bar[]; caption?: string; top?: number }> = ({
  durationInFrames,
  bars,
  caption,
  top = SAFE.top + 10,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 15);
  const out = exit(frame, durationInFrames, 6);
  const max = Math.max(...bars.map((b) => b.value));
  const H = 200;
  const n = Math.max(1, bars.length);
  const share = Math.floor((SAFE_WIDTH - 2 * PAD - (n - 1) * GAP) / n);
  const natural = Math.max(...bars.map((b) => measureText({ text: b.label, fontFamily: fonts.sans, fontSize: LABEL, fontWeight: "600" }).width));
  const col = Math.min(share, Math.max(COL_MIN, Math.ceil(natural)));
  const width = Math.max(600, n * col + (n - 1) * GAP + 2 * PAD);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          width,
          boxSizing: "border-box",
          background: "white",
          borderRadius: 24,
          padding: `30px ${PAD}px 30px`,
          boxShadow: "0 26px 60px rgba(31,35,40,0.28)",
          translate: `0px ${interpolate(s, [0, 1], [-560, 0])}px`,
          rotate: `${interpolate(s, [0, 1], [-5, -1])}deg`,
        }}
      >
        {caption ? (
          <div style={{ fontFamily: fonts.mono, fontSize: MIN_TEXT, letterSpacing: 5, color: readable(colors.muted, "#FFFFFF", colors.ink), marginBottom: 18, ...FIT_WRAP }}>
            {caption}
          </div>
        ) : null}
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-around", gap: GAP, minHeight: H + 60 }}>
          {bars.map((b, i) => {
            const f0 = sec(b.at, fps);
            const k = frame < f0 ? 0 : enter(frame, fps, f0, 14);
            const h = (H * b.value * k) / max;
            return (
              <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", width: col }}>
                <div
                  style={{
                    fontFamily: fonts.sans,
                    fontWeight: 600,
                    fontSize: fitSize(b.label, { fontFamily: fonts.sans, fontWeight: 600, max: LABEL, width: col }),
                    lineHeight: 1.1,
                    textAlign: "center",
                    width: col,
                    color: colors.ink,
                    opacity: Math.min(1, k * 2),
                    marginBottom: 10,
                    ...FIT_WRAP,
                  }}
                >
                  {b.label}
                </div>
                <div
                  style={{
                    width: Math.min(104, col),
                    height: Math.max(h, frame < f0 ? 0 : 6),
                    borderRadius: 14,
                    background: b.highlight ? colors.tint1 : colors.ink,
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
