import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";
import { LineIcon } from "./icons";

/** "The only one in the room": a white card with a row of people; at `highlightAt` (s) one of them
 *  (`highlight` index) turns peach and lifts while the others fade back. Floats above the head. */
export const RoomDots: React.FC<{
  durationInFrames: number;
  count?: number;
  highlight?: number;
  highlightAt: number;
  top?: number;
}> = ({ durationInFrames, count = 7, highlight = 3, highlightAt, top = SAFE.top + 40 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors } = useBrand();
  const s = enter(frame, fps, 0, 14);
  const out = exit(frame, durationInFrames, 6);
  const h = enter(frame, fps, sec(highlightAt, fps), 10);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          display: "flex",
          gap: 10,
          padding: "30px 36px",
          background: "white",
          borderRadius: 28,
          boxShadow: "0 22px 50px rgba(31,35,40,0.25)",
          opacity: Math.min(1, s * 1.5),
          translate: `0px ${interpolate(s, [0, 1], [-60, 0])}px`,
        }}
      >
        {Array.from({ length: count }, (_, i) => {
          const k = enter(frame, fps, 2 + i * 2, 13);
          const me = i === highlight;
          return (
            <div
              key={i}
              style={{
                width: 84,
                height: 104,
                borderRadius: 20,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: me ? interpolateColor(h, colors.bg, colors.tint1) : colors.bg,
                opacity: me ? k : k * interpolate(h, [0, 1], [1, 0.45]),
                translate: `0px ${me ? interpolate(h, [0, 1], [0, -16]) : interpolate(k, [0, 1], [20, 0])}px`,
                scale: String(me ? interpolate(h, [0, 1], [1, 1.12]) : 1),
              }}
            >
              <LineIcon kind="person" size={60} color={colors.ink} stroke={me ? 2.2 : 1.6} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// simple hex lerp (both colours #RRGGBB)
const interpolateColor = (t: number, a: string, b: string) => {
  const p = (c: string, i: number) => parseInt(c.slice(1 + i * 2, 3 + i * 2), 16);
  const ch = [0, 1, 2].map((i) => Math.round(p(a, i) + (p(b, i) - p(a, i)) * Math.max(0, Math.min(1, t))));
  return `rgb(${ch.join(",")})`;
};
