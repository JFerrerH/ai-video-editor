import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { useBrand } from "../theme";

/** Dark code editor typing lines + a "DAY n" counter that runs dayFrom→dayTo. */
export const CodeEditor: React.FC<{
  durationInFrames: number;
  file: string;
  lines: string[];
  dayLabel?: string;
  dayFrom?: number;
  dayTo?: number;
  countStart?: number;
  countEnd?: number;
}> = ({ durationInFrames, file, lines, dayLabel = "DÍA", dayFrom = 1, dayTo = 14, countStart = 0.3, countEnd = 2 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 16);
  const out = exit(frame, durationInFrames, 5);
  const total = lines.join("\n").length;
  const typed = Math.floor(interpolate(frame, [3, Math.max(4, durationInFrames * 0.7)], [0, total], clamp));
  const day = Math.round(interpolate(frame, [sec(countStart, fps), sec(countEnd, fps)], [dayFrom, dayTo], clamp));
  let left = typed;
  const keyword = (t: string) =>
    t.split(/(\bconst\b|\bawait\b|\breturn\b|\bfunction\b|\bexport\b|"[^"]*")/g).map((p, i) => (
      <span key={i} style={{ color: /^"/.test(p) ? "#F5D2B8" : /^(const|await|return|function|export)$/.test(p) ? "#BCD3E6" : undefined }}>
        {p}
      </span>
    ));
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top: 230,
          width: 900,
          height: 860,
          background: "#16181c",
          borderRadius: 28,
          boxShadow: "0 40px 90px rgba(0,0,0,0.45)",
          overflow: "hidden",
          scale: interpolate(s, [0, 1], [0.9, 1]),
          opacity: Math.min(1, s * 2),
        }}
      >
        <div style={{ height: 70, background: "#202328", display: "flex", alignItems: "center", gap: 14, padding: "0 28px" }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <div key={c} style={{ width: 20, height: 20, borderRadius: 10, background: c }} />
          ))}
          <div style={{ fontFamily: fonts.mono, fontSize: 24, color: "#9aa0a6", marginLeft: 20 }}>{file}</div>
        </div>
        <div style={{ padding: "36px 40px", fontFamily: fonts.mono, fontSize: 31, lineHeight: 1.6, color: "#e6e6e6" }}>
          {lines.map((l, i) => {
            const shown = l.slice(0, Math.max(0, left));
            left -= l.length + 1;
            return (
              <div key={i} style={{ display: "flex", gap: 28, minHeight: 50 }}>
                <span style={{ color: "#555b63", width: 30, textAlign: "right" }}>{i + 1}</span>
                <span style={{ whiteSpace: "pre" }}>
                  {keyword(shown)}
                  {left < 0 && left > -l.length - 2 && Math.floor(frame / 8) % 2 ? <span style={{ background: "#e6e6e6" }}> </span> : null}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          top: 170,
          right: 150,
          background: colors.bg,
          color: colors.ink,
          fontFamily: fonts.mono,
          fontSize: 40,
          letterSpacing: 4,
          padding: "14px 30px",
          borderRadius: 999,
          boxShadow: "0 16px 40px rgba(0,0,0,0.35)",
          rotate: "4deg",
          scale: frame >= sec(countStart, fps) ? 1 : 0,
        }}
      >
        {dayLabel} {day}
      </div>
    </AbsoluteFill>
  );
};
