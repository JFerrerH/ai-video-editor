import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

type Screen = { src: string; at: number; label?: string };
type Scroll = { src: string; srcWidth: number; from: number; to: number; start: number; end: number; url?: string };

/**
 * Phone with real product screens.
 *  variant "center": big phone (cutaway, pair with full: true); screens swipe in at `at` (s);
 *                    optional `label` pill above the phone changes with each screen.
 *  variant "side":   small tilted phone that pops in beside the speaker's face.
 *  scroll:           shows a full-page website capture scrolling from→to (source px).
 */
export const PhoneMockup: React.FC<{
  durationInFrames: number;
  variant?: "center" | "side";
  side?: "left" | "right";
  screens?: Screen[];
  scroll?: Scroll;
}> = ({ durationInFrames, variant = "center", side = "left", screens = [], scroll }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();

  const center = variant === "center";
  const W = center ? 500 : 300;
  const bezel = center ? 12 : 9;
  const innerW = W - 2 * bezel;
  const innerH = Math.round(innerW * 2.164);
  const H = innerH + 2 * bezel;
  const radius = center ? 64 : 44;

  const s = enter(frame, fps, 0, 15);
  const out = exit(frame, durationInFrames, 6);
  const float = Math.sin(frame / 22) * (center ? 0.6 : 1.2);

  const pos: React.CSSProperties = center
    ? { left: (1080 - W) / 2, top: 222 }
    : { top: 520, ...(side === "left" ? { left: 56 } : { right: SAFE.right }) };

  const enterFrom = center ? `0px ${interpolate(s, [0, 1], [260, 0])}px` : `${(side === "left" ? -1 : 1) * interpolate(s, [0, 1], [420, 0])}px 0px`;
  const baseTilt = center ? 0 : side === "left" ? -7 : 7;

  // active label = last screen whose `at` has passed
  const activeIdx = screens.reduce((acc, sc, i) => (frame >= sec(sc.at, fps) ? i : acc), 0);
  const label = screens[activeIdx]?.label;
  const labelIn = screens.length ? interpolate(frame - sec(screens[activeIdx].at, fps), [0, 8], [0, 1], clamp) : 0;

  return (
    <AbsoluteFill style={{ opacity: out }}>
      {center && label ? (
        <div
          style={{
            position: "absolute",
            top: 160,
            width: "100%",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: 30,
              letterSpacing: 5,
              textTransform: "uppercase",
              color: colors.bg,
              background: colors.ink,
              padding: "10px 26px",
              borderRadius: 999,
              opacity: labelIn * Math.min(1, s * 2),
              translate: `0px ${(1 - labelIn) * 14}px`,
            }}
          >
            {label}
          </div>
        </div>
      ) : null}

      <div
        style={{
          position: "absolute",
          ...pos,
          width: W,
          height: H,
          borderRadius: radius,
          background: colors.ink,
          padding: bezel,
          boxShadow: "0 40px 90px rgba(31,35,40,0.35), 0 8px 20px rgba(31,35,40,0.25)",
          translate: enterFrom,
          rotate: `${baseTilt * s + float}deg`,
          scale: interpolate(s, [0, 1], [0.85, 1]),
          opacity: Math.min(1, s * 2),
        }}
      >
        <div
          style={{
            position: "relative",
            width: innerW,
            height: innerH,
            borderRadius: radius - bezel,
            overflow: "hidden",
            background: colors.bg,
          }}
        >
          {scroll ? (
            <ScrollScreen scroll={scroll} innerW={innerW} />
          ) : (
            screens.map((sc, i) => {
              const t = frame - sec(sc.at, fps);
              const p = i === 0 ? 1 : enter(t, fps, 0, 18);
              if (i > 0 && t < 0) return null;
              return (
                <Img
                  key={i}
                  src={staticFile(sc.src)}
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    translate: `${(1 - p) * innerW}px 0px`,
                    boxShadow: i > 0 ? "-20px 0 40px rgba(0,0,0,0.15)" : undefined,
                  }}
                />
              );
            })
          )}
          {/* dynamic island */}
          <div
            style={{
              position: "absolute",
              top: center ? 12 : 8,
              left: "50%",
              translate: "-50% 0",
              width: innerW * 0.3,
              height: center ? 30 : 20,
              borderRadius: 999,
              background: "#0b0b0c",
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const ScrollScreen: React.FC<{ scroll: Scroll; innerW: number }> = ({ scroll, innerW }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const k = innerW / scroll.srcWidth;
  const y = interpolate(frame, [sec(scroll.start, fps), sec(scroll.end, fps)], [scroll.from, scroll.to], {
    ...clamp,
    easing: easeInOut,
  });
  const bar = scroll.url ? 86 : 0;
  return (
    <>
      <div style={{ position: "absolute", top: bar, left: 0, right: 0, bottom: 0, overflow: "hidden" }}>
        <Img src={staticFile(scroll.src)} style={{ width: innerW, translate: `0px ${-y * k}px` }} />
      </div>
      {scroll.url ? (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: bar,
            background: colors.bg,
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "center",
            paddingBottom: 10,
            borderBottom: "1px solid rgba(31,35,40,0.08)",
          }}
        >
          <div
            style={{
              fontFamily: fonts.sans,
              fontWeight: 500,
              fontSize: 20,
              color: colors.ink,
              background: "rgba(31,35,40,0.07)",
              padding: "6px 22px",
              borderRadius: 999,
            }}
          >
            🔒 {scroll.url}
          </div>
        </div>
      ) : null}
    </>
  );
};
