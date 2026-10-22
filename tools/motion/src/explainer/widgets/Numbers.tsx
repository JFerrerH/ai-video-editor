import React from "react";
import { interpolate, spring } from "remotion";
import { clamp, easeInOut, easeOut } from "../../anim";
import { useBrand } from "../../theme";
import { Card, f, MIN_TEXT, useCardColors, useEntrance, WidgetBase } from "./Card";

const fmt = (v: number, decimals: number, locale: string) => v.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

/** 0→1 between `start` and `end` (s), eased; 0 before, 1 after. */
const useRun = (frame: number, fps: number, start: number, end: number, easing = easeOut) =>
  interpolate(frame, [f(start, fps), Math.max(f(start, fps) + 1, f(end, fps))], [0, 1], { ...clamp, easing });

/**
 * A number that counts from `from` to `to` between `start` and `end` (say the number while it
 * moves), with a label and an optional sparkline that draws in step. Reads exactly `from` before
 * `start` and exactly `to` after `end`.
 */
export const Counter: React.FC<
  WidgetBase & { label?: string; from?: number; to: number; start?: number; end?: number; prefix?: string; suffix?: string; decimals?: number; locale?: string; spark?: boolean | number[] }
> = ({ label, from = 0, to, start, end, prefix = "", suffix = "", decimals = 0, locale = "en-US", spark, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const s0 = start ?? (base.at ?? 0) + 0.2;
  const p = useRun(frame, fps, s0, end ?? s0 + 1.2);
  // while it runs, the readout stays one display step inside the range: never `to` early, never `from` late
  const step = Math.sign(to - from) * 10 ** -decimals;
  const run = from + (to - from) * p;
  const shown = p <= 0 ? from : p >= 1 ? to : step > 0 ? Math.min(to - step, Math.max(from + step, run)) : Math.max(to - step, Math.min(from + step, run));
  const big = Math.max(MIN_TEXT, Math.min(150, base.box.h * 0.32, base.box.w / Math.max(3, (prefix + fmt(to, decimals, locale) + suffix).length * 0.62)));
  const pts = Array.isArray(spark) ? spark : [3, 4, 3.5, 5, 4.6, 6.2, 5.8, 7.4, 8.1, 9.6];
  const W = 560;
  const H = 120;
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const path = pts.map((y, i) => `${i ? "L" : "M"}${((i / (pts.length - 1)) * W).toFixed(1)},${(H - ((y - lo) / (hi - lo || 1)) * H).toFixed(1)}`).join(" ");
  return (
    <Card {...base} maxW={680}>
      {label ? <div style={{ fontFamily: fonts.sans, fontSize: Math.max(MIN_TEXT, 34), fontWeight: 600, color: c.muted, marginBottom: 6 }}>{label}</div> : null}
      <div style={{ fontFamily: fonts.sans, fontWeight: 800, fontSize: big, lineHeight: 1.05, letterSpacing: "-0.03em", fontVariantNumeric: "tabular-nums" }}>
        {prefix}
        {fmt(shown, decimals, locale)}
        <span style={{ color: c.accent }}>{suffix}</span>
      </div>
      {spark ? (
        <svg width="100%" viewBox={`-8 -8 ${W + 16} ${H + 16}`} style={{ marginTop: 18, display: "block" }}>
          <path d={path} fill="none" stroke={c.track} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" />
          <path d={path} fill="none" stroke={c.accent} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
        </svg>
      ) : null}
    </Card>
  );
};

/** A half-ring gauge that sweeps to `value` (0–100) from `at` over 0.8 s, with the number in the middle. */
export const Gauge: React.FC<WidgetBase & { value: number; label?: string; suffix?: string; fillAt?: number }> = ({ value, label, suffix = "%", fillAt, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const s0 = fillAt ?? (base.at ?? 0) + 0.2;
  const p = useRun(frame, fps, s0, s0 + 0.8);
  const v = value * p;
  const R = 200;
  const arc = Math.PI * R;
  const w = Math.min(560, base.box.w - 80, (base.box.h - (label ? 150 : 90)) * 1.9);
  return (
    <Card {...base} maxW={640}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <svg width={w} viewBox="-230 -230 460 250" style={{ display: "block" }}>
          <path d={`M ${-R} 0 A ${R} ${R} 0 0 1 ${R} 0`} fill="none" stroke={c.track} strokeWidth={36} strokeLinecap="round" />
          <path d={`M ${-R} 0 A ${R} ${R} 0 0 1 ${R} 0`} fill="none" stroke={c.accent} strokeWidth={36} strokeLinecap="round" strokeDasharray={arc} strokeDashoffset={arc * (1 - Math.min(100, v) / 100)} />
          <text x={0} y={-24} textAnchor="middle" fontFamily={fonts.sans} fontWeight={800} fontSize={104} fill={c.fg} style={{ fontVariantNumeric: "tabular-nums" }}>
            {Math.round(v)}
            {suffix}
          </text>
        </svg>
        {label ? <div style={{ fontFamily: fonts.sans, fontSize: 34, fontWeight: 600, color: c.muted, marginTop: 14 }}>{label}</div> : null}
      </div>
    </Card>
  );
};

/** A stopwatch whose hand sweeps and readout counts 0 → `seconds` between `start` and `end`
 *  (so 3 hours can pass in 2 seconds). */
export const Stopwatch: React.FC<WidgetBase & { seconds: number; start?: number; end?: number; label?: string }> = ({ seconds, start, end, label, ...base }) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const s0 = start ?? (base.at ?? 0) + 0.2;
  const p = useRun(frame, fps, s0, end ?? s0 + 1.5, easeInOut);
  const t = seconds * p;
  const hh = Math.floor(t / 3600);
  const mm = Math.floor((t % 3600) / 60);
  const ss = Math.floor(t % 60);
  const read = (hh ? `${hh}:${String(mm).padStart(2, "0")}` : String(mm).padStart(2, "0")) + `:${String(ss).padStart(2, "0")}`;
  // one turn per hour (or minute), but never more than 3 over the run: a week mustn't strobe
  const turns = p * Math.min(3, Math.max(1, seconds / (seconds >= 3600 ? 3600 : 60)));
  const d = Math.min(230, base.box.h - (label ? 190 : 120), base.box.w * 0.34);
  return (
    <Card {...base} maxW={680}>
      <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
        <svg width={d} height={d} viewBox="-110 -125 220 235" style={{ flex: "none" }}>
          <rect x={-14} y={-124} width={28} height={16} rx={5} fill={c.fg} />
          <circle r={96} fill="none" stroke={c.fg} strokeWidth={10} />
          {Array.from({ length: 12 }, (_, i) => (
            <line key={i} x1={0} y1={-80} x2={0} y2={i % 3 ? -72 : -64} stroke={c.muted} strokeWidth={5} strokeLinecap="round" transform={`rotate(${i * 30})`} />
          ))}
          <line x1={0} y1={8} x2={0} y2={-70} stroke={c.accent} strokeWidth={8} strokeLinecap="round" transform={`rotate(${turns * 360})`} />
          <circle r={9} fill={c.accent} />
        </svg>
        <div>
          <div style={{ fontFamily: fonts.mono, fontWeight: 700, fontSize: Math.max(MIN_TEXT, Math.min(64, base.box.w * 0.08)), fontVariantNumeric: "tabular-nums" }}>{read}</div>
          {label ? <div style={{ fontFamily: fonts.sans, fontSize: 34, fontWeight: 600, color: c.muted, marginTop: 8 }}>{label}</div> : null}
        </div>
      </div>
    </Card>
  );
};

/** Horizontal bars that grow in one after another from `at` (a funnel, a ranking). `drop: true`
 *  marks the % lost between consecutive rows in the accent colour. */
export const FunnelBars: React.FC<WidgetBase & { title?: string; rows: { label: string; value: number }[]; drop?: boolean; locale?: string }> = ({
  title,
  rows,
  drop,
  locale = "en-US",
  ...base
}) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const max = Math.max(...rows.map((r) => r.value));
  const a0 = f(base.at, fps) + 5;
  const n = rows.length + (title ? 0.8 : 0);
  // a row = label/value line + bar under it
  const fs = Math.max(MIN_TEXT, Math.min(40, (base.box.h - 100) / (n * 2.35)));
  const bar = fs * 0.78;
  return (
    <Card {...base} maxW={780}>
      {title ? <div style={{ fontFamily: fonts.sans, fontWeight: 700, fontSize: fs * 1.05, marginBottom: fs * 0.5 }}>{title}</div> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: fs * 0.5 }}>
        {rows.map((r, i) => {
          const p = interpolate(frame, [a0 + i * 5, a0 + i * 5 + 16], [0, 1], { ...clamp, easing: easeOut });
          const lost = i && drop ? Math.round((1 - r.value / rows[i - 1].value) * 100) : 0;
          return (
            <div key={i}>
              <div style={{ display: "flex", alignItems: "baseline", gap: fs * 0.5, fontFamily: fonts.sans, fontSize: fs, fontWeight: 600, marginBottom: fs * 0.22 }}>
                <span>{r.label}</span>
                {lost > 0 ? <span style={{ fontSize: MIN_TEXT, fontWeight: 700, color: c.accent, opacity: p }}>−{lost}%</span> : null}
                <span style={{ marginLeft: "auto", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{Math.round(r.value * p).toLocaleString(locale)}</span>
              </div>
              <div style={{ height: bar, borderRadius: bar / 2, background: c.track, overflow: "hidden" }}>
                <div style={{ width: `${Math.max(r.value / max, 0.02) * 100 * p}%`, height: "100%", borderRadius: bar / 2, background: i === 0 ? c.fg : c.accent }} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

/** A grid of `count` tiles popping in `stagger` s apart from `at`; the first `highlight` tiles take
 *  the accent (12 of 100 people…). `colors` overrides the tile colours (cycled). */
export const TileGrid: React.FC<WidgetBase & { count: number; cols?: number; highlight?: number; colors?: string[]; stagger?: number; label?: string }> = ({
  count,
  cols,
  highlight = 0,
  colors,
  stagger,
  label,
  ...base
}) => {
  const { frame, fps } = useEntrance(base.at, base.out);
  const { fonts } = useBrand();
  const c = useCardColors(base.bg);
  const k = cols ?? Math.ceil(Math.sqrt(count * (base.box.w / Math.max(1, base.box.h))));
  const rows = Math.ceil(count / k);
  const inner = Math.min(base.box.w, 780) - 80;
  const availH = base.box.h - 80 - (label ? 34 * 1.2 + 18 + 4 : 0); // card padding, label line + margin
  const cell = Math.min(inner / k, availH / rows, 90);
  const a0 = f(base.at, fps) + 4;
  const gap = stagger ?? Math.min(0.03, 0.8 / count); // the whole grid lands within ~0.8 s
  return (
    <Card {...base} maxW={Math.min(780, cell * k + 80)}>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${k}, ${cell}px)`, gap: 0, justifyContent: "center" }}>
        {Array.from({ length: count }, (_, i) => {
          const pop = spring({ frame: frame - a0 - Math.round(i * gap * fps), fps, config: { damping: 12, stiffness: 200, mass: 0.6 } });
          const col = colors?.length ? colors[i % colors.length] : i < highlight ? c.accent : c.track;
          return (
            <div key={i} style={{ width: cell, height: cell, padding: cell * 0.09, boxSizing: "border-box" }}>
              <div style={{ width: "100%", height: "100%", borderRadius: cell * 0.18, background: col, scale: String(pop) }} />
            </div>
          );
        })}
      </div>
      {label ? <div style={{ fontFamily: fonts.sans, fontSize: 34, fontWeight: 600, color: c.muted, marginTop: 18, textAlign: "center" }}>{label}</div> : null}
    </Card>
  );
};
