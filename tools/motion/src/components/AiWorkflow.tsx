import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, enter, exit, sec } from "../anim";
import { useBrand } from "../theme";
import { PostPile } from "./PostPile";

/** AI tools & workflows: a robot hub wires up tool nodes (emoji, unlabelled) one by one; optionally,
 *  at `pileAt` (s) the flow fades and content cards pile up ("too much content"). Pair with `full`. */
export const AiWorkflow: React.FC<{
  durationInFrames: number;
  hub?: string;
  nodes: { emoji: string; at: number }[];
  pileAt?: number;
  pileCount?: number;
}> = ({ durationInFrames, hub = "🤖", nodes, pileAt, pileCount = 11 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors } = useBrand();
  const out = exit(frame, durationInFrames, 5);
  const hubIn = enter(frame, fps, 1, 12);
  const pileF = pileAt != null ? sec(pileAt, fps) : Infinity;
  const flowOut = interpolate(frame, [pileF - 2, pileF + 6], [1, 0], clamp);
  // hub centre and node row (all above the caption band)
  const H = { x: 540, y: 430 };
  const row = 840;
  const xs = nodes.map((_, i) => 540 + (i - (nodes.length - 1) / 2) * 280);
  const N = 170;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <AbsoluteFill style={{ opacity: flowOut, scale: String(interpolate(flowOut, [0, 1], [0.92, 1])) }}>
        <svg width="1080" height="1920" style={{ position: "absolute" }}>
          {nodes.map((n, i) => {
            const t = interpolate(frame, [sec(n.at, fps) - 6, sec(n.at, fps) + 2], [0, 1], { ...clamp, easing: easeInOut });
            const x2 = H.x + (xs[i] - H.x) * t;
            const y2 = H.y + 110 + (row - N / 2 - (H.y + 110)) * t;
            return (
              <line
                key={i}
                x1={H.x}
                y1={H.y + 110}
                x2={x2}
                y2={y2}
                stroke={colors.ink}
                strokeWidth={5}
                strokeLinecap="round"
                strokeDasharray="2 16"
                strokeDashoffset={-frame * 2}
                opacity={t > 0 ? 0.8 : 0}
              />
            );
          })}
          {/* node → node arrows: the "workflow" */}
          {nodes.slice(1).map((n, i) => {
            const t = interpolate(frame, [sec(n.at, fps), sec(n.at, fps) + 8], [0, 1], { ...clamp, easing: easeInOut });
            const a = xs[i] + N / 2 + 8;
            const b = xs[i + 1] - N / 2 - 8;
            return (
              <line key={i} x1={a} y1={row} x2={a + (b - a) * t} y2={row} stroke={colors.ink} strokeWidth={5} strokeLinecap="round" opacity={t > 0 ? 1 : 0} />
            );
          })}
        </svg>
        <div
          style={{
            position: "absolute",
            left: H.x - 120,
            top: H.y - 120,
            width: 240,
            height: 240,
            borderRadius: 120,
            background: "white",
            boxShadow: "0 26px 60px rgba(31,35,40,0.22)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 140,
            scale: String(interpolate(hubIn, [0, 1], [0.3, 1]) * (1 + 0.03 * Math.sin(frame / 4))),
            opacity: Math.min(1, hubIn * 2),
          }}
        >
          {hub}
        </div>
        {nodes.map((n, i) => {
          const f0 = sec(n.at, fps);
          if (frame < f0) return null;
          const k = enter(frame, fps, f0, 11);
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: xs[i] - N / 2,
                top: row - N / 2,
                width: N,
                height: N,
                borderRadius: 36,
                background: "white",
                boxShadow: "0 18px 40px rgba(31,35,40,0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 86,
                scale: String(interpolate(k, [0, 1], [0.3, 1])),
                opacity: Math.min(1, k * 2),
              }}
            >
              {n.emoji}
            </div>
          );
        })}
      </AbsoluteFill>
      {pileAt != null ? (
        <Sequence from={pileF} layout="none">
          <PostPile durationInFrames={durationInFrames - pileF} count={pileCount} pileStart={0} pileEnd={Math.max(0.6, (durationInFrames - pileF) / fps - 0.5)} />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};
