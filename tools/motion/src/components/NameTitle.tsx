import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { useBrand } from "../theme";

/** Big serif title with no card (a name, or a punch line). Pair with `behind: true` so it sits BEHIND
 *  the speaker's head (the engine stacks a person-matted copy of the footage on top): set `top` so the
 *  lower part of the letters overlaps the head. Rises into place from behind the head.
 *  `lines[{text, at}]` instead of `text`: several centred lines, each rising on its own cue (s). */
export const NameTitle: React.FC<{
  durationInFrames: number;
  text?: string;
  lines?: { text: string; at?: number }[];
  color?: string;
  size?: number;
  weight?: number;
  top?: number;
  italic?: boolean;
}> = ({ durationInFrames, text, lines, color, size = 210, weight = 600, top = 470, italic = false }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const out = exit(frame, durationInFrames, 6);
  const rows = lines ?? [{ text: text ?? "", at: 0 }];
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div style={{ position: "absolute", top, display: "flex", flexDirection: "column", alignItems: "center", opacity: out }}>
        {rows.map((r, i) => {
          const f0 = sec(r.at ?? 0, fps);
          const s = frame >= f0 ? enter(frame, fps, f0, 15) : 0;
          return (
      <div
        key={i}
        style={{
          fontFamily: fonts.serif,
          fontStyle: italic ? "italic" : "normal",
          fontWeight: weight,
          fontSize: size,
          lineHeight: 1,
          letterSpacing: -4,
          whiteSpace: "nowrap",
          color: color ?? colors.ink,
          // pale colours over a light wall need a soft dark edge to read
          textShadow: "0 2px 4px rgba(0,0,0,0.35), 0 6px 30px rgba(0,0,0,0.3)",
          opacity: Math.min(1, s * 1.4),
          translate: `0px ${interpolate(s, [0, 1], [140, 0])}px`,
        }}
      >
        {r.text}
      </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
