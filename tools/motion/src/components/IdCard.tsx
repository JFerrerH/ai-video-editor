import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

// icon: "pin" | "swap" | "dot" draws a glyph; any other string (an emoji) is shown as text
type Row = { icon?: string; text: string; at: number };

const Icon: React.FC<{ kind?: string; color: string }> = ({ kind, color }) => {
  if (kind === "pin")
    return (
      <svg width="30" height="30" viewBox="0 0 24 24">
        <path d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7z" fill={color} />
        <circle cx="12" cy="9" r="2.6" fill="white" />
      </svg>
    );
  if (kind === "swap")
    return (
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 8h15l-4-4M20 16H5l4 4" />
      </svg>
    );
  if (kind && kind !== "dot") return <span style={{ fontSize: 30, lineHeight: 1 }}>{kind}</span>;
  return <div style={{ width: 14, height: 14, borderRadius: 7, background: color }} />;
};

/** Identity card (name / origin / roles) that floats above the head; subtitle and rows pop in on cue. */
export const IdCard: React.FC<{
  durationInFrames: number;
  kicker?: string;
  title: string;
  subtitle?: string;
  subtitleAt?: number;
  rows?: Row[];
  top?: number;
  width?: number;
}> = ({ durationInFrames, kicker, title, subtitle, subtitleAt = 0, rows = [], top = SAFE.top + 10, width = 720 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 15);
  const out = exit(frame, durationInFrames, 6);
  const sub = enter(frame, fps, sec(subtitleAt, fps), 13);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          width,
          background: "white",
          borderRadius: 22,
          padding: "34px 40px 34px",
          boxShadow: "0 26px 60px rgba(31,35,40,0.28)",
          translate: `0px ${interpolate(s, [0, 1], [-520, 0])}px`,
          rotate: `${interpolate(s, [0, 1], [-6, -1.5])}deg`,
        }}
      >
        {kicker ? <div style={{ fontFamily: fonts.mono, fontSize: 24, letterSpacing: 5, color: colors.muted }}>{kicker}</div> : null}
        <div style={{ fontFamily: fonts.serif, fontSize: 76, lineHeight: 1.05, color: colors.ink, marginTop: kicker ? 10 : 0, letterSpacing: -1 }}>
          {title}
        </div>
        {subtitle ? (
          <div
            style={{
              fontFamily: fonts.serif,
              fontStyle: "italic",
              fontSize: 38,
              color: colors.muted,
              marginTop: 4,
              opacity: frame < sec(subtitleAt, fps) ? 0 : Math.min(1, sub * 1.6),
            }}
          >
            {subtitle}
          </div>
        ) : null}
        {rows.map((r, i) => {
          const f0 = sec(r.at, fps);
          const k = enter(frame, fps, f0, 13);
          if (frame < f0) return null;
          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                marginTop: i === 0 ? 22 : 12,
                padding: "12px 20px",
                borderRadius: 999,
                background: colors.bg,
                fontFamily: fonts.sans,
                fontSize: 33,
                color: colors.ink,
                opacity: Math.min(1, k * 1.6),
                translate: `${interpolate(k, [0, 1], [-40, 0])}px 0px`,
              }}
            >
              <Icon kind={r.icon} color={colors.ink} />
              {r.text}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
