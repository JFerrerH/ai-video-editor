import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, fitSize, readable, useBrand } from "../theme";
import { IconKind, LineIcon } from "./icons";

const CARD_W = 236;

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
  // the title shrinks (44 → 32 px) to fit its card's width on one line, and wraps by word past that
  const titleSize = (t: string) => fitSize(t, { fontFamily: fonts.serif, max: 44, min: 32, width: CARD_W - 36 });
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
                width: CARD_W,
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
                <div style={{ fontFamily: fonts.mono, fontSize: 28, fontWeight: 600, letterSpacing: 4, color: readable(colors.muted, "#FFFFFF", colors.ink), marginTop: 4 }}>{c.kicker}</div>
              ) : null}
              <div style={{ fontFamily: fonts.serif, fontSize: titleSize(c.title), lineHeight: 1.05, color: colors.ink, letterSpacing: -0.5,
                textAlign: "center", overflowWrap: "anywhere", maxWidth: CARD_W - 36 }}>
                {c.title}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
