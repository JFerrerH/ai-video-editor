import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";
import { IconKind, LineIcon } from "./icons";

// "me": your question (ink bubble, abstract text lines — the captions carry the words)
// "ai": the answer (white bubble: an icon + a check = "yes, I can do that")
type Msg = { from: "me" | "ai"; at: number; icon?: IconKind; lines?: number };

/** Talking to your AI: bubbles stack upward from the bottom of a chat column as they arrive.
 *  No readable text — it shows the exchange, not the words.
 *  Default: a cutaway (pair with `full`). `floating`: a compact column above the head, no backdrop,
 *  no header (`bottom` = where the newest bubble settles, default ~700). */
export const ChatThread: React.FC<{ durationInFrames: number; messages: Msg[]; floating?: boolean; bottom?: number }> = ({
  durationInFrames,
  messages,
  floating = false,
  bottom,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors } = useBrand();
  const out = exit(frame, durationInFrames, 5);
  const head = enter(frame, fps, 1, 14);
  const BOTTOM = bottom ?? (floating ? 700 : 1250); // column ends above the caption band (or above the head)
  const ROW = floating ? 128 : 150;
  const BUBBLE = floating ? 0.84 : 1; // compact bubbles when floating
  const fadeTop = floating ? SAFE.top - 20 : SAFE.top + 60;
  const shown = messages.filter((m) => frame >= sec(m.at, fps));
  // smooth upward scroll: each new message pushes the stack by one row
  const lift = messages.reduce((acc, m) => acc + enter(frame, fps, sec(m.at, fps), 16) * ROW, 0);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {/* assistant header */}
      {floating ? null : (
      <div
        style={{
          position: "absolute",
          top: SAFE.top + 10,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          opacity: head,
        }}
      >
        <div style={{ width: 96, height: 96, borderRadius: 48, background: colors.ink, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <LineIcon kind="spark" size={54} color={colors.bg} fill={colors.bg} stroke={1} />
        </div>
      </div>
      )}
      <div style={{ position: "absolute", left: SAFE.side - 20, right: SAFE.side - 20, top: 0, height: BOTTOM, overflow: floating ? "visible" : "hidden" }}>
        {shown.map((m, i) => {
          const k = enter(frame, fps, sec(m.at, fps), 13);
          const idx = messages.indexOf(m);
          // newest settles at BOTTOM - ROW (sliding up from BOTTOM); older ones sit one ROW higher each
          const y = BOTTOM - lift + idx * ROW;
          const me = m.from === "me";
          // fade out as it scrolls up under the header
          const fade = interpolate(y, [fadeTop, fadeTop + 120], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                top: y,
                left: 0,
                right: 0,
                display: "flex",
                justifyContent: me ? "flex-end" : "flex-start",
                opacity: Math.min(1, k * 1.5) * fade,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  padding: "26px 32px",
                  borderRadius: me ? "40px 40px 10px 40px" : "40px 40px 40px 10px",
                  background: me ? colors.ink : "white",
                  boxShadow: floating ? "0 16px 36px rgba(31,35,40,0.28)" : "0 12px 30px rgba(31,35,40,0.14)",
                  scale: String(interpolate(k, [0, 1], [0.7, 1]) * BUBBLE),
                  transformOrigin: me ? "right bottom" : "left bottom",
                }}
              >
                {me ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {Array.from({ length: m.lines ?? 2 }, (_, j) => (
                      <div key={j} style={{ width: j ? 220 : 320, height: 16, borderRadius: 8, background: colors.bg, opacity: 0.55 }} />
                    ))}
                  </div>
                ) : (
                  <>
                    <div style={{ width: 72, height: 72, borderRadius: 20, background: colors.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <LineIcon kind={m.icon ?? "spark"} size={44} color={colors.ink} />
                    </div>
                    <div style={{ width: 160, height: 16, borderRadius: 8, background: colors.bg }} />
                    <div style={{ width: 52, height: 52, borderRadius: 26, background: colors.success, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <LineIcon kind="check" size={34} color="white" stroke={3} />
                    </div>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
