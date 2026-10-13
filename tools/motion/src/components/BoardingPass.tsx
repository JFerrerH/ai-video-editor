import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

/** Boarding pass (travel, conferences, remote work). The plane flies from → to between `flyStart` and `flyEnd` (s). */
export const BoardingPass: React.FC<{
  durationInFrames: number;
  kicker?: string;
  from: string;
  to: string;
  fromCity?: string;
  toCity?: string;
  details?: { k: string; v: string }[];
  flyStart?: number;
  flyEnd?: number;
  top?: number;
}> = ({
  durationInFrames,
  kicker = "BOARDING PASS",
  from,
  to,
  fromCity,
  toCity,
  details = [],
  flyStart = 0.4,
  flyEnd = 2.2,
  top = SAFE.top + 10,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 15);
  const out = exit(frame, durationInFrames, 6);
  const fly = interpolate(frame, [sec(flyStart, fps), sec(flyEnd, fps)], [0, 1], { ...clamp, easing: easeInOut });
  const trackW = 250;
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          width: 760,
          background: "white",
          borderRadius: 26,
          boxShadow: "0 26px 60px rgba(31,35,40,0.28)",
          translate: `0px ${interpolate(s, [0, 1], [-560, 0])}px`,
          rotate: `${interpolate(s, [0, 1], [5, 1.5])}deg`,
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "30px 46px 26px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontFamily: fonts.mono, fontSize: 22, letterSpacing: 5, color: colors.muted }}>
            <span>{kicker}</span>
            <span>LUCCE AIR</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 18 }}>
            <div>
              <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 104, lineHeight: 1, color: colors.ink, letterSpacing: -2 }}>{from}</div>
              {fromCity ? <div style={{ fontFamily: fonts.mono, fontSize: 22, letterSpacing: 3, color: colors.muted, marginTop: 8 }}>{fromCity}</div> : null}
            </div>
            <div style={{ position: "relative", width: trackW, height: 40 }}>
              <div style={{ position: "absolute", top: 19, left: 0, right: 0, borderTop: `3px dotted ${colors.muted}` }} />
              <div style={{ position: "absolute", top: 19, left: 0, width: trackW * fly, borderTop: `3px solid ${colors.ink}` }} />
              <svg
                width="44"
                height="44"
                viewBox="0 0 24 24"
                style={{ position: "absolute", top: -2, left: fly * (trackW - 44) }}
              >
                <path
                  d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"
                  fill={colors.ink}
                  transform="rotate(90 12 12)"
                />
              </svg>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 104, lineHeight: 1, color: colors.ink, letterSpacing: -2 }}>{to}</div>
              {toCity ? <div style={{ fontFamily: fonts.mono, fontSize: 22, letterSpacing: 3, color: colors.muted, marginTop: 8 }}>{toCity}</div> : null}
            </div>
          </div>
        </div>
        {/* perforation */}
        <div style={{ position: "relative", height: 2, margin: "0 30px", borderTop: `3px dashed #DAD8D3` }} />
        <div style={{ display: "flex", justifyContent: "space-between", padding: "22px 46px 30px", background: colors.bg }}>
          {details.map((d, i) => (
            <div key={i}>
              <div style={{ fontFamily: fonts.mono, fontSize: 19, letterSpacing: 4, color: colors.muted }}>{d.k}</div>
              <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 38, color: colors.ink, marginTop: 4 }}>{d.v}</div>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
