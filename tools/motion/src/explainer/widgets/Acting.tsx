import React from "react";
import { interpolate, spring } from "remotion";
import { clamp, easeInOut, easeOut } from "../../anim";
import { IconKind, LineIcon } from "../../components/icons";
import { useFrameLayout } from "../../layout";
import { textOn, useBrand } from "../../theme";
import { SlotName } from "../slots";
import { Card, f, MIN_TEXT, useCardColors, useEntrance, WidgetBase } from "./Card";

/**
 * Something the viewer wants: an icon tile, a name, a price and a buy button. `pressAt` presses the
 * button (it dips and turns to the success colour with a tick), `lockAt` greys the card out and
 * swaps the button text for `lockText`, and `out` makes the whole card shrink and vanish (a poof).
 */
export const ProductCard: React.FC<
  WidgetBase & { name: string; price: string; icon?: IconKind; button?: string; pressAt?: number; pressedText?: string; lockAt?: number; lockText?: string }
> = ({ name, price, icon = "cart", button = "Buy", pressAt, pressedText = "Done", lockAt, lockText = "Wait", ...base }) => {
  const { frame, fps, o } = useEntrance(base.at, base.out);
  const { fonts, colors } = useBrand();
  const c = useCardColors(base.bg);
  const pf = pressAt === undefined ? Infinity : f(pressAt, fps);
  const lf = lockAt === undefined ? Infinity : f(lockAt, fps);
  const pressed = frame >= pf;
  const locked = frame >= lf;
  const dip = pressed ? interpolate(frame - pf, [0, 3, 8], [1, 0.92, 1], clamp) : 1;
  const lockP = locked ? interpolate(frame - lf, [0, 8], [0, 1], { ...clamp, easing: easeOut }) : 0;
  const btnBg = pressed ? colors.success : colors.accent;
  const label = pressed ? pressedText : locked ? lockText : button;
  return (
    <Card {...base} maxW={640} pad={34}>
      <div style={{ scale: String(interpolate(o, [0, 1], [0.8, 1])), opacity: 1 - 0.55 * lockP, filter: `grayscale(${lockP})` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <div style={{ width: 128, height: 128, flex: "none", borderRadius: 26, background: c.track, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <LineIcon kind={icon} size={80} color={c.fg} stroke={1.7} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
            <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 38, color: c.muted }}>{name}</div>
            <div style={{ fontFamily: fonts.sans, fontWeight: 800, fontSize: 72, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums", lineHeight: 1.05 }}>{price}</div>
          </div>
        </div>
        <div
          style={{
            marginTop: 30,
            height: 96,
            borderRadius: 48,
            background: locked && !pressed ? c.track : btnBg,
            color: locked && !pressed ? c.muted : textOn(btnBg, colors.ink),
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            fontFamily: fonts.sans,
            fontWeight: 700,
            fontSize: 44,
            scale: String(dip),
          }}
        >
          {pressed ? <LineIcon kind="check" size={44} color={textOn(btnBg, colors.ink)} stroke={2.6} /> : null}
          {label}
          {!pressed && !locked ? <span style={{ fontWeight: 800 }}>›</span> : null}
        </div>
      </div>
    </Card>
  );
};

/**
 * A day page that flips to the next label on its cue: `pages: [{label, at?, sub?}]` (the first page
 * shows on entrance). The header strip takes the accent; each flip is a 12-frame turn of the page.
 */
export const Calendar: React.FC<WidgetBase & { title?: string; pages: { label: string; at?: number; sub?: string }[] }> = ({ title, pages, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts, colors } = useBrand();
  const c = useCardColors(base.bg);
  const starts = pages.map((p, i) => (i === 0 ? -Infinity : f(p.at, fps)));
  let cur = 0;
  starts.forEach((s, i) => (frame >= s ? (cur = i) : null));
  const t = cur > 0 ? interpolate(frame - starts[cur], [0, 12], [0, 1], { ...clamp, easing: easeInOut }) : 1;
  // first half: the old page turns away; second half: the new one turns in
  const shown = t < 0.5 && cur > 0 ? pages[cur - 1] : pages[cur];
  const angle = t < 0.5 && cur > 0 ? -180 * t : 90 * (1 - Math.min(1, (t - 0.5) * 2)) * (cur > 0 ? 1 : 0);
  const cardW = Math.min(base.box.w, 560);
  // one size for every page (the longest label fits), so the flip doesn't change the type size
  const longest = Math.max(...pages.map((p) => p.label.length));
  const fs = Math.max(MIN_TEXT, Math.min(104, (cardW - 70) / (longest * 0.62)));
  return (
    <Card {...base} maxW={560} pad={0}>
      <div style={{ borderRadius: 30, overflow: "hidden" }}>
        <div style={{ height: 84, background: colors.accent, color: textOn(colors.accent, colors.ink), display: "flex", alignItems: "center", justifyContent: "center", fontFamily: fonts.mono, fontWeight: 600, fontSize: 32, letterSpacing: "0.2em", textTransform: "uppercase" }}>
          {title ?? ""}
        </div>
        <div style={{ perspective: 900, padding: "44px 30px 48px" }}>
          <div style={{ transform: `rotateX(${angle}deg)`, transformOrigin: "50% 0%", textAlign: "center" }}>
            <div style={{ fontFamily: fonts.sans, fontWeight: 800, fontSize: fs, letterSpacing: "-0.03em", lineHeight: 1, whiteSpace: "nowrap" }}>{shown.label}</div>
            {shown.sub ? <div style={{ marginTop: 14, fontFamily: fonts.sans, fontWeight: 600, fontSize: 36, color: c.muted }}>{shown.sub}</div> : null}
          </div>
        </div>
      </div>
    </Card>
  );
};

/**
 * A balance scale with two labelled pans. `tilts: [{to: left|right|level, at}]` swings the beam
 * (±12°, springy) so the named side drops; the lower side's label takes the accent pill.
 */
export const Balance: React.FC<
  WidgetBase & { left: string; right: string; leftIcon?: IconKind; rightIcon?: IconKind; tilts?: { to: "left" | "right" | "level"; at?: number }[] }
> = ({ left, right, leftIcon, rightIcon, tilts = [], ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts, colors } = useBrand();
  const c = useCardColors(base.bg);
  const A = { left: -12, right: 12, level: 0 } as const;
  let ang = 0;
  for (const tl of [...tilts].sort((a, b) => (a.at ?? 0) - (b.at ?? 0))) {
    const s = f(tl.at, fps);
    if (frame < s) break;
    const p = spring({ frame: frame - s, fps, config: { damping: 14, stiffness: 120, mass: 0.9 } });
    ang = ang + (A[tl.to] - ang) * p;
  }
  const W = Math.min(base.box.w, 760);
  const H = Math.min(base.box.h, 440);
  const L = W * 0.36;
  const piv = { x: W / 2, y: H * 0.26 };
  const rad = (ang * Math.PI) / 180;
  const end = (sgn: number) => ({ x: piv.x + sgn * L * Math.cos(rad), y: piv.y + sgn * L * Math.sin(rad) });
  const hang = H * 0.3;
  const heavy = ang > 4 ? 1 : ang < -4 ? -1 : 0;
  const pan = (sgn: number, label: string, icon?: IconKind) => {
    const e = end(sgn);
    const y = e.y + hang;
    const hi = heavy === sgn;
    const fill = hi ? colors.accent : c.card;
    return (
      <g key={sgn}>
        <line x1={e.x} y1={e.y} x2={e.x - 70} y2={y} stroke={c.fg} strokeWidth={4} />
        <line x1={e.x} y1={e.y} x2={e.x + 70} y2={y} stroke={c.fg} strokeWidth={4} />
        <path d={`M ${e.x - 90} ${y} Q ${e.x} ${y + 60} ${e.x + 90} ${y} Z`} fill={c.fg} />
        <foreignObject x={e.x - 150} y={y + 46} width={300} height={90}>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 24px", borderRadius: 999, background: fill, color: hi ? textOn(colors.accent, colors.ink) : c.fg, fontFamily: fonts.sans, fontWeight: 700, fontSize: 40, boxShadow: c.shadow, whiteSpace: "nowrap" }}>
              {icon ? <LineIcon kind={icon} size={40} color={hi ? textOn(colors.accent, colors.ink) : c.fg} stroke={2.2} /> : null}
              {label}
            </div>
          </div>
        </foreignObject>
      </g>
    );
  };
  return (
    <Card {...base} bare>
      <svg width={W} height={H + 70} style={{ overflow: "visible" }}>
        <path d={`M ${piv.x} ${piv.y} L ${piv.x - 46} ${H * 0.86} L ${piv.x + 46} ${H * 0.86} Z`} fill={colors.accent} />
        <rect x={piv.x - 90} y={H * 0.86} width={180} height={14} rx={7} fill={c.fg} />
        <line x1={end(-1).x} y1={end(-1).y} x2={end(1).x} y2={end(1).y} stroke={c.fg} strokeWidth={12} strokeLinecap="round" />
        <circle cx={piv.x} cy={piv.y} r={14} fill={c.fg} />
        {pan(-1, left, leftIcon)}
        {pan(1, right, rightIcon)}
      </svg>
    </Card>
  );
};

/**
 * A thought bubble with an icon or a short text. Three dots trail towards the figure: down in the
 * stacked layouts' `main` slot (the figure is below), right from `side` (the figure is beside it),
 * and right from `main` in 16:9. `tail` overrides. The dots pop in first, then the bubble.
 */
export const ThoughtBubble: React.FC<WidgetBase & { icon?: IconKind; text?: string; slot?: SlotName; tail?: "down" | "right" | "left" }> = ({ icon, text, slot, tail, ...base }) => {
  const { frame, fps, o } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const { aspect } = useFrameLayout();
  const dirn = tail ?? (slot === "side" ? (aspect === "16:9" ? "down" : "right") : aspect === "16:9" ? "right" : "down");
  const a = f(base.at, fps);
  const pop = (d: number) => (frame < a + d ? 0 : spring({ frame: frame - a - d, fps, config: { damping: 12, stiffness: 220, mass: 0.6 } }));
  const fs = Math.max(MIN_TEXT, 46);
  const size = Math.min(base.box.w * 0.8, base.box.h * 0.7, text ? 420 : 300);
  const dots = [0, 1, 2].map((i) => {
    const r = [14, 20, 28][2 - i];
    const off = 40 + i * 46;
    const pos = dirn === "down" ? { left: "50%", top: `calc(100% + ${off - 20}px)` } : dirn === "right" ? { left: `calc(100% + ${off - 20}px)`, top: "70%" } : { right: `calc(100% + ${off - 20}px)`, top: "70%" };
    return <div key={i} style={{ position: "absolute", ...pos, width: r * 2, height: r * 2, marginLeft: -r, marginTop: -r, borderRadius: r, background: c.card, boxShadow: c.shadow, scale: String(pop(i === 2 ? 0 : i === 1 ? 3 : 6)) }} />;
  });
  const b = pop(8);
  return (
    <Card {...base} bare>
      <div style={{ position: "relative", opacity: o }}>
        {dots}
        <div
          style={{
            minWidth: size,
            minHeight: size * 0.62,
            padding: "28px 44px",
            boxSizing: "border-box",
            borderRadius: "50% / 46%",
            background: c.card,
            boxShadow: c.shadow,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 18,
            fontFamily: fonts.sans,
            fontWeight: 700,
            fontSize: fs,
            color: c.fg,
            scale: String(interpolate(b, [0, 1], [0.5, 1])),
            opacity: interpolate(b, [0, 0.3], [0, 1], clamp),
          }}
        >
          {icon ? <LineIcon kind={icon} size={text ? 64 : Math.round(size * 0.36)} color={c.fg} stroke={1.8} /> : null}
          {text ? <span style={{ whiteSpace: "nowrap" }}>{text}</span> : null}
        </div>
      </div>
    </Card>
  );
};
