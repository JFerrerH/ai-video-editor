import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

type IconKind = "cap" | "diploma" | "briefcase" | "star";
type Item = { icon: IconKind; at: number; label?: string };

const Glyph: React.FC<{ kind: IconKind; color: string }> = ({ kind, color }) => {
  const p = { fill: "none", stroke: color, strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (kind === "cap")
    return (
      <svg width="78" height="78" viewBox="0 0 24 24">
        <path d="M2 9l10-5 10 5-10 5z" {...p} fill={color} />
        <path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5" {...p} />
        <path d="M22 9v6" {...p} />
      </svg>
    );
  if (kind === "diploma")
    return (
      <svg width="78" height="78" viewBox="0 0 24 24">
        <rect x="3" y="5" width="18" height="12" rx="1.5" {...p} />
        <path d="M7 9h10M7 12h6" {...p} />
        <circle cx="16" cy="16" r="2.6" {...p} fill={color} />
        <path d="M15 18.5l-1 3 2-1 2 1-1-3" {...p} />
      </svg>
    );
  if (kind === "briefcase")
    return (
      <svg width="78" height="78" viewBox="0 0 24 24">
        <rect x="3" y="7" width="18" height="13" rx="2" {...p} />
        <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 12h18" {...p} />
      </svg>
    );
  return (
    <svg width="78" height="78" viewBox="0 0 24 24">
      <path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z" {...p} />
    </svg>
  );
};

/** Life milestones as icons on a line (no numbers: the speaker says them). Each lands at `at` (s). */
export const Milestones: React.FC<{ durationInFrames: number; items: Item[]; top?: number }> = ({
  durationInFrames,
  items,
  top = SAFE.top + 40,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const out = exit(frame, durationInFrames, 6);
  const gap = 250;
  const x0 = 540 - (gap * (items.length - 1)) / 2;
  const D = 150;
  // the line grows to each node as it lands
  const reach = items.reduce((acc, it, i) => {
    const t = interpolate(frame, [sec(it.at, fps) - 6, sec(it.at, fps)], [0, 1], { ...clamp, easing: easeOut });
    return i === 0 ? acc : acc + t * gap;
  }, 0);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div
        style={{
          position: "absolute",
          top: top + D / 2 - 3,
          left: x0,
          width: reach,
          height: 6,
          borderRadius: 3,
          background: "white",
          boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
        }}
      />
      {items.map((it, i) => {
        const f0 = sec(it.at, fps);
        if (frame < f0) return null;
        const k = enter(frame, fps, f0, 11);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x0 + i * gap - D / 2,
              top,
              width: D,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              scale: interpolate(k, [0, 1], [0.3, 1]),
              opacity: Math.min(1, k * 2),
            }}
          >
            <div
              style={{
                width: D,
                height: D,
                borderRadius: D / 2,
                background: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 18px 40px rgba(31,35,40,0.3)",
              }}
            >
              <Glyph kind={it.icon} color={colors.ink} />
            </div>
            {it.label ? (
              <div style={{ marginTop: 14, fontFamily: fonts.mono, fontSize: 24, letterSpacing: 4, color: "white", textShadow: "0 2px 10px rgba(0,0,0,0.5)" }}>
                {it.label}
              </div>
            ) : null}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
