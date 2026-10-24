import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, sec } from "../anim";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";
import { RevealLine, RevealStyle } from "./text";

type Line = { text: string; at?: number; emphasis?: string; size?: number };

/**
 * Kinetic typography: the words ARE the picture.
 *  rise | pop | fade | blur: lines stack and build word by word (each line at its `at`, s from scene start)
 *  slam: one line at a time, big, each replacing the last on its `at` (punchy beats, one idea per line)
 *  type: typewriter with a caret (searches, prompts, code-ish moments)
 * `emphasis` is a substring of the line set in the accent colour (serif italic when font is serif).
 */
export const KineticType: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  lines: Line[];
  style?: RevealStyle | "slam" | "type";
  font?: "serif" | "sans";
  size?: number;
  weight?: number;
  align?: "center" | "left";
  stagger?: number;
  uppercase?: boolean;
}> = ({ durationInFrames, bg, lines, style = "rise", font = "serif", size, weight, align, stagger, uppercase }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, portrait, aspect } = useFrameLayout();
  const base = size ?? (aspect === "16:9" ? 128 : portrait ? 124 : 104);
  const al = align ?? "center";
  const family = font === "serif" ? fonts.serif : fonts.sans;
  const textStyle: React.CSSProperties = {
    fontFamily: family,
    fontWeight: weight ?? (font === "serif" ? 400 : 700),
    color: pal.fg,
    letterSpacing: font === "serif" ? "-0.02em" : "-0.03em",
    lineHeight: 1.04,
    textTransform: uppercase ? "uppercase" : undefined,
  };
  const emph: React.CSSProperties = { color: pal.accent, fontStyle: font === "serif" ? "italic" : undefined };
  const box: React.CSSProperties = {
    position: "absolute",
    left: safe.left,
    right: safe.right,
    top: safe.top,
    bottom: safe.bottom,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: al === "center" ? "center" : "flex-start",
    textAlign: al,
    gap: base * 0.18,
  };

  if (style === "slam") {
    // default cue: lines evenly over the scene
    const cues = lines.map((l, i) => sec(l.at ?? (i * durationInFrames) / fps / lines.length, fps));
    let cur = 0;
    cues.forEach((c, i) => {
      if (frame >= c) cur = i;
    });
    const l = lines[cur];
    const p = spring({ frame: frame - cues[cur], fps, config: { damping: 14, stiffness: 260, mass: 0.6 } });
    const big = l.size ?? base * 1.35;
    return (
      <AbsoluteFill>
        <div style={box}>
          <div style={{ ...textStyle, fontSize: big, scale: interpolate(p, [0, 1], [1.25, 1]), opacity: interpolate(p, [0, 0.3], [0, 1], clamp), justifyContent: "inherit", display: "flex" }}>
            <RevealLine text={l.text} emphasis={l.emphasis} frame={frame} fps={fps} startFrame={cues[cur]} stagger={0} style="fade" emphStyle={emph} />
          </div>
        </div>
      </AbsoluteFill>
    );
  }

  if (style === "type") {
    const cps = 22; // characters per second: fast enough to feel live, slow enough to read
    return (
      <AbsoluteFill>
        <div style={box}>
          {lines.map((l, i) => {
            const start = sec(l.at ?? i * 0.9, fps);
            const n = Math.max(0, Math.floor(((frame - start) / fps) * cps));
            if (frame < start) return null;
            const done = n >= l.text.length;
            const isLast = i === lines.length - 1 || frame < sec(lines[i + 1].at ?? (i + 1) * 0.9, fps);
            const caret = isLast && (!done || Math.floor(frame / 15) % 2 === 0);
            return (
              <div key={i} style={{ ...textStyle, fontSize: l.size ?? base }}>
                {l.text.slice(0, n)}
                <span style={{ opacity: caret ? 1 : 0, color: pal.accent, marginLeft: 4 }}>|</span>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      <div style={box}>
        {lines.map((l, i) => (
          <div key={i} style={{ ...textStyle, fontSize: l.size ?? base, display: "flex", justifyContent: al === "center" ? "center" : "flex-start" }}>
            <RevealLine
              text={l.text}
              emphasis={l.emphasis}
              frame={frame}
              fps={fps}
              startFrame={sec(l.at ?? 0.1 + i * 0.35, fps)}
              stagger={stagger ?? (style === "pop" ? 3 : 2)}
              style={style}
              emphStyle={emph}
            />
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
