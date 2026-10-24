import React from "react";
import { interpolate, spring } from "remotion";
import { clamp, easeOut } from "../anim";

export type Word = { text: string; emph: boolean };

/** Split a line into words, flagging the ones inside the `emphasis` substring. */
export const words = (text: string, emphasis?: string): Word[] => {
  const at = emphasis ? text.indexOf(emphasis) : -1;
  const [a, b] = at >= 0 ? [at, at + emphasis!.length] : [-1, -1];
  const out: Word[] = [];
  const re = /\S+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const s = m.index;
    const e = s + m[0].length;
    out.push({ text: m[0], emph: at >= 0 && s < b && e > a });
  }
  return out;
};

export type RevealStyle = "rise" | "pop" | "fade" | "blur";

/**
 * One line whose words enter one after another from `startFrame`, `stagger` frames apart.
 *  rise: each word slides up out of a mask (the default; reads as "typeset")
 *  pop:  each word springs up from 60% scale (playful, social)
 *  fade: plain opacity + 12 px drift (calm, documentary)
 *  blur: opacity + de-blur (soft, premium)
 */
export const RevealLine: React.FC<{
  text: string;
  emphasis?: string;
  frame: number;
  fps: number;
  startFrame: number;
  stagger?: number;
  style?: RevealStyle;
  emphStyle?: React.CSSProperties;
  wordGap?: string;
}> = ({ text, emphasis, frame, fps, startFrame, stagger = 2, style = "rise", emphStyle, wordGap = "0.26em" }) => {
  const ws = words(text, emphasis);
  const render = (w: Word, i: number) => {
    const f = frame - startFrame - i * stagger;
    const s = emphStyle && w.emph ? emphStyle : undefined;
    if (style === "rise") {
      const p = interpolate(f, [0, 14], [0, 1], { ...clamp, easing: easeOut });
      return (
        // padding/margin keep descenders and italic overhangs inside the mask
        <span key={i} style={{ display: "inline-block", overflow: "hidden", padding: "0 0.08em 0.14em", margin: "0 -0.08em -0.14em" }}>
          <span style={{ display: "inline-block", translate: `0px ${(1 - p) * 105}%`, ...s }}>{w.text}</span>
        </span>
      );
    }
    if (style === "pop") {
      const p = spring({ frame: f, fps, config: { damping: 12, stiffness: 200, mass: 0.7 } });
      return (
        <span key={i} style={{ display: "inline-block", opacity: interpolate(p, [0, 0.4], [0, 1], clamp), scale: interpolate(p, [0, 1], [0.6, 1]), ...s }}>
          {w.text}
        </span>
      );
    }
    const p = interpolate(f, [0, 12], [0, 1], { ...clamp, easing: easeOut });
    return (
      <span
        key={i}
        style={{
          display: "inline-block",
          opacity: p,
          translate: `0px ${(1 - p) * 12}px`,
          filter: style === "blur" ? `blur(${(1 - p) * 14}px)` : undefined,
          ...s,
        }}
      >
        {w.text}
      </span>
    );
  };
  // an emphasised phrase never breaks across lines: its words wrap as one group
  const groups: { emph: boolean; items: [Word, number][] }[] = [];
  ws.forEach((w, i) => {
    const g = groups[groups.length - 1];
    if (w.emph && g?.emph) g.items.push([w, i]);
    else groups.push({ emph: w.emph, items: [[w, i]] });
  });
  return (
    <span style={{ display: "inline-flex", flexWrap: "wrap", columnGap: wordGap, justifyContent: "inherit" }}>
      {groups.map((g, k) =>
        g.emph && g.items.length > 1 ? (
          <span key={`g${k}`} style={{ display: "inline-flex", columnGap: wordGap, whiteSpace: "nowrap" }}>
            {g.items.map(([w, i]) => render(w, i))}
          </span>
        ) : (
          g.items.map(([w, i]) => render(w, i))
        ),
      )}
    </span>
  );
};
