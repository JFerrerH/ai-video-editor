import React from "react";
import { AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { useBrand } from "../theme";

/** "Too much content": blank social-post cards pile up fast (unlabelled skeletons). Pair with `full`. */
export const PostPile: React.FC<{
  durationInFrames: number;
  count?: number;
  pileStart?: number;
  pileEnd?: number;
  seed?: string;
}> = ({ durationInFrames, count = 10, pileStart = 0.1, pileEnd = 2.2, seed = "pile" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors } = useBrand();
  const out = exit(frame, durationInFrames, 5);
  const skel = "#E6E3DE";
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {Array.from({ length: count }).map((_, i) => {
        const at = sec(pileStart + ((pileEnd - pileStart) * i) / Math.max(1, count - 1), fps);
        if (frame < at) return null;
        const k = enter(frame, fps, at, 14);
        const r = (n: number) => random(`${seed}-${i}-${n}`);
        const x = 540 - 230 + (r(1) - 0.5) * 420;
        const y = 300 + r(2) * 300;
        const rot = (r(3) - 0.5) * 28;
        const tint = i % 2 ? colors.tint1 : colors.tint2;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: 460,
              background: "white",
              borderRadius: 22,
              padding: 22,
              boxShadow: "0 18px 44px rgba(31,35,40,0.22)",
              rotate: `${rot + interpolate(k, [0, 1], [r(4) > 0.5 ? 25 : -25, 0])}deg`,
              translate: `0px ${interpolate(k, [0, 1], [-900, 0])}px`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ width: 54, height: 54, borderRadius: 27, background: tint }} />
              <div style={{ flex: 1 }}>
                <div style={{ height: 14, width: `${50 + r(5) * 30}%`, borderRadius: 7, background: skel }} />
                <div style={{ height: 12, width: "30%", borderRadius: 6, background: skel, marginTop: 8 }} />
              </div>
            </div>
            <div
              style={{
                height: 300,
                borderRadius: 14,
                marginTop: 18,
                background: `linear-gradient(${Math.round(r(6) * 360)}deg, ${colors.tint1}, ${colors.tint2})`,
              }}
            />
            <div style={{ display: "flex", gap: 14, marginTop: 16 }}>
              {[0, 1, 2].map((j) => (
                <div key={j} style={{ width: 34, height: 34, borderRadius: 17, background: skel }} />
              ))}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
