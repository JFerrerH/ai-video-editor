import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";
import { LineIcon } from "./icons";

/** Searching the internet for answers: a search pill types `query`, a spinner turns, and grey
 *  skeleton results stack up below (endless, none of them the answer). Floats above the head. */
export const SearchBar: React.FC<{
  durationInFrames: number;
  query: string;
  typeEnd?: number;
  resultsAt?: number;
  top?: number;
}> = ({ durationInFrames, query, typeEnd = 0.8, resultsAt = 0.9, top = SAFE.top + 30 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 14);
  const out = exit(frame, durationInFrames, 6);
  const n = Math.round(interpolate(frame, [3, sec(typeEnd, fps)], [0, query.length], clamp));
  const rF = sec(resultsAt, fps);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          width: 1080 - 2 * SAFE.side,
          opacity: Math.min(1, s * 1.5),
          translate: `0px ${interpolate(s, [0, 1], [-60, 0])}px`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
            padding: "22px 30px",
            background: "white",
            borderRadius: 999,
            boxShadow: "0 20px 46px rgba(31,35,40,0.25)",
          }}
        >
          <LineIcon kind="search" size={42} color={colors.ink} stroke={2.2} />
          <div style={{ flex: 1, fontFamily: fonts.sans, fontSize: 36, color: colors.ink, whiteSpace: "nowrap", overflow: "hidden" }}>
            {query.slice(0, n)}
            <span style={{ opacity: frame % 16 < 8 ? 1 : 0, color: colors.muted }}>|</span>
          </div>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 17,
              border: `4px solid ${colors.bg}`,
              borderTopColor: colors.ink,
              rotate: `${frame * 14}deg`,
              opacity: frame >= rF ? 1 : 0,
            }}
          />
        </div>
        {[0, 1, 2].map((i) => {
          const f0 = rF + i * 4;
          const k = frame >= f0 ? enter(frame, fps, f0, 14) : 0;
          return (
            <div
              key={i}
              style={{
                marginTop: 12,
                padding: "20px 28px",
                background: "rgba(255,255,255,0.92)",
                borderRadius: 20,
                display: "flex",
                gap: 18,
                alignItems: "center",
                opacity: k,
                translate: `0px ${interpolate(k, [0, 1], [-20, 0])}px`,
              }}
            >
              <div style={{ width: 58, height: 58, borderRadius: 12, background: colors.bg }} />
              <div style={{ flex: 1 }}>
                <div style={{ width: `${70 - i * 12}%`, height: 14, borderRadius: 7, background: colors.muted, opacity: 0.45 }} />
                <div style={{ width: `${88 - i * 6}%`, height: 12, borderRadius: 6, background: colors.bg, marginTop: 12 }} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
