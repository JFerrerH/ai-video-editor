import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { clamp } from "../anim";

/** Hard white flash that decays — marks a turn in the story. */
export const Flash: React.FC<{ durationInFrames: number; color?: string }> = ({ durationInFrames, color }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        background: color ?? "white",
        opacity: interpolate(frame, [0, 1, durationInFrames], [0.95, 0.85, 0], clamp),
      }}
    />
  );
};
