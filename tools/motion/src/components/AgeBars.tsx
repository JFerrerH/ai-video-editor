import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

type Bar = { value: number; label: string; at: number; highlight?: boolean };

/** Ratio bars (×1 / ×2 / ×3): age gaps, multiples. Each bar grows at `at` (s). Floats above the head. */
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
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          width: 600,
          background: "white",
          borderRadius: 24,
          padding: "30px 44px 30px",
          boxShadow: "0 26px 60px rgba(31,35,40,0.28)",
          translate: `0px ${interpolate(s, [0, 1], [-560, 0])}px`,
          rotate: `${interpolate(s, [0, 1], [-5, -1])}deg`,
        }}
      >
        {caption ? (
          <div style={{ fontFamily: fonts.mono, fontSize: 22, letterSpacing: 5, color: colors.muted, marginBottom: 18 }}>{caption}</div>
        ) : null}
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-around", height: H + 60 }}>
          {bars.map((b, i) => {
            const f0 = sec(b.at, fps);
            const k = frame < f0 ? 0 : enter(frame, fps, f0, 14);
            const h = (H * b.value * k) / max;
            return (
              <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 120 }}>
                <div
                  style={{
                    fontFamily: fonts.sans,
                    fontWeight: 600,
                    fontSize: 44,
                    color: colors.ink,
                    opacity: Math.min(1, k * 2),
                    marginBottom: 10,
                  }}
                >
                  {b.label}
                </div>
                <div
                  style={{
                    width: 104,
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
