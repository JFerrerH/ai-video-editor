import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, sec } from "../anim";
import { IconKind, LineIcon } from "../components/icons";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";

type Item = { text: string; icon?: IconKind; at?: number };

/**
 * Steps / reasons / features revealed one per cue (`at`, s from scene start; default every 0.6 s).
 * marker: "number" (01 02 03), "check" (ticks in on cue), "icon" (each item's line icon), "dot".
 * Earlier items dim slightly when a new one lands, so the eye follows the newest.
 */
export const ListScene: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  kicker?: string;
  title?: string;
  items: Item[];
  marker?: "number" | "check" | "icon" | "dot";
  dimPrevious?: boolean;
}> = ({ bg, kicker, title, items, marker = "number", dimPrevious = true }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, aspect, innerW } = useFrameLayout();
  const wide = aspect === "16:9";
  const head = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: easeOut });
  const cues = items.map((it, i) => sec(it.at ?? 0.5 + i * 0.6, fps));
  const latest = cues.filter((c) => frame >= c).length - 1;
  const fs = wide ? 54 : 60;
  const mk = fs * 1.5;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: safe.left,
          right: safe.right,
          top: safe.top,
          bottom: safe.bottom,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <div style={{ width: Math.min(innerW, wide ? 1300 : 820) }}>
          {kicker ? (
            <div style={{ fontFamily: fonts.sans, fontSize: 32, fontWeight: 600, letterSpacing: "0.2em", textTransform: "uppercase", color: pal.accent, marginBottom: 14, opacity: head }}>
              {kicker}
            </div>
          ) : null}
          {title ? (
            <div style={{ fontFamily: fonts.serif, fontSize: wide ? 80 : 84, lineHeight: 1.05, letterSpacing: "-0.02em", color: pal.fg, marginBottom: 54, opacity: head, translate: `0px ${(1 - head) * 14}px` }}>
              {title}
            </div>
          ) : null}
          <div style={{ display: "flex", flexDirection: "column", gap: wide ? 30 : 38 }}>
            {items.map((it, i) => {
              const p = interpolate(frame, [cues[i], cues[i] + 14], [0, 1], { ...clamp, easing: easeOut });
              const pop = spring({ frame: frame - cues[i] - 3, fps, config: { damping: 11, stiffness: 220, mass: 0.6 } });
              const dim = dimPrevious && i < latest ? 0.45 : 1;
              const markerEl =
                marker === "number" ? (
                  <span style={{ fontFamily: fonts.sans, fontSize: fs * 0.62, fontWeight: 700, color: pal.accent, fontVariantNumeric: "tabular-nums" }}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                ) : marker === "dot" ? (
                  <span style={{ width: fs * 0.32, height: fs * 0.32, borderRadius: 99, background: pal.accent }} />
                ) : (
                  <LineIcon kind={marker === "check" ? "check" : (it.icon ?? "spark")} size={fs * 1.05} color={pal.accent} stroke={2} />
                );
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", opacity: p * dim, translate: `${(1 - p) * -40}px 0px` }}>
                  <div style={{ width: mk, flexShrink: 0, display: "flex", alignItems: "center", scale: String(interpolate(pop, [0, 1], [0.4, 1])) }}>
                    {markerEl}
                  </div>
                  <div style={{ fontFamily: fonts.sans, fontSize: fs, lineHeight: 1.2, fontWeight: 500, color: pal.fg }}>{it.text}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
