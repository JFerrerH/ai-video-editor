import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, sec } from "../anim";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";

/**
 * Hero number: counts from `from` to `value` between `countStart` and `countEnd` (s), then the
 * label rises in. With `max`, a thin bar under the number fills in step (value/max).
 * A number is a headline, not a chart: one stat per scene.
 */
export const StatScene: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  value: number;
  from?: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  locale?: string;
  kicker?: string;
  label?: string;
  max?: number;
  countStart?: number;
  countEnd?: number;
  size?: number;
}> = ({ bg, value, from = 0, prefix = "", suffix = "", decimals = 0, locale = "en-US", kicker, label, max, countStart = 0.15, countEnd = 1.3, size }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, aspect, portrait, innerW } = useFrameLayout();
  const big = size ?? (aspect === "16:9" ? 300 : portrait ? 260 : 230);
  const a = sec(countStart, fps);
  const b = Math.max(a + 1, sec(countEnd, fps));
  const p = interpolate(frame, [a, b], [0, 1], { ...clamp, easing: easeOut });
  const v = from + (value - from) * p;
  const num = v.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  const appear = interpolate(frame, [0, 8], [0, 1], { ...clamp, easing: easeOut });
  const lab = interpolate(frame, [b - 6, b + 10], [0, 1], { ...clamp, easing: easeOut });
  const barW = Math.min(innerW, 760);
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
          textAlign: "center",
        }}
      >
        {kicker ? (
          <div style={{ fontFamily: fonts.sans, fontSize: 30, fontWeight: 600, letterSpacing: "0.2em", textTransform: "uppercase", color: pal.accent, marginBottom: 16, opacity: appear }}>
            {kicker}
          </div>
        ) : null}
        <div
          style={{
            fontFamily: fonts.serif,
            fontSize: big,
            lineHeight: 1,
            letterSpacing: "-0.02em",
            color: pal.fg,
            fontVariantNumeric: "tabular-nums",
            opacity: appear,
            scale: interpolate(appear, [0, 1], [0.92, 1]),
          }}
        >
          {prefix}
          {num}
          <span style={{ color: pal.accent, marginLeft: suffix.length === 1 ? "0.04em" : "0.12em", fontSize: suffix.length > 2 ? "0.45em" : undefined }}>{suffix}</span>
        </div>
        {max ? (
          <div style={{ width: barW, height: 10, borderRadius: 5, background: pal.track, marginTop: 34, overflow: "hidden" }}>
            <div style={{ width: barW * Math.min(1, v / max), height: "100%", background: pal.accent, borderRadius: 5 }} />
          </div>
        ) : null}
        {label ? (
          <div
            style={{
              fontFamily: fonts.sans,
              fontSize: aspect === "16:9" ? 46 : portrait ? 54 : 44,
              lineHeight: 1.25,
              color: pal.muted,
              marginTop: 30,
              maxWidth: Math.min(innerW, 900),
              opacity: lab,
              translate: `0px ${(1 - lab) * 16}px`,
              whiteSpace: "pre-line",
            }}
          >
            {label}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
