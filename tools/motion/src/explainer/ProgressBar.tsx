import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { useBrand } from "../theme";

/** Thin accent bar along the top edge whose length is the elapsed fraction of its event (the engine
 *  spans it over the whole video when the storyboard sets `"progress": true`). */
export const ProgressBar: React.FC<{ durationInFrames: number; height?: number; color?: string }> = ({ durationInFrames, height, color }) => {
  const frame = useCurrentFrame();
  const { width, height: H } = useVideoConfig();
  const { colors } = useBrand();
  const h = height ?? (10 * Math.min(width, H)) / 1080;
  const p = Math.min(1, frame / Math.max(1, durationInFrames - 1));
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width, height: h, background: "rgba(127,127,127,0.18)" }} />
      <div style={{ position: "absolute", left: 0, top: 0, width: width * p, height: h, background: color ?? colors.accent }} />
    </AbsoluteFill>
  );
};
