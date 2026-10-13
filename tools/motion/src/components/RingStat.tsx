import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

/** Ring that fills to `value`% at `fillAt`, pulses at `pulseAt`. */
export const RingStat: React.FC<{
  durationInFrames: number;
  value: number;
  label?: string;
  fillAt?: number;
  pulseAt?: number;
  mono?: boolean;
}> = ({ durationInFrames, value, label, fillAt = 0.1, pulseAt, mono }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 14);
  const out = exit(frame, durationInFrames, 6);
  const v = interpolate(frame, [sec(fillAt, fps), sec(fillAt, fps) + 12], [0, value], { ...clamp, easing: easeOut });
  const pulse = pulseAt !== undefined ? enter(frame, fps, sec(pulseAt, fps), 8) : 0;
  const pulseScale = pulseAt !== undefined && frame >= sec(pulseAt, fps) ? interpolate(pulse, [0, 0.5, 1], [1, 1.18, 1.06]) : 1;
  const R = 150;
  const C = 2 * Math.PI * R;
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: SAFE.top + 40, filter: mono ? "grayscale(1)" : undefined }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 36,
          background: colors.bg,
          borderRadius: 999,
          padding: label ? "26px 56px 26px 26px" : 26,
          boxShadow: "0 24px 60px rgba(0,0,0,0.3)",
          opacity: Math.min(1, s * 1.5) * out,
          scale: interpolate(s, [0, 1], [0.6, 1]) * pulseScale,
        }}
      >
        <div style={{ position: "relative", width: 2 * R + 40, height: 2 * R + 40 }}>
          <svg width={2 * R + 40} height={2 * R + 40} style={{ rotate: "-90deg" }}>
            <circle cx={R + 20} cy={R + 20} r={R} stroke="rgba(31,35,40,0.12)" strokeWidth={34} fill="none" />
            <circle
              cx={R + 20}
              cy={R + 20}
              r={R}
              stroke={colors.ink}
              strokeWidth={34}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={C}
              strokeDashoffset={C * (1 - v / 100)}
            />
          </svg>
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: fonts.serif,
              fontSize: 110,
              color: colors.ink,
              letterSpacing: -4,
            }}
          >
            {Math.round(v)}%
          </div>
        </div>
        {label ? (
          <div style={{ fontFamily: fonts.serif, fontStyle: "italic", fontSize: 92, lineHeight: 0.95, color: colors.ink, whiteSpace: "pre-line" }}>
            {label}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
