import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

/** A vague brief → a disappointing deliverable, floating above the head (no words on it):
 *  0 → a chat bubble with typing dots (the brief), `gridAt` → an empty profile grid,
 *  `fillAt` → tiles fill one by one in clashing colours, `missAt` → the card tilts and wobbles. */
export const ContentGrid: React.FC<{
  durationInFrames: number;
  gridAt: number;
  fillAt: number;
  missAt?: number;
  top?: number;
}> = ({ durationInFrames, gridAt, fillAt, missAt, top = SAFE.top + 20 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors } = useBrand();
  const out = exit(frame, durationInFrames, 6);
  const b = enter(frame, fps, 0, 13);
  const gF = sec(gridAt, fps);
  const g = enter(frame, fps, gF, 14);
  const bubbleOut = interpolate(frame, [gF - 3, gF + 3], [1, 0], clamp);
  const fF = sec(fillAt, fps);
  const mF = missAt != null ? sec(missAt, fps) : Infinity;
  const m = frame >= mF ? enter(frame, fps, mF, 7) : 0;
  const wobble = frame >= mF ? Math.sin((frame - mF) * 0.9) * 3 * Math.exp(-(frame - mF) / 10) : 0;
  // deliberately off: clashing hues, nothing like the brand
  const tiles = ["#7CFF6B", "#8A2BE2", "#FF7A00", "#00C2FF", "#FF2E88", "#FFE600"];
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      {/* the brief: a chat bubble with typing dots */}
      <div
        style={{
          position: "absolute",
          top: top + 90,
          padding: "30px 40px",
          background: "white",
          borderRadius: "40px 40px 40px 10px",
          boxShadow: "0 20px 46px rgba(31,35,40,0.25)",
          display: "flex",
          gap: 16,
          opacity: Math.min(1, b * 1.5) * bubbleOut,
          scale: String(interpolate(b, [0, 1], [0.6, 1])),
        }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              width: 22,
              height: 22,
              borderRadius: 11,
              background: colors.muted,
              opacity: 0.4 + 0.6 * Math.max(0, Math.sin(frame * 0.35 - i * 0.9)),
            }}
          />
        ))}
      </div>
      {/* the deliverable: a 3×2 profile grid */}
      <div
        style={{
          position: "absolute",
          top,
          padding: 22,
          background: "white",
          borderRadius: 28,
          boxShadow: "0 22px 50px rgba(31,35,40,0.25)",
          opacity: frame < gF ? 0 : Math.min(1, g * 1.5),
          translate: `0px ${interpolate(g, [0, 1], [-50, 0])}px`,
          rotate: `${interpolate(m, [0, 1], [0, -4]) + wobble}deg`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
          <div style={{ width: 46, height: 46, borderRadius: 23, background: colors.tint1 }} />
          <div style={{ width: 150, height: 14, borderRadius: 7, background: colors.bg }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 118px)", gap: 8 }}>
          {tiles.map((c, i) => {
            const f0 = fF + i * 3;
            const k = frame >= f0 ? enter(frame, fps, f0, 12) : 0;
            return (
              <div key={i} style={{ width: 118, height: 118, borderRadius: 6, background: colors.bg, position: "relative", overflow: "hidden" }}>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: i % 2 ? c : `repeating-linear-gradient(45deg, ${c} 0 14px, white 14px 28px)`,
                    opacity: k,
                    scale: String(interpolate(k, [0, 1], [0.5, 1])),
                    filter: `saturate(${interpolate(m, [0, 1], [1, 0.55])})`,
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
