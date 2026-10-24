import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut } from "../anim";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";
import { RevealLine } from "./text";

/**
 * Chapter / opening title: small kicker, big serif title (one line per "\n"), an accent rule
 * that draws in, and a supporting line. Staggered entrances: kicker → title → rule → sub.
 */
export const TitleCard: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  kicker?: string;
  title: string;
  emphasis?: string;
  sub?: string;
  align?: "center" | "left";
  size?: number;
}> = ({ bg, kicker, title, emphasis, sub, align, size }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, aspect, portrait } = useFrameLayout();
  const al = align ?? (aspect === "16:9" ? "left" : "center");
  const big = size ?? (aspect === "16:9" ? 136 : portrait ? 136 : 112);
  const k = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: easeOut });
  const lines = title.split("\n");
  const ruleAt = 6 + lines.length * 5;
  const rule = interpolate(frame, [ruleAt, ruleAt + 16], [0, 1], { ...clamp, easing: easeOut });
  const s = interpolate(frame, [ruleAt + 6, ruleAt + 20], [0, 1], { ...clamp, easing: easeOut });
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
          justifyContent: "center",
          alignItems: al === "center" ? "center" : "flex-start",
          textAlign: al,
        }}
      >
        {kicker ? (
          <div
            style={{
              fontFamily: fonts.sans,
              fontSize: aspect === "16:9" ? 30 : 34,
              fontWeight: 600,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: pal.accent,
              marginBottom: 28,
              opacity: k,
              translate: `0px ${(1 - k) * 14}px`,
            }}
          >
            {kicker}
          </div>
        ) : null}
        {lines.map((l, i) => (
          <div
            key={i}
            style={{
              fontFamily: fonts.serif,
              fontSize: big,
              lineHeight: 1.02,
              letterSpacing: "-0.025em",
              color: pal.fg,
              display: "flex",
              justifyContent: al === "center" ? "center" : "flex-start",
            }}
          >
            <RevealLine
              text={l}
              emphasis={emphasis}
              frame={frame}
              fps={fps}
              startFrame={4 + i * 5}
              stagger={2}
              emphStyle={{ fontStyle: "italic", color: pal.accent }}
            />
          </div>
        ))}
        <div style={{ height: 4, width: 140 * rule, background: pal.accent, borderRadius: 2, marginTop: 36, marginBottom: sub ? 30 : 0 }} />
        {sub ? (
          <div
            style={{
              fontFamily: fonts.sans,
              fontSize: aspect === "16:9" ? 42 : portrait ? 54 : 46,
              lineHeight: 1.3,
              color: pal.muted,
              maxWidth: 1100,
              opacity: s,
              translate: `0px ${(1 - s) * 16}px`,
            }}
          >
            {sub}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
