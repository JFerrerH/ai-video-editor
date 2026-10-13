import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { useBrand } from "../theme";

/** Big year stamp + a paper document card (thesis, contract, report…). */
export const DocumentCard: React.FC<{
  durationInFrames: number;
  year?: string;
  kicker: string;
  title: string;
  emphasis?: string;
  author?: string;
  cardAt?: number;
  enterFrom?: "below" | "above"; // "above" when floating over footage, so it never crosses the face
}> = ({ durationInFrames, year, kicker, title, emphasis, author, cardAt = 0.35, enterFrom = "below" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const yIn = enter(frame, fps, 0, 11);
  const cIn = enter(frame, fps, sec(cardAt, fps), 16);
  const out = exit(frame, durationInFrames, 5);
  const parts = emphasis ? title.split(emphasis) : [title];
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      {year ? (
      <div
        style={{
          position: "absolute",
          top: 190,
          fontFamily: fonts.serif,
          fontSize: 300,
          lineHeight: 1,
          letterSpacing: -12,
          color: colors.ink,
          scale: interpolate(yIn, [0, 1], [1.6, 1]),
          opacity: Math.min(1, yIn * 2),
        }}
      >
        {year}
      </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          top: year ? 560 : 330,
          width: 700,
          background: "white",
          borderRadius: 18,
          padding: "50px 56px 56px",
          boxShadow: "0 30px 70px rgba(31,35,40,0.2)",
          rotate: `${interpolate(cIn, [0, 1], [8, -2])}deg`,
          translate: `0px ${interpolate(cIn, [0, 1], [enterFrom === "above" ? -700 : 700, 0])}px`,
        }}
      >
        <div style={{ fontFamily: fonts.mono, fontSize: 26, letterSpacing: 5, color: colors.muted }}>{kicker}</div>
        <div style={{ height: 3, width: 90, background: colors.ink, margin: "22px 0 26px" }} />
        <div style={{ fontFamily: fonts.serif, fontSize: 64, lineHeight: 1.08, color: colors.ink, letterSpacing: -1 }}>
          {parts[0]}
          {emphasis ? <span style={{ fontStyle: "italic" }}>{emphasis}</span> : null}
          {parts[1] ?? ""}
        </div>
        {author ? (
          <div style={{ fontFamily: fonts.sans, fontSize: 28, color: colors.muted, marginTop: 30 }}>{author}</div>
        ) : null}
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ height: 12, borderRadius: 6, background: "#ECEAE6", marginTop: 18, width: `${92 - i * 18}%` }} />
        ))}
      </div>
    </AbsoluteFill>
  );
};
