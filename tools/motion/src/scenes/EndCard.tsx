import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut } from "../anim";
import { useFrameLayout } from "../layout";
import { textOn, useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";

const STAGGER = 6; // frames between title, tagline, button and url
const FIRST = 8; // the title starts this many frames after the logo

/**
 * Closing card. The `logo` (SVG/PNG from the brand kit, staged by the engine) springs in over a
 * soft glow, then `title`, `tagline`, a CTA pill (`button`, with a drawn arrow) and `url` rise in,
 * in reading order. Button: `ink` on accent/light tones, `accent` on dark.
 */
export const EndCard: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  logo?: string;
  logoHeight?: number;
  title?: string;
  tagline?: string;
  button?: string;
  url?: string;
}> = ({ bg, logo, logoHeight, title, tagline, button, url }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, aspect, portrait, innerW } = useFrameLayout();
  const wide = aspect === "16:9";

  const ls = spring({ frame, fps, config: { damping: 14, stiffness: 150, mass: 0.9 } });
  const rise = (k: number) => interpolate(frame, [FIRST + k * STAGGER, FIRST + k * STAGGER + 14], [0, 1], { ...clamp, easing: easeOut });
  const steps = [title, tagline, button, url].map((x, k, all) => (x ? all.slice(0, k).filter(Boolean).length : -1));
  const style = (k: number): React.CSSProperties => {
    const p = rise(k);
    return { opacity: p, translate: `0px ${(1 - p) * 22}px` };
  };
  const btnFill = bg === "dark" ? colors.accent : colors.ink;
  const btnText = textOn(btnFill, colors.ink);
  const lh = logoHeight ?? (wide ? 150 : portrait ? 190 : 170);
  // the arrow nudges right once everything has landed, then rests
  const nudge = interpolate(frame, [FIRST + 4 * STAGGER + 10, FIRST + 4 * STAGGER + 20, FIRST + 4 * STAGGER + 32], [0, 10, 0], clamp);

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: safe.left,
          right: safe.right,
          top: safe.top,
          bottom: safe.bottom,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
        }}
      >
        {logo ? (
          <div style={{ position: "relative", marginBottom: title || tagline ? 56 : 40, opacity: interpolate(ls, [0, 0.35], [0, 1], clamp), scale: String(interpolate(ls, [0, 1], [0.6, 1])) }}>
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                width: lh * 3.2,
                height: lh * 3.2,
                translate: "-50% -50%",
                borderRadius: "50%",
                background: `radial-gradient(closest-side, ${pal.fg} 0%, transparent 100%)`,
                opacity: 0.15,
              }}
            />
            <Img src={staticFile(logo)} style={{ position: "relative", height: lh, maxWidth: innerW * 0.7, objectFit: "contain", display: "block" }} />
          </div>
        ) : null}
        {title ? (
          <div style={{ fontFamily: fonts.serif, fontSize: wide ? 88 : portrait ? 96 : 84, lineHeight: 1.05, letterSpacing: "-0.02em", color: pal.fg, whiteSpace: "pre-line", ...style(steps[0]) }}>
            {title}
          </div>
        ) : null}
        {tagline ? (
          <div style={{ fontFamily: fonts.sans, fontSize: wide ? 38 : 42, lineHeight: 1.3, color: pal.muted, marginTop: 20, maxWidth: 1000, ...style(steps[1]) }}>{tagline}</div>
        ) : null}
        {button ? (
          <div
            style={{
              marginTop: 52,
              display: "flex",
              alignItems: "center",
              gap: 18,
              padding: "24px 44px",
              borderRadius: 999,
              background: btnFill,
              color: btnText,
              fontFamily: fonts.sans,
              fontSize: wide ? 38 : 42,
              fontWeight: 700,
              lineHeight: 1,
              boxShadow: "0 16px 36px rgba(0,0,0,0.18)",
              ...style(steps[2]),
            }}
          >
            {button}
            <svg width={38} height={28} viewBox="0 0 38 28" style={{ translate: `${nudge}px 0px` }} fill="none" stroke={btnText} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 14h30M22 3l11 11-11 11" />
            </svg>
          </div>
        ) : null}
        {url ? (
          <div style={{ fontFamily: fonts.mono, fontSize: 32, color: pal.muted, marginTop: button ? 30 : 36, letterSpacing: "0.02em", ...style(steps[3]) }}>{url}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
