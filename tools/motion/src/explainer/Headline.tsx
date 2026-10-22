import { measureText } from "@remotion/layout-utils";
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut } from "../anim";
import { useFrameLayout } from "../layout";
import { BgKind, usePalette } from "../scenes/Bg";
import { useBrand } from "../theme";

/** One narration word as tools/storyboard.py injects it: script text (marks stripped), the time it's
 *  spoken (s from the scene start), whether it's `*emphasised*`, and its headline phrase. */
export type HeadWord = { text: string; t: number; emph: boolean; phrase: number };

const WEIGHT = 700;
const TRACK = "-0.02em";
const GAP = 0.27; // em between words
const PILL_X = 0.26; // em of pill padding either side
const RISE = 3; // frames for a word to rise in

/** Base size by aspect, at 1080 px short side. */
const BASE = { "9:16": 80, "16:9": 78, "1:1": 68, "4:5": 72 } as const;

type Unit = { words: HeadWord[]; emph: boolean; w: number; ws: number[] };

/** Greedy wrap of units into lines no wider than `maxW`. */
const wrap = (units: Unit[], gap: number, maxW: number) => {
  const lines: Unit[][] = [];
  let cur: Unit[] = [];
  let w = 0;
  for (const u of units) {
    const add = (cur.length ? gap : 0) + u.w;
    if (cur.length && w + add > maxW) {
      lines.push(cur);
      cur = [u];
      w = u.w;
    } else {
      cur.push(u);
      w += add;
    }
  }
  if (cur.length) lines.push(cur);
  return lines;
};

/**
 * The narration, built on screen word by word as it is spoken, at the top of the safe box.
 * Only the current phrase shows: each word rises in over 3 frames from its spoken time; upcoming
 * words hold their place but stay invisible, so the line never reflows. `*emphasis*` groups sit in
 * one accent pill (white text) that springs in. A phrase wraps to at most 2 lines (the size steps
 * down until it fits) and is replaced by the next phrase when that one's first word is spoken.
 */
export const Headline: React.FC<{ words: HeadWord[]; bg?: BgKind; size?: number; top?: number; align?: "center" | "left" }> = ({
  words,
  bg,
  size,
  top,
  align = "center",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts, colors } = useBrand();
  const pal = usePalette(bg);
  const { safe, innerW, aspect, width, height } = useFrameLayout();
  const f0 = (w: HeadWord) => Math.round(w.t * fps);
  const said = words.filter((w) => f0(w) <= frame);
  if (!said.length) return null;
  const phrase = said[said.length - 1].phrase;
  const ws = words.filter((w) => w.phrase === phrase);

  // units: an emphasis group never breaks across lines
  const units: { words: HeadWord[]; emph: boolean }[] = [];
  for (const w of ws) {
    const u = units[units.length - 1];
    if (w.emph && u?.emph) u.words.push(w);
    else units.push({ words: [w], emph: w.emph });
  }
  const measure = (s: number) => {
    const word = (t: string) => measureText({ text: t, fontFamily: fonts.sans, fontSize: s, fontWeight: WEIGHT, letterSpacing: TRACK }).width;
    return units.map((u) => {
      const ws = u.words.map((w) => word(w.text));
      return { ...u, ws, w: ws.reduce((a, x, i) => a + x + (i ? GAP * s : 0), 0) + (u.emph ? 2 * PILL_X * s : 0) };
    });
  };
  let s = (size ?? BASE[aspect]) * (Math.min(width, height) / 1080);
  let lines = wrap(measure(s), GAP * s, innerW);
  for (let k = 0; k < 8 && lines.length > 2; k++) {
    s *= 0.92;
    lines = wrap(measure(s), GAP * s, innerW);
  }

  const rise = (w: HeadWord) => interpolate(frame, [f0(w), f0(w) + RISE], [0, 1], { ...clamp, easing: easeOut });
  const wordEl = (w: HeadWord, key: number) => {
    const p = rise(w);
    return (
      <span key={key} style={{ display: "inline-block", opacity: p, translate: `0px ${(1 - p) * 0.22}em` }}>
        {w.text}
      </span>
    );
  };
  return (
    <div
      style={{
        position: "absolute",
        left: safe.left,
        right: safe.right,
        top: top ?? safe.top,
        display: "flex",
        flexDirection: "column",
        alignItems: align === "center" ? "center" : "flex-start",
        rowGap: s * 0.14,
        fontFamily: fonts.sans,
        fontWeight: WEIGHT,
        fontSize: s,
        letterSpacing: TRACK,
        lineHeight: 1.12,
        color: pal.fg,
      }}
    >
      {lines.map((line, li) => (
        <div key={li} style={{ display: "flex", columnGap: GAP * s, whiteSpace: "nowrap" }}>
          {line.map((u, ui) => {
            if (!u.emph) return wordEl(u.words[0], ui);
            const start = f0(u.words[0]);
            const pop = spring({ frame: frame - start, fps, config: { damping: 9, stiffness: 210, mass: 0.55 }, durationInFrames: Math.round(0.3 * fps) });
            // the pill grows with the words as they're said; its full width stays reserved (no reflow)
            const shown = u.words.reduce((a, w, wi) => a + rise(w) * (u.ws[wi] + (wi ? GAP * s : 0)), 0);
            return (
              <span
                key={ui}
                style={{
                  position: "relative",
                  display: "inline-flex",
                  columnGap: GAP * s,
                  padding: `0 ${PILL_X}em 0.06em`,
                  color: "#FFFFFF",
                  opacity: frame >= start ? 1 : 0,
                  scale: String(interpolate(pop, [0, 1], [0.6, 1])),
                  transformOrigin: "left center",
                }}
              >
                <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: shown + 2 * PILL_X * s, borderRadius: "0.24em", background: colors.accent }} />
                {u.words.map((w, wi) => (
                  <span key={wi} style={{ position: "relative" }}>
                    {wordEl(w, wi)}
                  </span>
                ))}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};
