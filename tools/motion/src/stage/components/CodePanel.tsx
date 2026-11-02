import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { useBrand } from "../../theme";
import { clamp, span, useEventTime } from "../fx";

/** A code window that types itself. Can sit behind the speaker. */
export const CodePanel: React.FC<{
  durationInFrames: number;
  file: string;
  lines: string[];
  typeFrom?: number;
  typeTo?: number;
  badge?: string;
  badgeRange?: number[];
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  scale?: number;
}> = ({ durationInFrames, file, lines, typeFrom = 0.3, typeTo, badge, badgeRange = [1, 14], x = 70, y = 1120, w = 940, h = 700, scale = 1 }) => {
  const { fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const vis = span(t, 0, d, 0.45, 0.35);
  const total = lines.join("\n").length;
  const n = Math.floor(interpolate(t, [typeFrom, typeTo ?? d - 0.4], [0, total], clamp));
  let left = n;
  return (
    <AbsoluteFill style={{ opacity: vis }}>
      <div style={{ position: "absolute", left: x, top: y + (1 - vis) * 120, width: w, height: h, transformOrigin: "0 0", transform: `scale(${scale})`, background: "#1E2127", borderRadius: 30, padding: "30px 40px", boxShadow: "0 30px 70px rgba(0,0,0,.35)" }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
            <div key={c} style={{ width: 20, height: 20, borderRadius: 10, background: c }} />
          ))}
          <div style={{ marginLeft: 20, fontFamily: fonts.mono, fontSize: 32, color: "#B4BAC4" }}>{file}</div>
          {badge ? (
            <div style={{ marginLeft: "auto", fontFamily: fonts.mono, fontSize: 36, fontWeight: 700, color: "#1E2127", background: "#F2F1EE", padding: "6px 16px", borderRadius: 10 }}>
              {badge.replace("{n}", String(Math.round(interpolate(t, [0, d], [badgeRange[0], badgeRange[1]], clamp))))}
            </div>
          ) : null}
        </div>
        <div style={{ marginTop: 34, fontFamily: fonts.mono, fontSize: 36, lineHeight: 1.6, color: "#E6E6E6", whiteSpace: "pre" }}>
          {lines.map((l, i) => {
            const s = l.slice(0, Math.max(0, left));
            left -= l.length + 1;
            return (
              <div key={i}>
                <span style={{ color: "#C9CED8", marginRight: 26 }}>{i + 1}</span>
                {s}
                {left < 0 && left > -l.length - 2 && Math.floor(t * 2) % 2 ? "▍" : ""}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
