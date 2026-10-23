import React, { useMemo } from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut } from "../anim";
import { Figure } from "../explainer/Figure";
import { HeadWord, Headline } from "../explainer/Headline";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { Grain } from "./Bg";
import {
  Action,
  ballAt,
  BallObj,
  blockAt,
  BlockObj,
  buildWorld,
  CalloutObj,
  cameraAt,
  figureAt,
  FigureObj,
  PropObj,
  propAt,
  rnd,
  SignObj,
  shownAt,
  skyAt,
  visibleAt,
  WorldDef,
} from "../world/model";

const FIG_H = 400; // world units from the figure's feet to the top of its box
const ALERT = "#E0512F";
const ICE = "#D7F0F2";
const ALERT_ICE = "#F6D9CF";

/**
 * A continuous world seen through a moving camera (see world/model.ts). tools/storyboard.py merges
 * a run of consecutive `WorldScene` beats that share a `world` into one of these: `world` is then
 * the definition, `actions` and `words` are on the run's clock.
 * Layers: sky + far ridge (parallax) → world (ground, trees, blocks, balls, figures, props, signs;
 * one transform: anchor, zoom, slope, camera) → snowfall → upright pills (values, bursts, chips,
 * callouts, timelapse) → headline → grain.
 */
export const WorldScene: React.FC<{
  durationInFrames: number;
  grain?: number;
  words?: HeadWord[];
  headline?: boolean;
  world: WorldDef;
  actions?: Action[];
  burst?: string;
}> = ({ grain = 0, words = [], headline = true, world, actions = [], burst = "¡Listo!" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { width: W, height: H } = useFrameLayout();
  const { colors, fonts } = useBrand();
  const w = useMemo(() => buildWorld(world, actions, fps), [world, actions, fps]);
  const t = frame / fps;
  const ink = colors.ink;
  const snow = colors.bg;
  const lime = colors.accent;

  const cam = cameraAt(w, t);
  const zoom = (cam.zoom * W) / 1080;
  const anchorX = W * 0.5;
  const anchorY = H * 0.7;
  const a = (w.slope * Math.PI) / 180;
  const toScreen = (wx: number, wy: number) => {
    const dx = wx - cam.x;
    const dy = wy - cam.y;
    return { x: anchorX + cam.sx + zoom * (dx * Math.cos(a) - dy * Math.sin(a)), y: anchorY + cam.sy + zoom * (dx * Math.sin(a) + dy * Math.cos(a)) };
  };
  const transform = `translate(${anchorX + cam.sx}px, ${anchorY + cam.sy}px) scale(${zoom}) rotate(${w.slope}deg) translate(${-cam.x}px, ${-cam.y}px)`;
  const enter = (at: number, damping = 13) => (t < at ? 0 : spring({ frame: Math.round((t - at) * fps), fps, config: { damping, stiffness: 170, mass: 0.7 } }));

  const objs = world.objects;
  const balls = objs.filter((o): o is BallObj => o.kind === "ball");
  const blocks = objs.filter((o): o is BlockObj => o.kind === "block");
  const figures = objs.filter((o): o is FigureObj => o.kind === "figure");
  const props = objs.filter((o): o is PropObj => o.kind === "prop");
  const signs = objs.filter((o): o is SignObj => o.kind === "sign");
  const callouts = objs.filter((o): o is CalloutObj => o.kind === "callout");
  const sky = skyAt(w, t);

  // ---- terrain (static paths)
  const ground = useMemo(() => {
    const pts: string[] = [];
    for (let x = -3000; x <= 14000; x += 120) pts.push(`${x},${(Math.sin(x * 0.011) * 6 + Math.sin(x * 0.0031) * 10).toFixed(1)}`);
    return `M -3000 3000 L ${pts.join(" L ")} L 14000 3000 Z`;
  }, []);
  const trees = useMemo(
    () => Array.from({ length: 34 }, (_, i) => ({ x: -1400 + i * 460 + rnd(i) * 200, h: 160 + rnd(i + 40) * 170, o: 0.45 + rnd(i + 90) * 0.3 })),
    [],
  );
  const ridgeOff = -((cam.x * zoom * 0.12) % 900);
  let ridge = `M ${ridgeOff - 900} ${H}`;
  for (let x = -900; x <= W + 1800; x += 150) {
    const k = (((Math.round(x / 150) % 6) + 6) % 6) + 1;
    ridge += ` L ${ridgeOff + x} ${H * 0.5 - (rnd(k) * 220 + 60)}`;
  }
  ridge += ` L ${ridgeOff + W + 1800} ${H} Z`;

  // ---- sky timelapse: sun then moon per step
  let skyGlow = 0;
  let orb: React.ReactNode = <circle cx={W * 0.8} cy={H * 0.3} r={70} fill={snow} opacity={0.12} />;
  if (sky && !sky.done) {
    const sun = sky.phase < 0.5;
    const q = sun ? sky.phase * 2 : (sky.phase - 0.5) * 2;
    const cx = W * (0.08 + 0.84 * q);
    const cy = H * 0.52 - Math.sin(q * Math.PI) * H * 0.1; // stays under the step pill
    skyGlow = sun ? Math.sin(q * Math.PI) * 0.35 : 0;
    orb = sun ? (
      <circle cx={cx} cy={cy} r={64} fill="#F8ECC4" />
    ) : (
      <g>
        <circle cx={cx} cy={cy} r={54} fill={snow} opacity={0.9} />
        <circle cx={cx + 22} cy={cy - 10} r={48} fill="#24231B" />
      </g>
    );
  }

  // ---- world layer pieces
  const blockEls = blocks.map((b, i) => {
    if (!visibleAt(w, b.id, t)) return null;
    const s = blockAt(w, b.id, t);
    const fill = b.tone === "alert" ? ALERT_ICE : ICE;
    const inP = enter(shownAt(w, b.id));
    if (!s.broken) {
      return (
        <g key={b.id} transform={`translate(${s.x},0) scale(1,${inP})`}>
          {s.glow > 0 ? <rect x={-14} y={-b.h - 14} width={b.w + 28} height={b.h + 28} rx={30} fill="none" stroke={ALERT} strokeWidth={10} opacity={s.glow} /> : null}
          <rect x={0} y={-b.h} width={b.w} height={b.h + 14} rx={22} fill={fill} />
          <rect x={14} y={-b.h + 14} width={b.w - 28} height={18} rx={9} fill="#FFFFFF" opacity={0.55} />
          <path d={`M ${b.w * 0.18} ${-b.h * 0.6} l ${b.w * 0.12} ${b.h * 0.12} l ${-b.w * 0.05} ${b.h * 0.14}`} stroke="#FFFFFF" strokeWidth={5} fill="none" opacity={0.6} />
          {s.pile > 0 ? <rect x={-10} y={-b.h - s.pile + 6} width={b.w + 20} height={s.pile + 4} rx={Math.min(30, s.pile / 2 + 8)} fill="#FFFFFF" /> : null}
          {b.tag ? (
            <text x={b.w / 2} y={-b.h * 0.66} textAnchor="middle" fontFamily={fonts.mono} fontSize={Math.max(26, b.w * 0.085)} fontWeight={600} letterSpacing="0.1em" fill={ink} opacity={0.6}>
              {b.tag.toUpperCase()}
            </text>
          ) : null}
          <text x={b.w / 2} y={-b.h * 0.34} textAnchor="middle" fontFamily={fonts.sans} fontSize={Math.max(40, Math.min(b.w * 0.17, b.h * 0.3))} fontWeight={700} fill={b.tone === "alert" ? ALERT : ink}>
            {b.label}
          </text>
        </g>
      );
    }
    // shards burst out, then get pulled into the ball; a lime ring + sparks at the contact
    const since = t - s.broken.at;
    const ball = s.broken.into ? ballAt(w, s.broken.into, t) : null;
    const pieces = Array.from({ length: 16 }, (_, k) => {
      const seed = i * 100 + k;
      const px = b.x + rnd(seed) * b.w;
      const py = -rnd(seed + 7) * b.h;
      const fly = Math.min(since, 0.3);
      let x = px + (200 + rnd(seed + 3) * 900) * fly;
      let y = py + (-500 - rnd(seed + 5) * 900) * fly + 1800 * fly * fly;
      const pull = ball ? interpolate(since, [0.22, 0.55], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) }) : interpolate(since, [0.3, 0.9], [0, 1], clamp);
      if (ball) {
        x += (ball.x - x) * pull;
        y += (-ball.r - y) * pull;
      } else y += 600 * pull * pull;
      const size = (0.15 + rnd(seed + 9) * 0.14) * Math.min(b.w, b.h) * (1 - pull * 0.8);
      const rot = rnd(seed + 11) * 360 + since * 500 * (rnd(seed + 13) - 0.5);
      if (pull >= 1) return null;
      const r1 = 0.6 + rnd(seed + 17) * 0.5;
      return (
        <polygon
          key={k}
          points={`0,${-size} ${size * 0.9 * r1},${-size * 0.1} ${size * 0.55},${size * 0.75} ${-size * 0.6},${size * 0.6} ${-size * 0.85 * r1},${-size * 0.2}`}
          fill={k % 4 === 0 ? "#FFFFFF" : fill}
          transform={`translate(${x},${y}) rotate(${rot})`}
        />
      );
    });
    const ring = interpolate(since, [0, 0.45], [0, 1], { ...clamp, easing: easeOut });
    const cx = b.x;
    const cy = -b.h * 0.5;
    return (
      <g key={b.id}>
        {since < 0.6 ? (
          <g opacity={1 - ring}>
            <circle cx={cx} cy={cy} r={40 + ring * 380} fill="none" stroke={lime} strokeWidth={14 * (1 - ring) + 2} />
            {Array.from({ length: 14 }, (_, k) => {
              const an = (k / 14) * Math.PI * 2 + rnd(i * 50 + k) * 0.4;
              const d = 60 + ring * (200 + rnd(k + 3) * 160);
              return <circle key={k} cx={cx + Math.cos(an) * d} cy={cy + Math.sin(an) * d} r={10 * (1 - ring) + 2} fill={lime} />;
            })}
          </g>
        ) : null}
        {pieces}
      </g>
    );
  });

  const ballEls = balls.map((o) => {
    if (!visibleAt(w, o.id, t)) return null;
    const b = ballAt(w, o.id, t);
    const inP = enter(shownAt(w, o.id), 12);
    const r = b.r * inP;
    const sq = b.squash;
    const mark = "#C9C5B6";
    return (
      <g key={o.id}>
        {b.x - o.x > 10 ? <line x1={o.x} y1={4} x2={b.x} y2={4} stroke={mark} strokeWidth={Math.min(b.r * 0.5, 70)} strokeLinecap="round" opacity={0.55} /> : null}
        <ellipse cx={b.x + 10} cy={8} rx={r * 0.95} ry={r * 0.16} fill="#000" opacity={0.18} />
        <g transform={`translate(${b.x},${-r * sq}) scale(${2 - sq},${sq})`}>
          <circle r={r} fill="#FFFFFF" />
          <circle r={r} fill={`url(#shade-${o.id})`} />
          {/* packed-snow texture: many small scattered dents (a few big marks read as a face) */}
          <g transform={`rotate(${b.rot})`}>
            {Array.from({ length: 16 }, (_, k) => {
              const an = rnd(k + 300) * Math.PI * 2;
              const d = (0.2 + rnd(k + 310) * 0.65) * r;
              return <ellipse key={k} cx={Math.cos(an) * d} cy={Math.sin(an) * d} rx={r * (0.03 + rnd(k + 320) * 0.04)} ry={r * (0.02 + rnd(k + 330) * 0.02)} fill={mark} opacity={0.75} transform={`rotate(${rnd(k + 340) * 180} ${Math.cos(an) * d} ${Math.sin(an) * d})`} />;
            })}
          </g>
        </g>
        <defs>
          <radialGradient id={`shade-${o.id}`} cx="35%" cy="30%" r="75%">
            <stop offset="55%" stopColor="#FFFFFF" stopOpacity={0} />
            <stop offset="100%" stopColor="#B9B5A6" stopOpacity={0.9} />
          </radialGradient>
        </defs>
      </g>
    );
  });

  const propEl = (p: PropObj) => {
    if (!visibleAt(w, p.id, t)) return null;
    const s = propAt(w, p.id, t, FIG_H);
    const k = p.size ?? 1;
    let body: React.ReactNode = null;
    if (p.item === "paper")
      body = (
        <g>
          <rect x={-60} y={-150} width={120} height={150} rx={8} fill="#FFFFFF" />
          {[0, 1, 2, 3, 4].map((i) => (
            <rect key={i} x={-42} y={-128 + i * 24} width={i === 4 ? 50 : 84} height={8} rx={4} fill="#C9C5B6" />
          ))}
        </g>
      );
    if (p.item === "towel")
      body = (
        <g>
          <rect x={-80} y={-60} width={160} height={60} rx={10} fill={snow} />
          <rect x={-80} y={-48} width={160} height={10} fill={lime} />
          <rect x={-80} y={-22} width={160} height={10} fill={lime} />
        </g>
      );
    if (p.item === "dumbbell")
      body = (
        <g>
          <rect x={-90} y={-40} width={180} height={14} rx={7} fill="#8E8A7C" />
          <rect x={-120} y={-70} width={36} height={74} rx={8} fill={ink} stroke={snow} strokeWidth={4} />
          <rect x={84} y={-70} width={36} height={74} rx={8} fill={ink} stroke={snow} strokeWidth={4} />
        </g>
      );
    if (p.item === "calculator")
      body = (
        <g>
          <rect x={-55} y={-150} width={110} height={150} rx={14} fill={ink} stroke={snow} strokeWidth={5} />
          <rect x={-40} y={-135} width={80} height={34} rx={6} fill={lime} />
          {[0, 1, 2].map((r) => [0, 1, 2].map((c) => <rect key={`${r}${c}`} x={-40 + c * 28} y={-88 + r * 28} width={22} height={20} rx={4} fill={snow} opacity={0.8} />))}
        </g>
      );
    return (
      <g key={p.id} transform={`translate(${s.x},${s.y}) rotate(${s.rot}) scale(${k})`}>
        {body}
      </g>
    );
  };

  // figures and signs stand upright: counter-rotate around their foot point
  const upright = (x: number, key: string, child: React.ReactNode) => (
    <div key={key} style={{ position: "absolute", left: x, top: 0, transform: `rotate(${-w.slope}deg)`, transformOrigin: "0 0" }}>
      {child}
    </div>
  );

  const figureEls = figures.map((o, i) => {
    if (!visibleAt(w, o.id, t)) return null;
    const f = figureAt(w, o.id, t);
    const bw = 560;
    return upright(
      f.x,
      o.id,
      <Figure poses={f.poses} facing={o.facing ?? "right"} scale={f.scale} phase={i * 0.9} walk={f.walking} box={{ x: -bw / 2, y: -FIG_H, w: bw, h: FIG_H }} bg="dark" />,
    );
  });

  const signEls = signs.map((o) => {
    if (!visibleAt(w, o.id, t)) return null;
    const p = enter(shownAt(w, o.id), 12);
    return upright(
      o.x,
      o.id,
      <div style={{ position: "absolute", left: 0, top: 0, transform: `translate(-50%,-100%) scaleY(${p})`, transformOrigin: "50% 100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ background: ink, border: `6px solid ${lime}`, borderRadius: 28, padding: "26px 40px", textAlign: "center", boxShadow: "0 18px 40px rgba(0,0,0,0.35)" }}>
          <div style={{ fontFamily: fonts.sans, fontWeight: 700, fontSize: 64, color: lime, whiteSpace: "nowrap", letterSpacing: "-0.01em" }}>{o.text}</div>
          {o.sub ? <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 34, color: snow, marginTop: 8, whiteSpace: "nowrap" }}>{o.sub}</div> : null}
        </div>
        <div style={{ width: 22, height: 170, background: "#8E8A7C", borderRadius: 6 }} />
      </div>,
    );
  });

  // ---- screen-space pills
  const pill = (key: string, x: number, y: number, scale: number, text: string, style: React.CSSProperties = {}, opacity = 1) => (
    <div
      key={key}
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%,-100%) scale(${scale})`,
        opacity,
        background: lime,
        color: ink,
        fontFamily: fonts.sans,
        fontWeight: 700,
        fontSize: 52,
        padding: "12px 32px",
        borderRadius: 999,
        whiteSpace: "nowrap",
        fontVariantNumeric: "tabular-nums",
        ...style,
      }}
    >
      {text}
    </div>
  );

  const burstPills = blocks.map((b) => {
    const brk = w.breaks.get(b.id);
    if (!brk) return null;
    const s = t - brk.at;
    if (s < 0.05 || s > 1.6) return null;
    const p = spring({ frame: Math.round(s * fps), fps, config: { damping: 12, stiffness: 180 } });
    const q = toScreen(b.x + b.w / 2, -b.h - 60);
    return pill(`burst-${b.id}`, q.x, q.y - s * 120, p, b.burst ?? burst, {}, interpolate(s, [1.25, 1.6], [1, 0], clamp));
  });

  const valuePills = balls.map((o) => {
    if (o.value === undefined || !visibleAt(w, o.id, t)) return null;
    const b = ballAt(w, o.id, t);
    const q = toScreen(b.x, -b.r * 2 - 40);
    const fmt = (n: number) => (o.prefix ?? "") + n.toLocaleString(o.locale ?? "es-CO") + (o.suffix ?? "");
    const chips = w
      .of(o.id)
      .filter((a) => a.do === "value" && a.chip)
      .map((a, i) => {
        const s = t - a.at + 0.5;
        if (s < 0 || s > 0.75) return null;
        const p = spring({ frame: Math.round(s * fps), fps, config: { damping: 12, stiffness: 200 } });
        const fly = interpolate(s, [0.3, 0.6], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
        const x0 = q.x + 300 * zoom;
        const y0 = q.y + 140 * zoom;
        return pill(`chip-${o.id}-${i}`, x0 + (q.x - x0) * fly, y0 + (q.y - 40 - y0) * fly, p * (1 - fly * 0.6), a.chip!, { fontSize: 46 }, 1 - fly * 0.7);
      });
    return (
      <React.Fragment key={`val-${o.id}`}>
        {pill(`val-${o.id}`, q.x, q.y, enter(shownAt(w, o.id), 14) * b.pop, fmt(b.value), { background: ink, color: lime, border: `4px solid ${lime}`, fontSize: 54 })}
        {chips}
      </React.Fragment>
    );
  });

  const anchorOf = (id: string): { x: number; y: number } | null => {
    const o = w.objs.get(id);
    if (!o) return null;
    if (o.kind === "block") {
      const s = blockAt(w, id, t);
      return { x: s.x + o.w / 2, y: -o.h - s.pile - 30 };
    }
    if (o.kind === "ball") {
      const b = ballAt(w, id, t);
      return { x: b.x, y: -b.r * 2 - 30 };
    }
    if (o.kind === "figure") return { x: figureAt(w, id, t).x, y: -FIG_H * 1.05 };
    if (o.kind === "prop") {
      const p = propAt(w, id, t, FIG_H);
      return { x: p.x, y: p.y - 170 };
    }
    return { x: o.x ?? 0, y: -200 };
  };
  const calloutEls = callouts.map((c) => {
    if (!visibleAt(w, c.id, t)) return null;
    const an = anchorOf(c.target);
    if (!an) return null;
    const q = toScreen(an.x + (c.dx ?? 0), an.y + (c.dy ?? 0));
    const p = enter(shownAt(w, c.id), 12);
    return (
      <div key={c.id} style={{ position: "absolute", left: q.x, top: q.y, transform: `translate(-50%,-100%) scale(${p})`, transformOrigin: "50% 100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ background: snow, color: ink, fontFamily: fonts.sans, fontWeight: 700, fontSize: 46, padding: "16px 30px", borderRadius: 26, whiteSpace: "nowrap" }}>{c.text}</div>
        <div style={{ width: 0, height: 0, borderLeft: "18px solid transparent", borderRight: "18px solid transparent", borderTop: `22px solid ${snow}` }} />
      </div>
    );
  });

  const skyPill = sky && t < sky.end + 0.6 ? pill("sky", W / 2, H * 0.34, 0.8 + 0.2 * enter(sky.stepAt, 10), sky.label, { background: "transparent", color: snow, border: `4px solid ${snow}`, fontFamily: fonts.mono, fontSize: 44, letterSpacing: "0.12em" }, interpolate(t, [sky.end + 0.2, sky.end + 0.6], [1, 0], clamp)) : null;

  // snowfall in screen space, three depths
  const flakes = Array.from({ length: 70 }, (_, k) => {
    const depth = 0.3 + rnd(k + 500) * 0.7;
    const y = ((((rnd(k + 600) * H + t * (60 + 90 * depth)) % (H + 40)) + H + 40) % (H + 40)) - 20;
    const x = (((rnd(k + 700) * W - cam.x * zoom * 0.35 * depth + Math.sin(t * 1.3 + k) * 18) % W) + W) % W;
    return <circle key={k} cx={x} cy={y} r={2 + depth * 4} fill="#FFFFFF" opacity={0.25 + depth * 0.45} />;
  });

  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${ink} 0%, #24231B 55%, #2E2D24 100%)`, overflow: "hidden" }}>
      {skyGlow > 0 ? <AbsoluteFill style={{ background: "linear-gradient(180deg, #5A5844 0%, transparent 70%)", opacity: skyGlow }} /> : null}
      <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
        {orb}
        <path d={ridge} fill="#3A392F" opacity={0.7} />
      </svg>
      <div style={{ position: "absolute", left: 0, top: 0, transform, transformOrigin: "0 0" }}>
        <svg style={{ position: "absolute", left: -3000, top: -3000, overflow: "visible" }} width={17000} height={6000} viewBox="-3000 -3000 17000 6000">
          {trees.map((tr, i) => (
            <g key={i} transform={`translate(${tr.x},-6)`} opacity={tr.o}>
              <polygon points={`0,${-tr.h} ${tr.h * 0.32},0 ${-tr.h * 0.32},0`} fill="#4A493D" />
              <polygon points={`0,${-tr.h} ${tr.h * 0.14},${-tr.h * 0.55} ${-tr.h * 0.14},${-tr.h * 0.55}`} fill={snow} opacity={0.7} />
            </g>
          ))}
          <path d={ground} fill={snow} />
          <path d={ground} fill="none" stroke="#FFFFFF" strokeWidth={6} />
          {blockEls}
          {props.map(propEl)}
          {ballEls}
        </svg>
        {signEls}
        {figureEls}
      </div>
      <svg width={W} height={H} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {flakes}
      </svg>
      {calloutEls}
      {burstPills}
      {valuePills}
      {skyPill}
      {headline && words.length ? <Headline words={words} bg="dark" /> : null}
      {grain > 0 ? <Grain amount={grain} /> : null}
    </AbsoluteFill>
  );
};

