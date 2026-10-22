import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Brand, useBrand } from "../theme";

/** Scene background tones. `none` = transparent (the scene sits on whatever is under it). */
export type BgKind = "light" | "dark" | "accent" | "none";

/** Text colours that read on a given background tone. Scenes take every colour from here,
 *  so one storyboard switches tone without touching the scene props. */
export const paletteFor = (kind: BgKind | undefined, colors: Brand["colors"]) => {
  switch (kind) {
    case "dark":
      return { fg: "#F5F4F0", muted: "rgba(245,244,240,0.62)", accent: colors.accent, track: "rgba(245,244,240,0.14)" };
    case "accent":
      return { fg: "#FFFFFF", muted: "rgba(255,255,255,0.75)", accent: colors.ink, track: "rgba(255,255,255,0.22)" };
    case "none":
      return { fg: "#FFFFFF", muted: "rgba(255,255,255,0.8)", accent: colors.accent, track: "rgba(255,255,255,0.25)" };
    default:
      return { fg: colors.ink, muted: colors.muted, accent: colors.accent, track: "rgba(26,26,26,0.10)" };
  }
};

export const usePalette = (kind?: BgKind) => paletteFor(kind, useBrand().colors);

/** Full-frame brand background with a slow light drift and optional film grain (0–1). */
export const Bg: React.FC<{ kind?: BgKind; grain?: number }> = ({ kind = "light", grain = 0 }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const { colors } = useBrand();
  if (kind === "none") return grain > 0 ? <Grain amount={grain} /> : null;
  const drift = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1]);
  const r = Math.max(width, height);
  const base = kind === "dark" ? colors.ink : kind === "accent" ? colors.accent : colors.bg;
  const glow =
    kind === "dark"
      ? `radial-gradient(${r * 0.7}px ${r * 0.7}px at ${22 + drift * 14}% 18%, rgba(255,255,255,0.10) 0%, transparent 70%),
         radial-gradient(${r * 0.6}px ${r * 0.6}px at ${80 - drift * 10}% 92%, rgba(255,255,255,0.05) 0%, transparent 70%)`
      : kind === "accent"
        ? `radial-gradient(${r * 0.8}px ${r * 0.8}px at ${25 + drift * 12}% 15%, rgba(255,255,255,0.18) 0%, transparent 70%),
           radial-gradient(${r * 0.7}px ${r * 0.7}px at ${80 - drift * 10}% 95%, rgba(0,0,0,0.18) 0%, transparent 70%)`
        : `radial-gradient(${r * 0.6}px ${r * 0.65}px at ${15 + drift * 12}% 10%, ${colors.tint1} 0%, transparent 65%),
           radial-gradient(${r * 0.65}px ${r * 0.7}px at ${85 - drift * 12}% 95%, ${colors.tint2} 0%, transparent 65%)`;
  return (
    <AbsoluteFill style={{ background: base }}>
      <AbsoluteFill style={{ background: glow }} />
      {grain > 0 ? <Grain amount={grain} /> : null}
    </AbsoluteFill>
  );
};

/** Animated film grain: SVG turbulence with a new seed every 2 frames. Keep it subtle (0.3–0.6). */
export const Grain: React.FC<{ amount: number }> = ({ amount }) => {
  const frame = useCurrentFrame();
  const seed = Math.floor(frame / 2) % 97;
  return (
    <AbsoluteFill style={{ opacity: 0.14 * amount, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <svg width="100%" height="100%">
        <filter id={`grain-${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#grain-${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};
