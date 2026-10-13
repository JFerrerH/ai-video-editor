import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

/** Waitlist sign-up mock: email types in, button presses, success state. */
export const Waitlist: React.FC<{
  durationInFrames: number;
  title: string;
  placeholder: string;
  email: string;
  button: string;
  success: string;
  typeStart?: number;
  typeEnd?: number;
  submitAt: number;
}> = ({ durationInFrames, title, placeholder, email, button, success, typeStart = 0.3, typeEnd = 1.2, submitAt }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 15);
  const out = exit(frame, durationInFrames, 6);
  const n = Math.floor(interpolate(frame, [sec(typeStart, fps), sec(typeEnd, fps)], [0, email.length], clamp));
  const press = interpolate(frame - sec(submitAt, fps), [0, 3, 7], [1, 0.92, 1], clamp);
  const done = enter(frame, fps, sec(submitAt, fps) + 5, 14);
  const isDone = frame >= sec(submitAt, fps) + 5;
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: SAFE.top + 50 }}>
      <div
        style={{
          width: 800,
          background: colors.bg,
          borderRadius: 40,
          padding: "40px 44px 44px",
          boxShadow: "0 24px 60px rgba(31,35,40,0.28)",
          opacity: Math.min(1, s * 1.5) * out,
          translate: `0px ${interpolate(s, [0, 1], [-70, 0])}px`,
        }}
      >
        <div style={{ fontFamily: fonts.serif, fontSize: 62, lineHeight: 1.05, color: colors.ink, letterSpacing: -1, marginBottom: 28 }}>
          {title}
        </div>
        {isDone ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 22,
              fontFamily: fonts.sans,
              fontWeight: 600,
              fontSize: 40,
              color: colors.success,
              height: 196,
              scale: interpolate(done, [0, 1], [0.85, 1]),
              opacity: Math.min(1, 0.35 + done * 2), // never a blank card between press and success
            }}
          >
            <div style={{ width: 72, height: 72, borderRadius: 36, background: colors.success, color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 44 }}>
              ✓
            </div>
            {success}
          </div>
        ) : (
          <>
            <div
              style={{
                background: "white",
                borderRadius: 22,
                padding: "26px 30px",
                fontFamily: fonts.sans,
                fontSize: 36,
                color: n ? colors.ink : "#a0a4a9",
                border: "2px solid rgba(31,35,40,0.08)",
              }}
            >
              {n ? email.slice(0, n) : placeholder}
              {n && n < email.length && Math.floor(frame / 6) % 2 ? "|" : ""}
            </div>
            <div
              style={{
                marginTop: 18,
                background: colors.ink,
                color: colors.bg,
                borderRadius: 999,
                padding: "24px 30px",
                textAlign: "center",
                fontFamily: fonts.sans,
                fontWeight: 600,
                fontSize: 36,
                scale: press,
              }}
            >
              {button}
            </div>
          </>
        )}
      </div>
    </AbsoluteFill>
  );
};
