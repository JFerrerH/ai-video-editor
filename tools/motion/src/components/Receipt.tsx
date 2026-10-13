import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

/** Quote / receipt: items tick in one by one, total, then a rubber stamp. */
export const Receipt: React.FC<{
  durationInFrames: number;
  title: string;
  items: { text: string; at: number }[];
  total: string;
  stamp?: string; // optional: leave out for a plain quote
  stampAt?: number;
  enterFrom?: "below" | "above"; // "above" when floating over footage, so it never crosses the face
}> = ({ durationInFrames, title, items, total, stamp, stampAt = 0, enterFrom = "below" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const cIn = enter(frame, fps, 0, 16);
  const st = enter(frame, fps, sec(stampAt, fps), 9);
  const out = exit(frame, durationInFrames, 5);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top: SAFE.top + 10,
          width: 680,
          background: "white",
          padding: "48px 52px 60px",
          borderRadius: 10,
          boxShadow: "0 30px 70px rgba(31,35,40,0.22)",
          translate: `0px ${interpolate(cIn, [0, 1], [enterFrom === "above" ? -900 : 900, 0])}px`,
          rotate: "-1.5deg",
          fontFamily: fonts.mono,
          color: colors.ink,
        }}
      >
        <div style={{ fontSize: 40, letterSpacing: 8, textAlign: "center" }}>{title}</div>
        <div style={{ borderTop: `3px dashed ${colors.muted}`, margin: "30px 0" }} />
        {items.map((it, i) => {
          const p = interpolate(frame, [sec(it.at, fps), sec(it.at, fps) + 5], [0, 1], clamp);
          return (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 34,
                margin: "20px 0",
                opacity: p,
                translate: `${(1 - p) * -30}px 0px`,
              }}
            >
              <span>{it.text}</span>
              <span>$$$</span>
            </div>
          );
        })}
        <div style={{ borderTop: `3px dashed ${colors.muted}`, margin: "30px 0 24px" }} />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 44, fontWeight: 500 }}>
          <span>TOTAL</span>
          <span>{total}</span>
        </div>
        {stamp ? (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "56%",
            translate: "-50% -50%",
            border: `8px solid ${colors.accent}`,
            color: colors.accent,
            fontFamily: fonts.sans,
            fontWeight: 600,
            fontSize: 64,
            lineHeight: 1.05,
            textAlign: "center",
            padding: "14px 30px",
            borderRadius: 14,
            whiteSpace: "pre-line",
            rotate: "-14deg",
            opacity: st > 0.01 ? 0.92 : 0,
            scale: interpolate(st, [0, 1], [2.4, 1]),
            mixBlendMode: "multiply",
          }}
        >
          {stamp}
        </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
