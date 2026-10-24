import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { clamp, easeOut } from "../anim";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind } from "./Bg";

type Move = "in" | "out" | "left" | "right" | "up" | "down" | "none";

/**
 * A still that never sits still: a slow camera move across the whole scene (Ken Burns).
 * `src` is a path in the public dir (the storyboard engine stages it). `focus` {x, y} (0–1) is
 * what the move centres on: put it on the subject. `amount` is the zoom/pan travel (0.06 subtle,
 * 0.12 default, 0.2 dramatic). Optional `kicker`/`title` set a lower-third over a bottom scrim.
 */
export const ImageScene: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  src: string;
  move?: Move;
  amount?: number;
  focus?: { x: number; y: number };
  kicker?: string;
  title?: string;
  darken?: number;
  mono?: boolean;
}> = ({ durationInFrames, src, move = "in", amount = 0.12, focus = { x: 0.5, y: 0.5 }, kicker, title, darken = 0, mono }) => {
  const frame = useCurrentFrame();
  const { fonts } = useBrand();
  const { safe, width, height, aspect } = useFrameLayout();
  // near-constant speed reads as a camera move; a strong ease reads as an animation
  const t = interpolate(frame, [0, durationInFrames], [0, 1], { ...clamp, easing: Easing.bezier(0.33, 0, 0.67, 1) });
  const z0 = move === "out" ? 1 + amount : move === "in" ? 1 : 1 + amount;
  const z1 = move === "out" ? 1 : 1 + amount;
  const zoom = interpolate(t, [0, 1], [z0, z1]);
  const travel = amount * 0.5; // fraction of the frame to pan, inside the zoom margin
  const dx = move === "left" ? interpolate(t, [0, 1], [travel, -travel]) * width * 0.5 : move === "right" ? interpolate(t, [0, 1], [-travel, travel]) * width * 0.5 : 0;
  const dy = move === "up" ? interpolate(t, [0, 1], [travel, -travel]) * height * 0.5 : move === "down" ? interpolate(t, [0, 1], [-travel, travel]) * height * 0.5 : 0;
  const lt = interpolate(frame, [6, 20], [0, 1], { ...clamp, easing: easeOut });
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000" }}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: `${focus.x * 100}% ${focus.y * 100}%`,
          transformOrigin: `${focus.x * 100}% ${focus.y * 100}%`,
          scale: String(zoom),
          translate: `${dx}px ${dy}px`,
          filter: mono ? "grayscale(1)" : undefined,
        }}
      />
      {darken > 0 ? <AbsoluteFill style={{ background: `rgba(0,0,0,${darken})` }} /> : null}
      {title ? (
        <>
          <AbsoluteFill style={{ background: "linear-gradient(to top, rgba(0,0,0,0.62) 0%, rgba(0,0,0,0) 45%)" }} />
          <div style={{ position: "absolute", left: safe.left, right: safe.right, bottom: safe.bottom + (aspect === "9:16" ? 120 : 0), opacity: lt, translate: `0px ${(1 - lt) * 20}px` }}>
            {kicker ? (
              <div style={{ fontFamily: fonts.sans, fontSize: 32, fontWeight: 600, letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(255,255,255,0.85)", marginBottom: 12 }}>
                {kicker}
              </div>
            ) : null}
            <div style={{ fontFamily: fonts.serif, fontSize: aspect === "16:9" ? 84 : 76, lineHeight: 1.05, letterSpacing: "-0.02em", color: "#fff", whiteSpace: "pre-line" }}>{title}</div>
          </div>
        </>
      ) : null}
    </AbsoluteFill>
  );
};
