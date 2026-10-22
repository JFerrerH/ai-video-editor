import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { Grain } from "../scenes/Bg";
import { useBrand } from "../theme";

export type GridTone = "light" | "dark";

/** Line colour per tone: ≤ 6% luma off the background (≈ 4.7% light, 4.9% dark on the neutral palette). */
export const GRID_LINE: Record<GridTone, string> = { light: "rgba(0,0,0,0.05)", dark: "rgba(255,255,255,0.055)" };

/**
 * Explainer background: the brand's page colour (light) or ink (dark), a faint square grid
 * (64 px pitch at 1080 short side, centred), a soft vignette, and the scene's film grain.
 * The grid must stay a texture, never a pattern you read: keep it within 6% luminance.
 */
export const GridBg: React.FC<{ kind?: GridTone; grain?: number }> = ({ kind = "light", grain = 0 }) => {
  const { width, height } = useVideoConfig();
  const { colors } = useBrand();
  const dark = kind === "dark";
  const pitch = (64 * Math.min(width, height)) / 1080;
  const line = GRID_LINE[kind];
  const off = (n: number) => ((n / 2) % pitch) - 0.5; // a line through the frame centre
  return (
    <AbsoluteFill style={{ background: dark ? colors.ink : colors.bg }}>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(to right, ${line} 1px, transparent 1px), linear-gradient(to bottom, ${line} 1px, transparent 1px)`,
          backgroundSize: `${pitch}px ${pitch}px`,
          backgroundPosition: `${off(width)}px ${off(height)}px`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse ${width * 0.75}px ${height * 0.75}px at 50% 45%, transparent 45%, ${dark ? "rgba(0,0,0,0.38)" : "rgba(40,40,30,0.07)"} 100%)`,
        }}
      />
      {grain > 0 ? <Grain amount={grain} /> : null}
    </AbsoluteFill>
  );
};
