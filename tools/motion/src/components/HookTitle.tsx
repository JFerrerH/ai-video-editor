import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit } from "../anim";
import { SAFE, textOn, useBrand } from "../theme";

type Line = { text: string; emphasis?: string };

/** Opening hook: serif headline on a cream card above the speaker's head.
 *  `emphasis` is a substring of the line rendered italic + accent, or as an accent highlighter block
 *  when the accent is as light (or as dark) as the card and wouldn't read as text on it. */
export const HookTitle: React.FC<{ durationInFrames: number; lines: Line[] }> = ({
  durationInFrames,
  lines,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 14);
  const out = exit(frame, durationInFrames, 6);
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: SAFE.top + 20 }}>
      <div
        style={{
          background: colors.bg,
          borderRadius: 34,
          padding: "28px 44px 32px",
          maxWidth: 1080 - 2 * SAFE.side,
          boxSizing: "border-box",
          boxShadow: "0 24px 60px rgba(31,35,40,0.22)",
          textAlign: "center",
          opacity: Math.min(s * 1.4, 1) * out,
          scale: interpolate(s, [0, 1], [0.8, 1]),
          translate: `0px ${interpolate(s, [0, 1], [-40, 0])}px`,
        }}
      >
        {lines.map((l, i) => {
          const parts = l.emphasis ? l.text.split(l.emphasis) : [l.text];
          const lineIn = interpolate(frame, [3 + i * 4, 10 + i * 4], [0, 1], clamp);
          return (
            <div
              key={i}
              style={{
                fontFamily: fonts.serif,
                fontSize: 64,
                lineHeight: 1.08,
                color: colors.ink,
                letterSpacing: -1.5,
                opacity: lineIn,
                translate: `0px ${(1 - lineIn) * 18}px`,
              }}
            >
              {parts[0]}
              {l.emphasis ? (
                textOn(colors.accent, colors.ink) === textOn(colors.bg, colors.ink) ? (
                  <span style={{ background: colors.accent, color: textOn(colors.accent, colors.ink), padding: "0 10px", borderRadius: 8 }}>
                    {l.emphasis}
                  </span>
                ) : (
                  <span style={{ fontStyle: "italic", color: colors.accent }}>{l.emphasis}</span>
                )
              ) : null}
              {parts[1] ?? ""}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
