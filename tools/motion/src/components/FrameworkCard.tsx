import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

type Step = { title: string; lines: string[] };

/** A framework to screenshot: kicker + numbered steps, built up one by one (`stepGap` s apart).
 *  `flashAt` (s): a camera-flash + slight shrink, the "screenshot" moment.
 *  layout "list" (pair with `full`): one card per row, content ends by ~1270.
 *  layout "grid": a compact 2-column block that floats over the footage above the head (no backdrop);
 *  small text on purpose — a short hold makes viewers pause / rewatch to screenshot it. */
export const FrameworkCard: React.FC<{
  durationInFrames: number;
  kicker?: string;
  steps: Step[];
  stepsAt?: number;
  stepGap?: number;
  flashAt?: number;
  layout?: "list" | "grid";
  top?: number;
}> = ({ durationInFrames, kicker, steps, stepsAt = 0.25, stepGap = 0.3, flashAt, layout = "list", top }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const out = exit(frame, durationInFrames, 5);
  const kin = enter(frame, fps, 1, 14);
  const fl = flashAt != null ? sec(flashAt, fps) : Infinity;
  const flash = interpolate(frame, [fl, fl + 1, fl + 8], [0, 0.85, 0], clamp);
  const snap = interpolate(frame, [fl, fl + 3, fl + 10], [1, 0.965, 1], clamp);
  if (layout === "grid") {
    return (
      <AbsoluteFill style={{ opacity: out }}>
        <div
          style={{
            position: "absolute",
            top: top ?? SAFE.top + 10,
            left: SAFE.side - 40,
            right: SAFE.side - 40,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            scale: String(snap),
          }}
        >
          {kicker ? (
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 22,
                letterSpacing: 6,
                color: colors.ink,
                background: colors.bg,
                padding: "8px 20px",
                borderRadius: 999,
                opacity: kin,
              }}
            >
              {kicker}
            </div>
          ) : null}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, width: "100%" }}>
            {steps.map((st, i) => {
              const f0 = sec(stepsAt + i * stepGap, fps);
              const k = enter(frame, fps, f0, 14);
              return (
                <div
                  key={i}
                  style={{
                    background: "white",
                    borderRadius: 22,
                    padding: "18px 20px 20px",
                    borderLeft: `7px solid ${colors.tint1}`,
                    boxShadow: "0 18px 40px rgba(31,35,40,0.28)",
                    opacity: frame < f0 ? 0 : Math.min(1, k * 1.5),
                    translate: `0px ${interpolate(k, [0, 1], [-40, 0])}px`,
                    scale: String(interpolate(k, [0, 1], [0.9, 1])),
                  }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                    <div style={{ fontFamily: fonts.serif, fontStyle: "italic", fontSize: 44, lineHeight: 0.9, color: colors.muted }}>{i + 1}</div>
                    <div style={{ fontFamily: fonts.serif, fontWeight: 650, fontSize: 36, letterSpacing: 1, color: colors.ink }}>
                      {st.title.toUpperCase()}
                    </div>
                  </div>
                  {st.lines.map((l, j) => (
                    <div key={j} style={{ fontFamily: fonts.sans, fontSize: 22, color: colors.muted, marginTop: j ? 2 : 8, lineHeight: 1.25 }}>
                      {l}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
        <AbsoluteFill style={{ background: "white", opacity: flash * 0.8 }} />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div
        style={{
          position: "absolute",
          top: SAFE.top + 10,
          left: SAFE.side - 30,
          right: SAFE.side - 30,
          display: "flex",
          flexDirection: "column",
          gap: 16,
          scale: String(snap),
        }}
      >
        {kicker ? (
          <div
            style={{
              alignSelf: "center",
              fontFamily: fonts.mono,
              fontSize: 26,
              letterSpacing: 7,
              color: colors.muted,
              marginBottom: 6,
              opacity: kin,
            }}
          >
            {kicker}
          </div>
        ) : null}
        {steps.map((st, i) => {
          const f0 = sec(stepsAt + i * stepGap, fps);
          const k = enter(frame, fps, f0, 14);
          return (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 30,
                alignItems: "flex-start",
                background: "white",
                borderRadius: 24,
                padding: "26px 34px 28px 30px",
                borderLeft: `8px solid ${colors.tint1}`,
                boxShadow: "0 14px 34px rgba(31,35,40,0.12)",
                opacity: frame < f0 ? 0 : Math.min(1, k * 1.5),
                translate: `${interpolate(k, [0, 1], [70, 0])}px 0px`,
              }}
            >
              <div style={{ fontFamily: fonts.serif, fontStyle: "italic", fontSize: 76, lineHeight: 0.9, color: colors.muted, width: 52 }}>
                {i + 1}
              </div>
              <div>
                <div style={{ fontFamily: fonts.serif, fontWeight: 650, fontSize: 50, letterSpacing: 1.5, color: colors.ink, lineHeight: 1.05 }}>
                  {st.title.toUpperCase()}
                </div>
                {st.lines.map((l, j) => (
                  <div key={j} style={{ fontFamily: fonts.sans, fontSize: 31, color: colors.muted, marginTop: j ? 2 : 10, lineHeight: 1.25 }}>
                    {l}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <AbsoluteFill style={{ background: "white", opacity: flash }} />
    </AbsoluteFill>
  );
};
