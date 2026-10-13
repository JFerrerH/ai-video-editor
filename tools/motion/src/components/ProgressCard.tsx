import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

/**
 * Progress bar card above the speaker's head.
 * Fills from→to between fillStart..fillEnd (s). `stall` makes it stutter and
 * turn accent-coloured with a warning note (e.g. "tech wasn't there yet").
 */
export const ProgressCard: React.FC<{
  durationInFrames: number;
  label: string;
  from?: number;
  to: number;
  fillStart?: number;
  fillEnd?: number;
  stall?: boolean;
  note?: string;
  mono?: boolean;
  showValue?: boolean; // hide the number when the captions already say it
}> = ({ durationInFrames, label, from = 0, to, fillStart = 0.15, fillEnd = 0.9, stall, note, mono, showValue = true }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 15);
  const out = exit(frame, durationInFrames, 6);
  let v = interpolate(frame, [sec(fillStart, fps), sec(fillEnd, fps)], [from, to], { ...clamp, easing: easeOut });
  const stalled = stall && frame > sec(fillEnd, fps);
  if (stalled) v = to + Math.sin(frame * 1.7) * 1.2; // stutter
  const barColor = stalled ? colors.accent : colors.ink;
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: SAFE.top + 70, filter: mono ? "grayscale(1)" : undefined }}>
      <div
        style={{
          width: 760,
          background: colors.bg,
          borderRadius: 36,
          padding: "34px 44px 40px",
          boxShadow: "0 24px 60px rgba(31,35,40,0.25)",
          opacity: Math.min(1, s * 1.5) * out,
          translate: `0px ${interpolate(s, [0, 1], [-60, 0])}px`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={{ fontFamily: fonts.mono, fontSize: 30, letterSpacing: 4, color: colors.muted }}>{label}</div>
          {showValue ? (
            <div style={{ fontFamily: fonts.serif, fontSize: 92, lineHeight: 1, color: barColor, letterSpacing: -3 }}>
              {Math.round(Math.max(0, v))}%
            </div>
          ) : null}
        </div>
        <div style={{ marginTop: 22, height: 26, borderRadius: 999, background: "rgba(31,35,40,0.1)", overflow: "hidden" }}>
          <div style={{ width: `${Math.max(0, v)}%`, height: "100%", borderRadius: 999, background: barColor }} />
        </div>
        {note ? (
          <div
            style={{
              marginTop: 18,
              fontFamily: fonts.mono,
              fontSize: 26,
              letterSpacing: 2,
              color: colors.accent,
              opacity: stalled ? (Math.floor(frame / 8) % 2 ? 1 : 0.35) : 0,
            }}
          >
            ⚠ {note}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
