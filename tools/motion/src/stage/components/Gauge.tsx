import React from "react";
import { interpolate, spring } from "remotion";
import { accentOn, useBrand } from "../../theme";
import { clamp, inOut, popAt, span, useEventTime } from "../fx";

/** A dial whose needle creeps, then slams to red at `slamAt`, with a stamp. */
export const Gauge: React.FC<{ durationInFrames: number; label: string; stamp: string; slamAt: number; y?: number }> = ({ durationInFrames, label, stamp, slamAt, y = 380 }) => {
  const { colors, fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const vis = span(t, 0, d, 0.4, 0.3);
  const stampColor = accentOn(colors, colors.bg, 6); // 30 px text: well over 4.5:1, thin strokes lose contrast when anti-aliased
  const creep = interpolate(t, [0.25, slamAt - 0.15], [-80, -10], { ...clamp, easing: inOut });
  const slam = t < slamAt ? 0 : spring({ frame: (t - slamAt) * 30, fps: 30, config: { damping: 7, stiffness: 220, mass: 0.6 } });
  const ang = creep + (82 - creep) * slam;
  const st = popAt(t, slamAt + 0.1, 9);
  const arc = (a0: number, a1: number, col: string) => {
    const r = 200;
    const cx = 310;
    const cy = 250;
    const q = (a: number) => [cx + r * Math.cos(((a - 90) * Math.PI) / 180), cy + r * Math.sin(((a - 90) * Math.PI) / 180)];
    const [x0, y0] = q(a0);
    const [x1, y1] = q(a1);
    return <path d={`M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1}`} stroke={col} strokeWidth={34} fill="none" />;
  };
  return (
    <div style={{ position: "absolute", left: 230, top: y, width: 620, height: 420, background: colors.bg, borderRadius: 30, opacity: vis, transform: `translateY(${(1 - vis) * 60}px)`, boxShadow: "0 20px 50px rgba(0,0,0,.3)" }}>
      <div style={{ position: "absolute", top: 26, width: "100%", textAlign: "center", fontFamily: fonts.mono, fontSize: 36, fontWeight: 700, letterSpacing: 3, color: colors.ink }}>{label}</div>
      <svg width={620} height={420} style={{ position: "absolute", top: 40 }}>
        {arc(-90, -30, colors.success)}
        {arc(-30, 30, "#E2A93B")}
        {arc(30, 90, colors.accent)}
        <g transform={`rotate(${ang} 310 250)`}>
          <rect x={304} y={70} width={12} height={185} rx={6} fill={colors.ink} />
        </g>
        <circle cx={310} cy={250} r={22} fill={colors.ink} />
      </svg>
      {st > 0 ? (
        <div data-overhang style={{ position: "absolute", left: 90, top: -34, width: 440, textAlign: "center", transform: `rotate(-4deg) scale(${1.6 - 0.6 * st})`, opacity: Math.min(1, st * 1.5), border: `5px solid ${stampColor}`, color: stampColor, fontFamily: fonts.mono, fontWeight: 700, fontSize: 30, letterSpacing: 2, whiteSpace: "nowrap", padding: "8px 0", borderRadius: 10, background: colors.bg }}>
          {stamp}
        </div>
      ) : null}
    </div>
  );
};
