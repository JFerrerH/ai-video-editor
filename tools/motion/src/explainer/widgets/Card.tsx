import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut } from "../../anim";
import { BgKind } from "../../scenes/Bg";
import { useBrand } from "../../theme";
import { Rect } from "../slots";

/** What every widget gets: its slot, the scene tone, its entrance (`at`) and optional exit (`out`),
 *  all in seconds from the scene start (the engine resolves `@word` cues to numbers). */
export type WidgetBase = { box: Rect; bg?: BgKind; at?: number; out?: number; scale?: number };

export const MIN_TEXT = 28; // px at 1080 short side: nothing in a widget is smaller

/** Card colours that read on each scene tone (a dark scene gets a dark card). */
export const useCardColors = (bg?: BgKind) => {
  const { colors } = useBrand();
  const dark = bg === "dark";
  return {
    dark,
    card: dark ? "#26272A" : "#FFFFFF",
    fg: dark ? "#F5F4F0" : colors.ink,
    muted: dark ? "rgba(245,244,240,0.62)" : colors.muted,
    line: dark ? "rgba(255,255,255,0.10)" : "rgba(26,26,26,0.08)",
    track: dark ? "rgba(255,255,255,0.12)" : "rgba(26,26,26,0.08)",
    accent: colors.accent,
    ok: colors.success,
    shadow: dark ? "0 30px 70px rgba(0,0,0,0.55)" : "0 26px 60px rgba(30,30,20,0.16), 0 2px 6px rgba(30,30,20,0.06)",
  };
};

/** 0→1 entrance spring from `at`, and 1→0 over the 8 frames before `out`. */
export const useEntrance = (at = 0, out?: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = Math.round(at * fps);
  const s = spring({ frame: frame - a, fps, config: { damping: 16, stiffness: 170, mass: 0.8 } });
  const o = out === undefined ? 1 : interpolate(frame, [Math.round(out * fps) - 8, Math.round(out * fps)], [1, 0], { ...clamp, easing: easeOut });
  return { s: frame < a ? 0 : s, o, frame, fps };
};

/** Seconds → frames on the widget's clock. */
export const f = (s: number | undefined, fps: number, d = 0) => Math.round((s ?? d) * fps);

/**
 * The shared widget shell: a rounded card centred in its slot (at most `maxW` wide), with a soft
 * shadow, a spring rise-in at `at` and a fade-out at `out`. `bare` drops the card surface (stamps,
 * badges) but keeps the placement and motion.
 */
export const Card: React.FC<
  WidgetBase & { children: React.ReactNode; maxW?: number; pad?: number; surface?: string; bare?: boolean; align?: "center" | "start" }
> = ({ box, bg, at, out, scale = 1, children, maxW = 760, pad = 40, surface, bare, align = "center" }) => {
  const { s, o } = useEntrance(at, out);
  const c = useCardColors(bg);
  return (
    <div
      style={{
        position: "absolute",
        left: box.x,
        top: box.y,
        width: box.w,
        height: box.h,
        display: "flex",
        alignItems: align === "center" ? "center" : "flex-start",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          width: bare ? undefined : Math.min(box.w, maxW * scale),
          maxHeight: box.h,
          boxSizing: "border-box",
          padding: bare ? 0 : pad * scale,
          borderRadius: bare ? 0 : 30 * scale,
          background: bare ? undefined : (surface ?? c.card),
          boxShadow: bare ? undefined : c.shadow,
          color: c.fg,
          opacity: Math.min(1, s * 1.6) * o,
          translate: `0px ${(1 - s) * 46}px`,
          scale: String(interpolate(s, [0, 1], [0.94, 1])),
        }}
      >
        {children}
      </div>
    </div>
  );
};
