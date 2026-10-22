import React from "react";
import { useBrand } from "../../theme";
import { Card, f, MIN_TEXT, useEntrance, WidgetBase } from "./Card";

export type TermLine = { text: string; at?: number; kind?: "cmd" | "out" | "ok" };

const CPS = 22; // characters per second: fast enough to feel live, slow enough to read

/**
 * A terminal window. `cmd` lines type at 22 chars/s from their `at` (with a `$` prompt and a caret);
 * `out` lines appear whole at their `at`; `ok` lines appear with a success tick. Lines without `at`
 * follow the previous one (a command's typing time + 0.25 s). Always a dark window.
 */
export const Terminal: React.FC<WidgetBase & { title?: string; lines: TermLine[] }> = ({ title = "terminal", lines, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts, colors } = useBrand();
  const fs = Math.max(MIN_TEXT, Math.min(34, (base.box.h - 170) / (lines.length * 1.55)));
  // start time of each line: explicit, or after the previous one
  const starts: number[] = [];
  lines.forEach((l, i) => {
    const prev = i ? starts[i - 1] + (lines[i - 1].kind === "cmd" || !lines[i - 1].kind ? lines[i - 1].text.length / CPS : 0) + 0.25 : (base.at ?? 0) + 0.35;
    starts.push(l.at ?? prev);
  });
  const live = starts.filter((s) => f(s, fps) <= frame).length - 1;
  return (
    <Card {...base} maxW={860} pad={0} surface="#16181C">
      <div style={{ height: 64, background: "#202328", display: "flex", alignItems: "center", gap: 12, padding: "0 26px", borderRadius: "30px 30px 0 0" }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <div key={c} style={{ width: 18, height: 18, borderRadius: 9, background: c }} />
        ))}
        <div style={{ fontFamily: fonts.mono, fontSize: MIN_TEXT, color: "#9aa0a6", marginLeft: 16 }}>{title}</div>
      </div>
      <div style={{ padding: "28px 34px 34px", fontFamily: fonts.mono, fontSize: fs, lineHeight: 1.55, color: "#E6E6E6", minHeight: lines.length * fs * 1.55 }}>
        {lines.map((l, i) => {
          const a = f(starts[i], fps);
          if (frame < a) return <div key={i} style={{ height: fs * 1.55 }} />;
          const kind = l.kind ?? "cmd";
          const n = kind === "cmd" ? Math.min(l.text.length, Math.floor(((frame - a) / fps) * CPS)) : l.text.length;
          const typing = kind === "cmd" && n < l.text.length;
          const caret = i === live && kind === "cmd" && (typing || Math.floor(frame / 15) % 2 === 0);
          return (
            <div key={i} style={{ whiteSpace: "pre", overflow: "hidden", textOverflow: "clip" }}>
              {kind === "cmd" ? <span style={{ color: colors.accent }}>$ </span> : null}
              {kind === "ok" ? <span style={{ color: "#4ADE80" }}>✓ </span> : null}
              <span style={{ color: kind === "out" ? "#9AA0A6" : kind === "ok" ? "#4ADE80" : undefined }}>{l.text.slice(0, n)}</span>
              {caret ? <span style={{ display: "inline-block", width: "0.55em", height: "1.05em", verticalAlign: "-0.15em", background: "#E6E6E6", marginLeft: 2 }} /> : null}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
