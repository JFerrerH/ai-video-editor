import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, easeOut, enter } from "../anim";
import { IconKind, LineIcon } from "../components/icons";
import { useFrameLayout } from "../layout";
import { textOn, useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";
import { SceneHeader, useHeaderSize } from "./header";

export type NetNode = { id: string; label: string; color?: string; icon?: IconKind };
export type NetHub = { label?: string; icon?: IconKind; color?: string };
export type NetChip = { node: string; text: string; at?: number };
export type NetMessage = { from: string; to: string; at: number; lock?: boolean };
export type NetLog = { text: string; at: number };

/** Node colours when a node gives none: muted, distinct, readable under a white icon. */
export const NODE_COLORS = ["#4F6BED", "#E07A3F", "#2F9E77", "#B65CC9", "#C99A1E", "#3B9FC9", "#D2557A", "#6B7A8F"];

const LABEL_FS = 32; // node labels and log lines: never under 28 px at 1080 short side
const LOG_FS = 30;
const LOG_LINE = 46;
const CONNECT_S = 0.8; // a node's travel from chaos to its ring slot
const STAGGER_F = 3; // frames between nodes
const MESSAGE_S = 0.9; // a packet's trip (half per leg through the hub)

const fract = (x: number) => x - Math.floor(x);
const rand = (i: number, k: number) => fract(Math.sin(i * 12.9898 + k * 78.233) * 43758.5453);
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
type Pt = [number, number];
const mix = (a: Pt, b: Pt, p: number): Pt => [lerp(a[0], b[0], p), lerp(a[1], b[1], p)];
const ramp = (t: number, a: number, len: number, ease = easeInOut) => interpolate(t, [a, a + len], [0, 1], { ...clamp, easing: ease });

/** Solid page colour of a tone (label pills sit on it so spokes pass behind the text). */
const baseOf = (bg: BgKind | undefined, c: { bg: string; ink: string; accent: string }) =>
  bg === "dark" ? c.ink : bg === "accent" ? c.accent : bg === "none" ? "transparent" : c.bg;

const Lock: React.FC<{ x: number; y: number; s: number; color: string }> = ({ x, y, s, color }) => (
  <g transform={`translate(${x - s / 2} ${y - s / 2}) scale(${s / 24})`} fill="none" stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
    <rect x="5" y="10.5" width="14" height="10" rx="2" fill={color} />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
  </g>
);

const Envelope: React.FC<{ x: number; y: number; s: number; color: string }> = ({ x, y, s, color }) => (
  <g transform={`translate(${x - s / 2} ${y - s / 2}) scale(${s / 24})`} fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="6" width="18" height="13" rx="2" />
    <path d="M3.5 7.5 12 13.5l8.5-6" />
  </g>
);

/**
 * Things connecting through a hub. Labelled `nodes` (colour, optional line icon) drift in `chaos`
 * (tangled dashed lines, error marks) until that time, then ease into a ring around the `hub` at
 * `connect` and spokes draw in. `chips` pin a small pill to a node, `messages` send a packet
 * (optionally locked) from one node through the hub to another, and `log` lines print in a ticker
 * under the ring (to its right in 16:9). Every time is seconds from the scene start or an `@word` cue.
 */
export const NetworkScene: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  kicker?: string;
  title?: string;
  emphasis?: string;
  nodes: NetNode[];
  hub?: NetHub | null;
  chaos?: number;
  connect?: number;
  chips?: NetChip[];
  messages?: NetMessage[];
  log?: NetLog[];
}> = ({ bg, kicker, title, emphasis, nodes, hub, chaos, connect, chips = [], messages = [], log = [] }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { colors, fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, innerW, innerH, aspect, width, height } = useFrameLayout();
  const head = useHeaderSize(kicker, title);
  const base = baseOf(bg, colors);

  // ── layout: diagram box, log box ──
  const wide = aspect === "16:9";
  const box = { x: safe.left, y: safe.top + head.height, w: innerW, h: innerH - head.height };
  const logLines = wide ? 7 : aspect === "9:16" ? 5 : 3;
  let logBox: { x: number; y: number; w: number; h: number } | null = null;
  if (log.length) {
    const lh = logLines * LOG_LINE + 40;
    if (wide) {
      const lw = Math.min(600, innerW * 0.36);
      logBox = { x: box.x + box.w - lw, y: box.y + Math.max(0, (box.h - lh) / 2), w: lw, h: Math.min(lh, box.h) };
      box.w -= lw + 40;
    } else {
      logBox = { x: box.x, y: box.y + box.h - lh, w: box.w, h: lh };
      box.h -= lh + 28;
    }
  }
  const D = Math.min(box.w, box.h);
  const nodeR = Math.max(36, Math.min(72, D * 0.09));
  const hubR = nodeR * 1.5;
  const labelH = LABEL_FS * 1.25 + 14;
  const labelHalf = Math.max(nodeR, ...nodes.map((n) => (n.label.length * LABEL_FS * 0.56) / 2 + 14));
  const ry = Math.max(nodeR * 2, Math.min(0.36 * D, box.h / 2 - nodeR - labelH / 2 - 4));
  const rx = Math.max(nodeR * 2, Math.min(box.w / 2 - labelHalf - 4, ry * Math.min(1.4, Math.max(1, box.w / box.h))));
  // tall frames: the ring needs less height than it gets, so close the gap and centre ring + log as one group
  const slack = box.h - (2 * ry + 2 * nodeR + labelH + 24);
  if (!wide && slack > 0) {
    box.y += slack / 2;
    box.h -= slack;
    if (logBox) logBox.y -= slack / 2;
  }
  const cx = box.x + box.w / 2;
  const cy = box.y + (box.h - labelH) / 2 + nodeR * 0.15;

  const n = nodes.length;
  const tc = connect ?? chaos ?? 0;
  const ringAt = (i: number): Pt => {
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
    return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)];
  };
  // chaos: each node gets its own cell of a grid over the diagram box (shuffled, jittered), so the
  // tangle spreads out instead of piling up; neighbours in the list end up far apart and lines cross
  const gc = Math.max(2, Math.ceil(Math.sqrt((n * box.w) / box.h)));
  const gr = Math.max(2, Math.ceil(n / gc));
  const cells = Array.from({ length: gc * gr }, (_, k) => k).sort((a, b) => rand(a, 9) - rand(b, 9));
  const chaosAt = (i: number): Pt => {
    const cell = cells[i % cells.length];
    const [gx, gy] = [cell % gc, Math.floor(cell / gc)];
    const cw = (box.w - 2 * labelHalf) / gc;
    const ch = (box.h - 2 * nodeR - labelH) / gr;
    const x = box.x + labelHalf + (gx + 0.5 + (rand(i, 1) - 0.5) * 0.5) * cw + Math.sin(t * 0.9 + i * 1.7) * nodeR * 0.4;
    const y = box.y + nodeR + (gy + 0.5 + (rand(i, 2) - 0.5) * 0.5) * ch + Math.cos(t * 0.7 + i * 2.3) * nodeR * 0.3;
    return [x, y];
  };
  const settle = (i: number) => (chaos === undefined ? 1 : ramp(t, tc + (i * STAGGER_F) / fps, CONNECT_S));
  const pos = nodes.map((_, i) => mix(chaosAt(i), ringAt(i), settle(i)));
  const idx = new Map(nodes.map((nd, i) => [nd.id, i]));
  const center: Pt = [cx, cy];
  const pop = nodes.map((_, i) => enter(frame, fps, 2 + i * STAGGER_F));
  const hubPop = hub ? enter(frame, fps, Math.round(tc * fps)) : 0;
  const spoke = nodes.map((_, i) => ramp(t, tc + (i * STAGGER_F) / fps + (chaos === undefined ? 0.3 : CONNECT_S * 0.55), 0.45, easeOut));
  const chaosA = chaos === undefined ? 0 : 1 - ramp(t, chaos, 0.35, easeOut);
  const color = (i: number) => nodes[i].color ?? NODE_COLORS[i % NODE_COLORS.length];

  // ── messages: packet position, which spoke is lit, arrival pulses ──
  const lit = new Map<number, number>(); // node index → spoke highlight 0–1
  const pulses: { at: Pt; r: number; p: number; c: string }[] = [];
  const packets = messages.flatMap((m) => {
    const a = idx.get(m.from);
    const b = idx.get(m.to);
    if (a === undefined || b === undefined) return [];
    const u = (t - m.at) / MESSAGE_S;
    if (u > 0 && u < 1.5) {
      if (u >= 1) pulses.push({ at: pos[b], r: nodeR, p: (u - 1) / 0.5, c: color(b) });
      if (hub && u >= 0.5 && u < 1) pulses.push({ at: center, r: hubR, p: (u - 0.5) / 0.5, c: pal.accent });
    }
    if (u <= 0 || u >= 1) return [];
    let p: Pt;
    if (hub) {
      if (u < 0.5) {
        lit.set(a, Math.max(lit.get(a) ?? 0, 1));
        p = mix(pos[a], center, easeInOut(u * 2));
      } else {
        lit.set(b, Math.max(lit.get(b) ?? 0, 1));
        p = mix(center, pos[b], easeInOut(u * 2 - 1));
      }
    } else {
      p = mix(pos[a], pos[b], easeInOut(u));
    }
    const s = interpolate(u, [0, 0.08, 0.92, 1], [0.4, 1, 1, 0.4], clamp);
    return [{ p, s, lock: !!m.lock }];
  });

  // ── log ticker ──
  const shown = [...log].sort((x, y) => x.at - y.at).filter((l) => l.at <= t);
  const tail = shown.slice(-logLines);
  const newest = shown.length ? shown[shown.length - 1].at : 0;
  const scroll = ramp(t, newest, 8 / fps, easeOut);
  const logIn = log.length ? ramp(t, Math.min(...log.map((l) => l.at)) - 0.25, 0.3, easeOut) : 0;

  const pkt = nodeR * 0.82;
  return (
    <AbsoluteFill>
      <SceneHeader bg={bg} kicker={kicker} title={title} emphasis={emphasis} />
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0 }}>
        {/* chaos: tangled dashed lines with packets that never arrive, and blinking error marks */}
        {chaosA > 0
          ? nodes.flatMap((_, i) =>
              [2, 3].map((step) => {
                const j = (i + step) % n;
                if (j === i || (step === 3 && n < 5)) return null;
                const [p, q] = [pos[i], pos[j]];
                const ctrl: Pt = [(p[0] + q[0]) / 2 + (rand(i, step) - 0.5) * D * 0.5, (p[1] + q[1]) / 2 + (rand(j, step) - 0.5) * D * 0.5];
                const d = `M${p[0]},${p[1]} Q${ctrl[0]},${ctrl[1]} ${q[0]},${q[1]}`;
                const k = fract(t * 0.55 + rand(i, step + 4));
                const dot = mix(mix(p, ctrl, k), mix(ctrl, q, k), k);
                const mid = mix(mix(p, ctrl, 0.5), mix(ctrl, q, 0.5), 0.5);
                const blink = Math.sin(t * 7 + i * 2.1 + step) > 0.2 && (i + step) % 3 === 0;
                return (
                  <g key={`c${i}-${step}`} opacity={chaosA}>
                    <path d={d} fill="none" stroke={pal.muted} strokeOpacity={0.55} strokeWidth={3} strokeDasharray="10 12" />
                    <circle cx={dot[0]} cy={dot[1]} r={7} fill={pal.muted} opacity={0.8} />
                    {blink ? (
                      <g transform={`translate(${mid[0]} ${mid[1]})`} stroke={colors.accent} strokeWidth={6} strokeLinecap="round">
                        <circle r={20} fill={base === "transparent" ? "#000" : base} stroke={colors.accent} strokeWidth={4} />
                        <path d="M-8,-8 L8,8 M8,-8 L-8,8" />
                      </g>
                    ) : null}
                  </g>
                );
              }),
            )
          : null}
        {/* spokes (or a ring of links when there is no hub) */}
        {nodes.map((_, i) => {
          const s = spoke[i];
          if (s <= 0) return null;
          const from = hub ? center : pos[i];
          const to = hub ? pos[i] : pos[(i + 1) % n];
          if (!hub && n < 3 && i === n - 1) return null;
          const end = mix(from, to, s);
          const hi = lit.get(i) ?? 0;
          return (
            <g key={`s${i}`}>
              <line x1={from[0]} y1={from[1]} x2={end[0]} y2={end[1]} stroke={pal.track} strokeWidth={10} strokeLinecap="round" />
              <line x1={from[0]} y1={from[1]} x2={end[0]} y2={end[1]} stroke={hi ? pal.accent : pal.muted} strokeOpacity={hi ? 0.9 : 0.45} strokeWidth={hi ? 5 : 3} strokeLinecap="round" />
            </g>
          );
        })}
        {/* hub */}
        {hub && hubPop > 0.01 ? (
          <g transform={`translate(${cx} ${cy}) scale(${hubPop})`}>
            <circle r={hubR * 1.28} fill={hub.color ?? pal.fg} opacity={0.1} />
            <circle r={hubR} fill={hub.color ?? pal.fg} />
            {hub.icon ? (
              <g transform={`translate(${-hubR * 0.5} ${-hubR * 0.5})`}>
                <LineIcon kind={hub.icon} size={hubR} color={textOn(hub.color ?? pal.fg, colors.ink)} stroke={1.9} />
              </g>
            ) : null}
          </g>
        ) : null}
        {/* nodes */}
        {nodes.map((nd, i) => {
          const [x, y] = pos[i];
          const c = color(i);
          return (
            <g key={nd.id} transform={`translate(${x} ${y}) scale(${pop[i]})`}>
              <circle r={nodeR} fill={c} />
              <circle r={nodeR} fill="none" stroke="#000" strokeOpacity={0.08} strokeWidth={3} />
              {nd.icon ? (
                <g transform={`translate(${-nodeR * 0.55} ${-nodeR * 0.55})`}>
                  <LineIcon kind={nd.icon} size={nodeR * 1.1} color={textOn(c, colors.ink)} stroke={2} />
                </g>
              ) : (
                <text textAnchor="middle" dominantBaseline="central" fontFamily={fonts.sans} fontWeight={700} fontSize={nodeR * 0.9} fill={textOn(c, colors.ink)}>
                  {nd.label.slice(0, 1).toUpperCase()}
                </text>
              )}
            </g>
          );
        })}
        {/* arrival pulses */}
        {pulses.map((q, k) => (
          <circle key={`p${k}`} cx={q.at[0]} cy={q.at[1]} r={q.r * (1 + q.p * 0.7)} fill="none" stroke={q.c} strokeWidth={6 * (1 - q.p)} opacity={1 - q.p} />
        ))}
      </svg>
      {/* hub label, node labels and chips: HTML for brand fonts */}
      {hub?.label && hubPop > 0.01 ? (
        <div
          style={{
            position: "absolute",
            left: cx - hubR,
            top: cy - (hub.icon ? -hubR - 10 : LABEL_FS * 0.62),
            width: hubR * 2,
            textAlign: "center",
            fontFamily: fonts.sans,
            fontWeight: 700,
            fontSize: LABEL_FS,
            lineHeight: 1.2,
            color: hub.icon ? pal.fg : textOn(hub.color ?? pal.fg, colors.ink),
            opacity: hubPop,
            whiteSpace: "nowrap",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <span style={{ background: hub.icon ? base : undefined, padding: "0 10px", borderRadius: 8 }}>{hub.label}</span>
        </div>
      ) : null}
      {nodes.map((nd, i) => {
        const [x, y] = pos[i];
        return (
          <div
            key={`l${nd.id}`}
            style={{
              position: "absolute",
              left: x - 300,
              top: y + nodeR + 8,
              width: 600,
              display: "flex",
              justifyContent: "center",
              opacity: interpolate(pop[i], [0.3, 1], [0, 1], clamp),
            }}
          >
            <span style={{ fontFamily: fonts.sans, fontSize: LABEL_FS, fontWeight: 600, lineHeight: 1.25, color: pal.fg, background: base, padding: "0 12px", borderRadius: 10, whiteSpace: "nowrap" }}>
              {nd.label}
            </span>
          </div>
        );
      })}
      {chips.map((c, k) => {
        const i = idx.get(c.node);
        if (i === undefined) return null;
        const s = enter(frame, fps, Math.round((c.at ?? tc + 1) * fps), 12);
        if (frame < Math.round((c.at ?? tc + 1) * fps)) return null;
        const [x, y] = pos[i];
        return (
          <div
            key={`chip${k}`}
            style={{
              position: "absolute",
              left: x + nodeR * 0.55,
              top: y - nodeR * 1.15,
              scale: String(s),
              transformOrigin: "0% 100%",
              fontFamily: fonts.mono,
              fontSize: 28,
              fontWeight: 700,
              lineHeight: 1.2,
              padding: "4px 14px",
              borderRadius: 999,
              background: pal.fg,
              color: textOn(pal.fg, colors.ink),
              whiteSpace: "nowrap",
              boxShadow: "0 6px 16px rgba(0,0,0,0.18)",
            }}
          >
            {c.text}
          </div>
        );
      })}
      {/* packets ride above the labels, so a packet leaving a node is never hidden by its name */}
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0 }}>
          {/* packets */}
          {packets.map(({ p, s, lock }, k) => (
            <g key={`k${k}`} transform={`translate(${p[0]} ${p[1]}) scale(${s})`}>
              <rect x={-pkt / 2} y={-pkt / 2} width={pkt} height={pkt} rx={pkt * 0.28} fill={pal.accent} />
              <rect x={-pkt / 2} y={-pkt / 2} width={pkt} height={pkt} rx={pkt * 0.28} fill="none" stroke={base === "transparent" ? "#fff" : base} strokeWidth={4} />
              {lock ? <Lock x={0} y={0} s={pkt * 0.62} color={textOn(pal.accent, colors.ink)} /> : <Envelope x={0} y={0} s={pkt * 0.66} color={textOn(pal.accent, colors.ink)} />}
            </g>
          ))}
      </svg>
      {logBox && logIn > 0 ? (
        <div
          style={{
            position: "absolute",
            left: logBox.x,
            top: logBox.y,
            width: logBox.w,
            height: logBox.h,
            borderRadius: 22,
            border: `2px solid ${pal.track}`,
            background: bg === "dark" ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.03)",
            overflow: "hidden",
            opacity: logIn,
            fontFamily: fonts.mono,
            fontSize: LOG_FS,
          }}
        >
          {tail.map((l, k) => {
            const fromEnd = tail.length - 1 - k; // 0 = newest
            const isNew = fromEnd === 0;
            return (
              <div
                key={`${l.at}-${k}`}
                style={{
                  position: "absolute",
                  left: 26,
                  right: 26,
                  bottom: 20 + fromEnd * LOG_LINE - (1 - scroll) * LOG_LINE,
                  height: LOG_LINE,
                  lineHeight: `${LOG_LINE}px`,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  color: pal.fg,
                  opacity: isNew ? scroll : 0.45,
                }}
              >
                <span style={{ color: isNew ? pal.accent : pal.muted }}>{"› "}</span>
                {l.text}
              </div>
            );
          })}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
