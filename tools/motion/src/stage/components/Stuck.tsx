import React from "react";
import { interpolate } from "remotion";
import { accentOn, useBrand } from "../../theme";
import { clamp, ease, ramp, span, useEventTime } from "../fx";

/** A progress bar that stalls, then shows its result at `resultAt`. */
export const Stuck: React.FC<{
  durationInFrames: number;
  label: string;
  stopAt?: number;
  resultAt: number;
  resultTag: string;
  result: string;
  resultItalic?: string;
  y?: number;
}> = ({ durationInFrames, label, stopAt = 0.14, resultAt, resultTag, result, resultItalic, y = 260 }) => {
  const { colors, fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const vis = span(t, 0, d, 0.35, 0.2);
  const warn = accentOn(colors, colors.bg, 6); // the tag is 26 px text: well over 4.5:1, thin strokes lose contrast when anti-aliased
  const v = interpolate(t, [0.2, 0.8], [0, stopAt], { ...clamp, easing: ease });
  const no = t > resultAt;
  const blink = no ? 0.55 + 0.45 * Math.cos((t - resultAt) * 14) : 1;
  return (
    <div style={{ position: "absolute", left: 170, top: y, width: 740, padding: "30px 40px 36px", background: colors.bg, borderRadius: 26, opacity: vis, transform: `translateY(${(1 - vis) * -50}px)`, boxShadow: "0 18px 44px rgba(0,0,0,.3)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: fonts.mono, fontSize: 26, letterSpacing: 3, color: colors.muted }}>
        <span>{label}</span>
        <span style={{ color: no ? warn : colors.muted, fontWeight: no ? 700 : 400 }}>{no ? resultTag : `${Math.round(v * 100)}%`}</span>
      </div>
      <div style={{ height: 22, background: "#E3E0DA", borderRadius: 11, marginTop: 20, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${v * 100}%`, background: no ? colors.accent : colors.ink, opacity: blink, borderRadius: 11 }} />
      </div>
      <div style={{ fontFamily: fonts.serif, fontSize: 52, color: warn, marginTop: 18, opacity: no ? ramp(t, resultAt, 0.25) : 0 }}>
        {result} {resultItalic ? <i>{resultItalic}</i> : null}
      </div>
    </div>
  );
};
