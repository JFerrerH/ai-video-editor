import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp } from "../anim";
import { useBrand } from "../theme";

/** `emph`: 0 = regular word; same non-zero id = one emphasised phrase. */
export type CapWord = { t: number; text: string; emph?: number; chunk: number };
export type CapChunk = { start: number; end: number };

/**
 * Progressive captions: each word appears on its own spoken timestamp; a
 * chunk (short phrase) clears when the next one starts.
 *  - regular words: literary serif, sentence case — white over footage, ink on
 *    light cutaway backdrops (`lightRanges`). No boxes or panels behind text.
 *  - key phrases (`emph` group): heavier, larger serif in `emphColor` (from the
 *    brand's brand.json `captions`; white by default), ALWAYS alone on screen
 *    (the engine gives each emphasis phrase its own chunk). On light cutaway
 *    backdrops everything renders as plain ink.
 * Rendered as the LAST overlay event so it sits above every other layer
 * (video-use hard rule 1: subtitles last).
 */
export const Captions: React.FC<{
  durationInFrames: number;
  words: CapWord[];
  chunks: CapChunk[];
  lightRanges?: [number, number][];
  top?: number;
  /** [start, end, top] (s, s, px): while a scene's text sits in the caption band, captions move to `top` */
  avoid?: [number, number, number][];
  size?: number;
  emphSize?: number;
  emphColor?: string;
  /** "phrase": a short phrase builds word by word; "word": one word at a time (key phrases stay together) */
  mode?: "phrase" | "word";
  /** key phrases in uppercase (they may then wrap onto a second line instead of overflowing) */
  emphCaps?: boolean;
  emphWeight?: number;
  /** darkness (0–1) of the soft radial shade behind the line over footage (light clothes/walls need more) */
  shade?: number;
}> = ({
  words,
  chunks,
  lightRanges = [],
  top: baseTop = 1300,
  avoid = [],
  size = 58,
  emphSize = 68,
  emphColor = "white",
  mode = "phrase",
  emphCaps = false,
  emphWeight = 600,
  shade = 0.32,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const now = frame / fps;
  const top = avoid.find(([a, b]) => now >= a && now < b)?.[2] ?? baseTop;

  const ci = chunks.findIndex((c) => now >= c.start && now < c.end);
  if (ci < 0) return null;
  const light = lightRanges.some(([a, b]) => now >= a && now < b);

  // group consecutive words of the same emphasis phrase
  const items: CapWord[][] = [];
  for (const w of words.filter((x) => x.chunk === ci)) {
    const last = items[items.length - 1];
    if (last && w.emph && last[0].emph === w.emph) last.push(w);
    else items.push([w]);
  }

  const startFrame = (w: CapWord) => Math.round(w.t * fps) - 1; // land on the syllable
  const reveal = (w: CapWord) =>
    interpolate(frame, [startFrame(w), startFrame(w) + 5], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  // word mode: each chunk pops in as it replaces the previous one
  const chunkPop = mode === "word"
    ? interpolate(frame, [Math.round(chunks[ci].start * fps), Math.round(chunks[ci].start * fps) + 4], [0.86, 1], {
        ...clamp,
        easing: Easing.out(Easing.back(2)),
      })
    : 1;
  // tight dark edge + wide glow: keeps a thin serif (and pale accent colours) legible over light footage
  const shadow = light ? "none" : "0 1px 2px rgba(0,0,0,0.85), 0 2px 6px rgba(0,0,0,0.55), 0 4px 26px rgba(0,0,0,0.6)";

  const word = (w: CapWord, emph: boolean, key: React.Key) => {
    const p = reveal(w);
    return (
      <span
        key={key}
        style={{
          ...wordStyle(fonts.serif, emph && (!light || emphCaps), size, emphSize, emphWeight, emphCaps),
          // light cutaway backdrops: everything plain ink, no accent colour on a background
          color: light ? colors.ink : emph ? emphColor : "white",
          textShadow: shadow,
          opacity: p, // 0 before its time: space stays reserved, the line never reflows
          translate: `0px ${(1 - p) * 10}px`,
        }}
      >
        {w.text}
      </span>
    );
  };

  return (
    <AbsoluteFill>
      {light ? null : (
        // soft shade behind the line: keeps a thin serif legible over busy footage
        <div
          style={{
            position: "absolute",
            top: top - 60,
            left: 90,
            right: 90,
            height: 260,
            background: `radial-gradient(ellipse at center, rgba(0,0,0,${shade}) 0%, rgba(0,0,0,0) 70%)`,
          }}
        />
      )}
      <div style={{ position: "absolute", top, left: 110, right: 150, display: "flex", justifyContent: "center" }}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "baseline",
            columnGap: 14,
            rowGap: 2,
            maxWidth: "100%",
            scale: String(chunkPop),
          }}
        >
          {items.map((it, i) =>
            it[0].emph ? (
              // one unbreakable group so a key phrase never wraps mid-way
              // (caps phrases are wider: they may wrap, but as one centred block)
              <span
                key={i}
                style={
                  emphCaps
                    ? { display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 16, rowGap: 0, maxWidth: 1080 - 2 * 130 }
                    : { whiteSpace: "nowrap", display: "inline-flex", columnGap: 14 }
                }
              >
                {it.map((w, j) => word(w, true, j))}
              </span>
            ) : (
              word(it[0], false, i)
            ),
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const wordStyle = (
  serif: string,
  emph: boolean,
  size: number,
  emphSize: number,
  emphWeight: number,
  emphCaps: boolean,
): React.CSSProperties => ({
  fontFamily: serif,
  fontSize: emph ? emphSize : size,
  fontWeight: emph ? emphWeight : 460,
  textTransform: emph && emphCaps ? "uppercase" : undefined,
  lineHeight: emph && emphCaps ? 1.05 : 1.15,
  letterSpacing: emph ? (emphCaps ? 0.5 : -0.5) : -0.3,
  whiteSpace: "nowrap",
  display: "inline-block",
});
