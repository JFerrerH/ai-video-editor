import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { clamp } from "../anim";
import { useBrand } from "../theme";

/** Full-bleed brand gradient used under cutaways (`full: true`). */
export const Backdrop: React.FC<{ durationInFrames: number; mono?: boolean; dark?: boolean }> = ({
  durationInFrames,
  mono,
  dark,
}) => {
  const frame = useCurrentFrame();
  const { colors } = useBrand();
  const drift = interpolate(frame, [0, durationInFrames], [0, 60]);
  const base = dark ? colors.ink : colors.bg;
  return (
    <AbsoluteFill
      style={{
        opacity: interpolate(frame, [0, 3, durationInFrames - 3, durationInFrames], [0, 1, 1, 0], clamp),
        background: base,
        filter: mono ? "grayscale(1)" : undefined,
      }}
    >
      <AbsoluteFill
        style={{
          background: dark
            ? `radial-gradient(900px 900px at ${20 + drift / 6}% 15%, #3E434A 0%, transparent 70%)`
            : `radial-gradient(900px 1000px at ${15 + drift / 5}% 10%, ${colors.tint1} 0%, transparent 65%),
               radial-gradient(1000px 1100px at ${85 - drift / 5}% 95%, ${colors.tint2} 0%, transparent 65%)`,
        }}
      />
    </AbsoluteFill>
  );
};
