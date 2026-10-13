import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit } from "../anim";
import { SAFE, useBrand } from "../theme";

/** Persistent end card: optional kicker + a big pill (@handle, or a CTA such as "Cuéntame abajo 👇"). */
export const HandleCard: React.FC<{ durationInFrames: number; kicker?: string; handle: string; logo?: string }> = ({
  durationInFrames,
  kicker,
  handle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 13);
  const out = exit(frame, durationInFrames, 5);
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: SAFE.top + 30 }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 18,
          opacity: Math.min(1, s * 1.5) * out,
          scale: interpolate(s, [0, 1], [0.7, 1]),
        }}
      >
        {kicker ? (
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 30,
            letterSpacing: 6,
            color: colors.ink,
            background: colors.bg,
            padding: "10px 22px",
            borderRadius: 999,
          }}
        >
          {kicker}
        </div>
        ) : null}
        <div
          style={{
            fontFamily: fonts.sans,
            fontWeight: 600,
            fontSize: 84,
            color: colors.bg,
            background: colors.ink,
            padding: "20px 52px 26px",
            borderRadius: 999,
            letterSpacing: -1,
            boxShadow: "0 20px 50px rgba(0,0,0,0.3)",
          }}
        >
          {handle}
        </div>
      </div>
    </AbsoluteFill>
  );
};
