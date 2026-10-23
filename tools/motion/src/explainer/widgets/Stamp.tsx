import React from "react";
import { interpolate, spring } from "remotion";
import { clamp } from "../../anim";
import { LineIcon, IconKind } from "../../components/icons";
import { textOn, useBrand } from "../../theme";
import { Card, f, MIN_TEXT, useCardColors, useEntrance, WidgetBase } from "./Card";

/**
 * A rubber stamp that slams onto whatever is under it at `at`: drops from 2x scale, rotated −8°,
 * with a small overshoot. Use it for a negation ("SKIP IT", "NOT THIS"). Colour: the brand accent,
 * or `color`.
 */
export const Stamp: React.FC<WidgetBase & { text: string; color?: string; rotate?: number }> = ({ text, color, rotate = -8, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts, colors } = useBrand();
  const a = f(base.at, fps);
  const s = spring({ frame: frame - a, fps, config: { damping: 11, stiffness: 260, mass: 0.6 } });
  const col = color ?? colors.accent;
  const fs = Math.min(110, (base.box.w * 0.8) / Math.max(4, text.length * 0.68));
  if (frame < a) return null;
  return (
    <div style={{ position: "absolute", left: base.box.x, top: base.box.y, width: base.box.w, height: base.box.h, display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
      <div
        style={{
          fontFamily: fonts.sans,
          fontWeight: 900,
          fontSize: Math.max(MIN_TEXT, fs),
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: col,
          border: `${Math.max(6, fs * 0.09)}px solid ${col}`,
          borderRadius: fs * 0.16,
          padding: "0.08em 0.34em",
          background: "rgba(255,255,255,0.08)",
          rotate: `${rotate}deg`,
          scale: String(interpolate(s, [0, 1], [2.1, 1])),
          opacity: interpolate(s, [0, 0.25], [0, 0.94], clamp),
          mixBlendMode: base.bg === "dark" ? undefined : "multiply",
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>
    </div>
  );
};

/** A status pill that pops in at `at`: `ok` (success colour + tick), `alert` (accent), `neutral`. */
export const Badge: React.FC<WidgetBase & { text: string; icon?: IconKind; tone?: "ok" | "alert" | "neutral" }> = ({ text, icon, tone = "neutral", ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts, colors } = useBrand();
  const c = useCardColors(base.bg);
  const a = f(base.at, fps);
  const pop = spring({ frame: frame - a, fps, config: { damping: 10, stiffness: 220, mass: 0.55 } });
  const col = tone === "ok" ? c.ok : tone === "alert" ? c.accent : c.fg;
  const fs = 40;
  return (
    <Card {...base} bare>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "16px 34px 16px 18px",
          borderRadius: 999,
          background: c.card,
          boxShadow: c.shadow,
          border: `3px solid ${col}`,
          fontFamily: fonts.sans,
          fontWeight: 700,
          fontSize: fs,
          color: c.fg,
          whiteSpace: "nowrap",
          scale: String(frame < a ? 0 : interpolate(pop, [0, 1], [0.6, 1])),
        }}
      >
        <div style={{ width: 60, height: 60, borderRadius: 30, background: col, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <LineIcon kind={icon ?? (tone === "alert" ? "spark" : "check")} size={38} color={tone === "neutral" ? c.card : textOn(col, colors.ink)} stroke={2.4} />
        </div>
        {text}
      </div>
    </Card>
  );
};
