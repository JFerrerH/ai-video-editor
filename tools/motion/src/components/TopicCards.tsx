import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";
import { IconKind, LineIcon } from "./icons";

type Card = { icon: IconKind; kicker?: string; title: string; at: number };

/** A row of small topic cards floating above the head, each popping in on its own cue
 *  (e.g. "how to use AI for X, Y, Z" → three concrete uses). Line icon + mono kicker + serif title. */
export const TopicCards: React.FC<{ durationInFrames: number; cards: Card[]; top?: number }> = ({
  durationInFrames,
  cards,
  top = SAFE.top + 30,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const out = exit(frame, durationInFrames, 6);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div style={{ position: "absolute", top, display: "flex", gap: 24 }}>
        {cards.map((c, i) => {
          const f0 = sec(c.at, fps);
          const k = frame >= f0 ? enter(frame, fps, f0, 12) : 0;
          return (
            <div
              key={i}
              style={{
                width: 236,
                padding: "26px 18px 24px",
                boxSizing: "border-box",
                background: "white",
                borderRadius: 26,
                boxShadow: "0 20px 46px rgba(31,35,40,0.25)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 10,
                opacity: Math.min(1, k * 1.6),
                translate: `0px ${interpolate(k, [0, 1], [-50, 0])}px`,
                scale: String(interpolate(k, [0, 1], [0.8, 1])),
                rotate: `${(i - (cards.length - 1) / 2) * 3}deg`,
              }}
            >
              <div style={{ width: 84, height: 84, borderRadius: 22, background: colors.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <LineIcon kind={c.icon} size={52} color={colors.ink} />
              </div>
              {c.kicker ? (
                <div style={{ fontFamily: fonts.mono, fontSize: 19, letterSpacing: 4, color: colors.muted, marginTop: 4 }}>{c.kicker}</div>
              ) : null}
              <div style={{ fontFamily: fonts.serif, fontSize: 44, lineHeight: 1, color: colors.ink, letterSpacing: -0.5, whiteSpace: "nowrap" }}>
                {c.title}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
