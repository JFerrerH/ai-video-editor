import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";
import { LineIcon } from "./icons";

/** Progress as dots on a white card, floating above the head.
 *  variant "steps": a few big circles on a line, each checked at `stops[i]` (s) — "step by step".
 *  variant "days":  `count` small squares filling from `fillStart` to `fillEnd` (s), with a big
 *  `value` label (e.g. 14) and a mono `unit` — a habit tracker. */
export const DotTrack: React.FC<{
  durationInFrames: number;
  variant?: "steps" | "days";
  stops?: number[];
  count?: number;
  fillStart?: number;
  fillEnd?: number;
  value?: string;
  unit?: string;
  top?: number;
}> = ({ durationInFrames, variant = "steps", stops = [], count = 14, fillStart = 0.3, fillEnd = 1.4, value, unit, top = SAFE.top + 40 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 14);
  const out = exit(frame, durationInFrames, 6);
  const card: React.CSSProperties = {
    position: "absolute",
    top,
    background: "white",
    borderRadius: 28,
    boxShadow: "0 22px 50px rgba(31,35,40,0.25)",
    opacity: Math.min(1, s * 1.5),
    translate: `0px ${interpolate(s, [0, 1], [-60, 0])}px`,
  };
  if (variant === "steps") {
    const D = 104;
    const GAP = 120;
    const W = stops.length * D + (stops.length - 1) * GAP;
    // line fill follows the latest stop
    const prog = stops.reduce((acc, t, i) => (i ? acc + interpolate(frame, [sec(t, fps) - 6, sec(t, fps)], [0, 1], { ...clamp, easing: easeInOut }) : acc), 0);
    return (
      <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
        <div style={{ ...card, padding: "36px 46px" }}>
          <div style={{ position: "relative", width: W, height: D }}>
            <div style={{ position: "absolute", top: D / 2 - 4, left: D / 2, width: W - D, height: 8, borderRadius: 4, background: colors.bg }} />
            <div
              style={{
                position: "absolute",
                top: D / 2 - 4,
                left: D / 2,
                width: ((W - D) * prog) / Math.max(1, stops.length - 1),
                height: 8,
                borderRadius: 4,
                background: colors.ink,
              }}
            />
            {stops.map((t, i) => {
              const f0 = sec(t, fps);
              const k = frame >= f0 ? enter(frame, fps, f0, 11) : 0;
              return (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: i * (D + GAP),
                    width: D,
                    height: D,
                    borderRadius: D / 2,
                    boxSizing: "border-box",
                    background: k > 0 ? colors.ink : "white",
                    border: `4px solid ${k > 0 ? colors.ink : colors.bg}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    scale: String(k > 0 ? interpolate(k, [0, 1], [0.8, 1]) : 1),
                  }}
                >
                  {k > 0 ? (
                    <LineIcon kind="check" size={58} color={colors.bg} stroke={3} />
                  ) : (
                    <div style={{ fontFamily: fonts.serif, fontStyle: "italic", fontSize: 44, color: colors.muted }}>{i + 1}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </AbsoluteFill>
    );
  }
  const filled = interpolate(frame, [sec(fillStart, fps), sec(fillEnd, fps)], [0, count], { ...clamp, easing: easeInOut });
  const cols = Math.ceil(count / 2);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div style={{ ...card, padding: "30px 40px", display: "flex", alignItems: "center", gap: 36 }}>
        {value ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div style={{ fontFamily: fonts.serif, fontSize: 110, lineHeight: 0.9, color: colors.ink, letterSpacing: -3 }}>{value}</div>
            {unit ? <div style={{ fontFamily: fonts.mono, fontSize: 22, letterSpacing: 6, color: colors.muted, marginTop: 8 }}>{unit}</div> : null}
          </div>
        ) : null}
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 46px)`, gap: 10 }}>
          {Array.from({ length: count }, (_, i) => {
            const k = Math.max(0, Math.min(1, filled - i));
            return (
              <div key={i} style={{ width: 46, height: 46, borderRadius: 12, background: colors.bg, position: "relative", overflow: "hidden" }}>
                <div style={{ position: "absolute", inset: 0, borderRadius: 12, background: colors.ink, opacity: k, scale: String(0.5 + 0.5 * k) }} />
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
