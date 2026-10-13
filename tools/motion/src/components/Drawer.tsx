import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, enter, exit, sec } from "../anim";
import { useBrand } from "../theme";

/** A document drops into a drawer, which slams shut at `closeAt` (s). */
export const Drawer: React.FC<{ durationInFrames: number; docTitle: string; closeAt: number }> = ({
  durationInFrames,
  docTitle,
  closeAt,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const out = exit(frame, durationInFrames, 5);
  const drop = interpolate(frame, [2, sec(closeAt, fps) - 4], [0, 1], { ...clamp, easing: easeInOut });
  const close = enter(frame, fps, sec(closeAt, fps) - 5, 12);
  const shake = frame >= sec(closeAt, fps) && frame < sec(closeAt, fps) + 6 ? Math.sin(frame * 3) * 6 : 0;
  const drawerTop = 860;
  const W = 760;
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out, filter: "grayscale(1)", translate: `0px ${shake}px` }}>
      {/* back of the drawer */}
      <div style={{ position: "absolute", top: drawerTop - 120, width: W - 80, height: 140, background: "#2a2d31", borderRadius: "14px 14px 0 0" }} />
      {/* document — clipped at the drawer lip so it disappears inside */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: drawerTop + 30, overflow: "hidden", display: "flex", justifyContent: "center" }}>
        <div
          style={{
            position: "absolute",
            top: interpolate(drop, [0, 1], [260, drawerTop + 40]),
            width: 520,
            height: 560,
            background: "white",
            borderRadius: 12,
            padding: 44,
            boxShadow: "0 20px 50px rgba(0,0,0,0.25)",
            rotate: `${interpolate(drop, [0, 1], [-6, 1])}deg`,
            fontFamily: fonts.serif,
            fontSize: 54,
            lineHeight: 1.1,
            color: colors.ink,
            whiteSpace: "pre-line",
          }}
        >
          {docTitle}
        </div>
      </div>
      {/* drawer body (open) */}
      <div
        style={{
          position: "absolute",
          top: drawerTop + interpolate(close, [0, 1], [0, -90]),
          width: W,
          height: 300,
          background: "#3E434A",
          borderRadius: 18,
          boxShadow: "0 30px 60px rgba(0,0,0,0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          scale: `1 ${interpolate(close, [0, 1], [1, 0.82])}`,
        }}
      >
        <div style={{ width: 200, height: 26, borderRadius: 999, background: "#9aa0a6" }} />
      </div>
    </AbsoluteFill>
  );
};
