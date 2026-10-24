import React from "react";
import { interpolate } from "remotion";
import { clamp, easeOut } from "../../anim";
import { useBrand } from "../../theme";
import { Card, f, MIN_TEXT, useCardColors, useEntrance, WidgetBase } from "./Card";

export type CheckItem = { text: string; at?: number; state?: "todo" | "done" | "struck" };

/**
 * A to-do list. Items rise in one after another as the card enters; an item with `state: "done"`
 * gets its box ticked at its `at`, `state: "struck"` gets a line drawn through it at its `at` (and
 * dims). Without `at`, the state shows from the start.
 */
export const Checklist: React.FC<WidgetBase & { title?: string; items: CheckItem[] }> = ({ title, items, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const rows = items.length + (title ? 1.2 : 0);
  const fs = Math.max(MIN_TEXT, Math.min(40, (base.box.h - 90) / (rows * 1.75)));
  const a0 = f(base.at, fps);
  return (
    <Card {...base} maxW={720}>
      {title ? <div style={{ fontFamily: fonts.sans, fontWeight: 700, fontSize: fs * 1.05, marginBottom: fs * 0.5 }}>{title}</div> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: fs * 0.55 }}>
        {items.map((it, i) => {
          const rise = interpolate(frame, [a0 + 4 + i * 3, a0 + 14 + i * 3], [0, 1], { ...clamp, easing: easeOut });
          const t = it.at === undefined ? -1e9 : f(it.at, fps);
          const p = interpolate(frame, [t, t + 8], [0, 1], { ...clamp, easing: easeOut });
          const done = it.state === "done";
          const struck = it.state === "struck";
          const box = fs * 1.15;
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: fs * 0.6, opacity: rise, translate: `0px ${(1 - rise) * 16}px` }}>
              <div
                style={{
                  width: box,
                  height: box,
                  flex: "none",
                  borderRadius: box * 0.26,
                  border: `${Math.max(3, fs * 0.09)}px solid ${done && p > 0 ? c.ok : c.muted}`,
                  background: done ? `rgba(47,125,91,${p})` : "transparent",
                  boxSizing: "border-box",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {done ? (
                  <svg width={box * 0.7} height={box * 0.7} viewBox="0 0 24 24">
                    <path d="M4 12.5 9.5 18 20 6.5" fill="none" stroke="#FFFFFF" strokeWidth={3.4} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={26} strokeDashoffset={26 * (1 - p)} />
                  </svg>
                ) : null}
              </div>
              <div style={{ position: "relative", fontFamily: fonts.sans, fontSize: fs, fontWeight: 500, color: c.fg, opacity: struck ? interpolate(p, [0, 1], [1, 0.5]) : 1 }}>
                {it.text}
                {struck ? (
                  <div style={{ position: "absolute", left: -4, top: "54%", height: Math.max(4, fs * 0.11), width: `calc(${p * 100}% + ${8 * p}px)`, background: c.accent, borderRadius: 3 }} />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
