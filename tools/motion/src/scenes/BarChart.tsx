import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, sec } from "../anim";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";

type Bar = { label: string; value: number; highlight?: boolean };

/**
 * Horizontal bar chart for a single series (works in every aspect: long labels fit, bars grow
 * left → right). Bars are recessive ink; the bar the story is about gets `highlight` and the
 * accent. Values are text (ink), never the bar colour. Bars grow one after another from `start`
 * (s), `stagger` apart; values count with them. More than ~6 bars won't read in a few seconds.
 */
export const BarChart: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  kicker?: string;
  title?: string;
  bars: Bar[];
  unit?: string;
  prefix?: string;
  decimals?: number;
  max?: number;
  start?: number;
  stagger?: number;
  grow?: number;
}> = ({ bg, kicker, title, bars, unit = "", prefix = "", decimals = 0, max, start = 0.35, stagger = 0.18, grow = 0.8 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, aspect, innerW } = useFrameLayout();
  const wide = aspect === "16:9";
  const top = Math.max(...bars.map((b) => b.value), max ?? 0) || 1;
  const labelW = wide ? 340 : 0; // wide: labels in a left column; tall: labels above each bar
  const valueW = wide ? 190 : 170;
  const trackW = Math.min(innerW, wide ? 1500 : 900) - labelW - valueW;
  const barH = wide ? 50 : 60;
  const head = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: easeOut });
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: safe.left,
          right: safe.right,
          top: safe.top,
          bottom: safe.bottom,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <div style={{ width: labelW + trackW + valueW }}>
          {kicker ? (
            <div style={{ fontFamily: fonts.sans, fontSize: 32, fontWeight: 600, letterSpacing: "0.2em", textTransform: "uppercase", color: pal.accent, marginBottom: 14, opacity: head }}>
              {kicker}
            </div>
          ) : null}
          {title ? (
            <div style={{ fontFamily: fonts.serif, fontSize: wide ? 72 : 84, lineHeight: 1.05, letterSpacing: "-0.02em", color: pal.fg, marginBottom: 56, opacity: head, translate: `0px ${(1 - head) * 14}px` }}>
              {title}
            </div>
          ) : null}
          <div style={{ display: "flex", flexDirection: "column", gap: wide ? 26 : 34 }}>
            {bars.map((b, i) => {
              const a = sec(start + i * stagger, fps);
              const p = interpolate(frame, [a, a + sec(grow, fps)], [0, 1], { ...clamp, easing: easeOut });
              const show = interpolate(frame, [a - 4, a + 6], [0, 1], clamp);
              const v = (b.value * p).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
              const label = (
                <div style={{ fontFamily: fonts.sans, fontSize: wide ? 34 : 42, color: b.highlight ? pal.fg : pal.muted, fontWeight: b.highlight ? 700 : 500, opacity: show }}>
                  {b.label}
                </div>
              );
              return (
                <div key={i}>
                  {!wide ? <div style={{ marginBottom: 10 }}>{label}</div> : null}
                  <div style={{ display: "flex", alignItems: "center" }}>
                    {wide ? <div style={{ width: labelW, paddingRight: 24, boxSizing: "border-box", textAlign: "right" }}>{label}</div> : null}
                    <div style={{ width: trackW, height: barH, position: "relative" }}>
                      {/* baseline-anchored bar, rounded only at the data end */}
                      <div
                        style={{
                          position: "absolute",
                          left: 0,
                          top: 0,
                          height: barH,
                          width: Math.max(2, (trackW * b.value * p) / top),
                          borderRadius: "0 6px 6px 0",
                          background: b.highlight ? pal.accent : pal.fg,
                          opacity: b.highlight ? 1 : 0.22,
                        }}
                      />
                    </div>
                    <div
                      style={{
                        width: valueW,
                        paddingLeft: 20,
                        boxSizing: "border-box",
                        fontFamily: fonts.sans,
                        fontSize: wide ? 36 : 44,
                        fontWeight: b.highlight ? 700 : 500,
                        color: b.highlight ? pal.fg : pal.muted,
                        fontVariantNumeric: "tabular-nums",
                        opacity: show,
                      }}
                    >
                      {prefix}
                      {v}
                      {unit}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
