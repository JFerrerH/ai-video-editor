/**
 * Prototype "live stage": the speaker footage is inside the motion composition, so a plan can
 * move the camera (pull back, split, corner, push in) and place graphics behind the cut-out
 * speaker, under a split, or around a corner bubble. Engine components (HookTitle, Polaroids,
 * Waitlist, Flash, Captions) still render on top, unchanged.
 *
 * Every time in the plan is in seconds. Camera moves and events use absolute `start`/`end`;
 * times inside an event's props (`at`, `dropAt`…) are relative to the event's start.
 */
import React from "react";
import {
  AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from "remotion";
import { OverlayLayer, useBrandFonts, type OverlayEvent } from "./engine/Overlay";
import { BrandContext, useBrand, type Brand } from "./engine/theme";

export type CamMove = { kind: "pull" | "split" | "corner" | "push" | "side"; start: number; end: number; amount?: number };
export type LiveEvent = { type: string; layer: "front" | "behind" | "panel"; start: number; end: number; props: Record<string, any> };
export type LiveProps = {
  base: string; person: string; duration: number; brand: Brand;
  camera: CamMove[]; events: LiveEvent[]; engine: OverlayEvent[]; sfx: [number, string, number][];
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const inOut = Easing.bezier(0.65, 0, 0.35, 1);
const ramp = (t: number, a: number, len = 0.35, e = ease) => interpolate(t, [a, a + len], [0, 1], { ...clamp, easing: e });
const span = (t: number, a: number, b: number, inLen = 0.35, outLen = 0.25) =>
  Math.min(ramp(t, a, inLen), 1 - ramp(t, b - outLen, outLen, Easing.in(Easing.cubic)));
const popAt = (t: number, at: number, damping = 11) =>
  t < at ? 0 : spring({ frame: (t - at) * 30, fps: 30, config: { damping, stiffness: 180, mass: 0.7 } });

// ─── camera ───────────────────────────────────────────────────────────────────
const SPLIT_PANEL = 860; // px of the frame the bottom panel takes in a split
const CORNER = 0.3; // speaker scale in the corner bubble

type Cam = { scale: number; ox: number; oy: number; tx: number; ty: number; radius: number; clipBottom: number; bg: "ink" | "bg" | "tint"; shadow: number };

const camera = (moves: CamMove[], t: number): Cam => {
  const w = (k: CamMove["kind"]) => moves.filter((m) => m.kind === k)
    .map((m) => (m.kind === "push" ? ramp(t, m.start, m.end - m.start, inOut) * (t < m.end + 0.01 ? 1 : 0) * (m.amount ?? 0.07) : span(t, m.start, m.end, 0.45, 0.35)))
    .reduce((a, b) => Math.max(a, b), 0);
  const pull = w("pull"), split = w("split"), corner = w("corner"), push = w("push"), side = w("side");
  // side: reframe the speaker to the left third (zoom in so no edge shows), leaving the wall free on the right
  const scale = (1 - 0.2 * pull) * (1 - (1 - CORNER) * corner) * (1 + push) * (1 + 0.3 * side);
  const [ox, oy] = corner > 0 ? [1040, 1880] : pull > 0 ? [540, 760] : [540, 700];
  return {
    scale, ox, oy, tx: -170 * side, ty: -170 * split,
    radius: Math.max(56 * pull, 48 * split, 130 * corner),
    clipBottom: SPLIT_PANEL * split,
    bg: split > 0 ? "bg" : corner > 0 ? "tint" : "ink",
    shadow: corner,
  };
};

const camStyle = (c: Cam): React.CSSProperties => ({ transformOrigin: `${c.ox}px ${c.oy}px`, transform: `translate(${c.tx}px, ${c.ty}px) scale(${c.scale})` });

// ─── live components ─────────────────────────────────────────────────────────
type FX = React.FC<{ t: number; d: number; p: Record<string, any> }>;

const Stickers: FX = ({ t, d, p }) => {
  const { colors, fonts } = useBrand();
  const o = 1 - ramp(t, d - 0.2, 0.2);
  return (
    <>
      {(p.items as any[]).map((s, i) => {
        const k = popAt(t, s.at);
        if (k <= 0) return null;
        return (
          <div key={i} style={{ position: "absolute", left: s.x, top: s.y, transform: `rotate(${s.rot ?? 0}deg) scale(${0.6 + 0.4 * k})`, opacity: Math.min(1, k * 2) * o,
            background: colors.ink, color: colors.bg, padding: "14px 34px 20px", borderRadius: 26, fontFamily: fonts.serif, fontStyle: "italic", fontSize: s.size ?? 84,
            boxShadow: "0 18px 40px rgba(0,0,0,.35)", whiteSpace: "nowrap" }}>{s.text}</div>
        );
      })}
    </>
  );
};

const BehindWord: FX = ({ t, d, p }) => {
  const { colors, fonts } = useBrand();
  const vis = span(t, 0, d, 0.3, 0.25);
  const rise = ramp(t, p.riseAt ?? 0, 0.4);
  const strike = p.strikeAt != null ? ramp(t, p.strikeAt, 0.3, inOut) : 0;
  const y = p.y ?? 640;
  return (
    <AbsoluteFill style={{ opacity: vis }}>
      {p.lead ? <div style={{ position: "absolute", top: y - 80, width: "100%", textAlign: "center", fontFamily: fonts.mono, fontSize: 40, letterSpacing: 6, color: colors.tint1, textTransform: "uppercase" }}>{p.lead}</div> : null}
      <div style={{ position: "absolute", top: y, width: "100%", textAlign: "center", overflow: "hidden", height: 260 }}>
        <div style={{ transform: `translateY(${(1 - rise) * 100}%)`, fontFamily: fonts.serif, fontWeight: 600, fontSize: p.size ?? 196, color: p.color ?? colors.bg, letterSpacing: -4, lineHeight: "240px", textShadow: "0 8px 40px rgba(0,0,0,.25)" }}>
          {p.word}
        </div>
        {strike > 0 ? <div style={{ position: "absolute", left: 70, top: 128, height: 14, width: 940 * strike, background: colors.accent, borderRadius: 7 }} /> : null}
      </div>
    </AbsoluteFill>
  );
};

/** A document-like object that can come back later in the story (fill shows how far it got). */
const Doc: React.FC<{ p: Record<string, any>; t: number; w?: number }> = ({ p, t, w = 640 }) => {
  const { colors, fonts } = useBrand();
  const fill = p.fillAt != null ? interpolate(ramp(t, p.fillAt, p.fillDur ?? 0.6, inOut), [0, 1], [p.fillFrom ?? 0, p.fillTo ?? 0]) : (p.fillFrom ?? 0);
  return (
    <div style={{ width: w, background: "#fff", borderRadius: 22, padding: "30px 38px 36px", boxShadow: "0 22px 50px rgba(31,35,40,.25)", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, width: `${fill * 100}%`, background: p.fillColor ?? colors.tint1 }} />
      <div style={{ position: "relative" }}>
        <div style={{ fontFamily: fonts.mono, fontSize: 24, letterSpacing: 4, color: colors.muted }}>{p.kicker}</div>
        <div style={{ fontFamily: fonts.serif, fontSize: 50, lineHeight: 1.08, color: colors.ink, marginTop: 12 }}>{p.title} {p.italic ? <i>{p.italic}</i> : null}</div>
        {[0.9, 0.75, 0.82].map((k, i) => <div key={i} style={{ height: 10, width: `${k * 100}%`, background: "#E6E3DD", borderRadius: 5, marginTop: i ? 12 : 26 }} />)}
      </div>
      {fill > 0.03 ? <div style={{ position: "absolute", right: 30, top: 22, fontFamily: fonts.sans, fontWeight: 600, fontSize: 50, color: colors.accent }}>{Math.round(fill * 100)}%</div> : null}
    </div>
  );
};

const DocCard: FX = ({ t, d, p }) => {
  const { colors, fonts } = useBrand();
  const s = popAt(t, 0, 13);
  const out = ramp(t, d - 0.3, 0.3, Easing.in(Easing.cubic));
  const pulse = p.pulseAt != null && t > p.pulseAt ? 1 + 0.05 * Math.exp(-(t - p.pulseAt) * 6) : 1;
  const tag = p.tagAt != null ? ramp(t, p.tagAt, 0.3) : 0;
  return (
    <div style={{ position: "absolute", left: p.x ?? 220, top: p.y ?? 210, opacity: Math.min(1, s * 2) * (1 - out), transform: `scale(${(0.8 + 0.2 * s) * pulse}) rotate(${p.rot ?? -2}deg)` }}>
      {p.tag ? <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 34, color: colors.bg, background: colors.accent, display: "inline-block", padding: "8px 20px", borderRadius: 12,
        marginBottom: 14, opacity: tag, transform: `translateY(${(1 - tag) * 16}px)` }}>{p.tag}</div> : null}
      <Doc p={p} t={t} />
    </div>
  );
};

const DrawerPanel: FX = ({ t, d, p }) => {
  const vis = span(t, 0, d, 0.45, 0.35);
  const cardIn = ramp(t, 0.15, 0.5);
  const drop = ramp(t, p.dropAt, 0.45, Easing.in(Easing.quad));
  const shut = ramp(t, p.shutAt - 0.16, 0.16, Easing.in(Easing.cubic));
  const th = t > p.shutAt ? Math.sin((t - p.shutAt) * 40) * 6 * Math.exp(-(t - p.shutAt) * 9) : 0;
  return (
    <AbsoluteFill style={{ opacity: vis, transform: `translateY(${(1 - vis) * 120}px)` }}>
      <div style={{ position: "absolute", left: 160, top: 1560 + th, width: 760, height: 300, background: "#2B2F35", borderRadius: 18 }} />
      <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1600 + th, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 220, top: 1140 + (1 - cardIn) * 80 + drop * 420, opacity: cardIn, transform: `rotate(${-2 + drop * 4}deg)` }}>
          <Doc p={p.card} t={t} />
        </div>
      </div>
      <div style={{ position: "absolute", left: 130, top: 1660 - 110 * shut + th, width: 820, height: 210, background: "#3A3F46", borderRadius: 18, boxShadow: "0 -6px 24px rgba(0,0,0,.25)" }}>
        <div style={{ position: "absolute", left: 330, top: 92, width: 160, height: 22, background: "#8A9099", borderRadius: 11 }} />
      </div>
    </AbsoluteFill>
  );
};

/** A phone whose screen changes on cue: in a split it fills the bottom panel; in a corner layout it is the hero. */
const PhonePanel: FX = ({ t, d, p }) => {
  const vis = span(t, 0, d, 0.45, 0.35);
  const corner = p.mode === "corner", side = p.mode === "side";
  const W = corner ? 520 : side ? 380 : 400, H = W * 2.164;
  const top = corner ? 200 : side ? 470 : 1120;
  const left = side ? 650 + (1 - vis) * 420 : (1080 - W) / 2 + (corner ? -130 : 0);
  const bob = side ? Math.sin(t * 1.6) * 8 : 0;
  const screens = p.screens as { src: string; at: number }[];
  const cur = screens.reduce((k, s, i) => (t >= s.at ? i : k), 0);
  const slide = ramp(t, screens[cur].at, 0.45, inOut);
  const scroll = p.scroll ? interpolate(t, [0, d], [0, -p.scroll], clamp) : 0;
  return (
    <AbsoluteFill style={{ opacity: vis }}>
      <div style={{ position: "absolute", left, top: top + bob + (side ? 0 : (1 - vis) * 140), width: W, height: corner || side ? H : Math.min(H, 1920 - top + 80),
        borderRadius: 64, background: "#111", padding: 14, boxShadow: "0 30px 70px rgba(31,35,40,.35)", transform: `rotate(${corner ? -3 : side ? 4 : 0}deg)` }}>
        <div style={{ width: "100%", height: "100%", borderRadius: 52, overflow: "hidden", position: "relative", background: "#fff" }}>
          {screens.map((s, i) => (i === cur || i === cur - 1) ? (
            <Img key={i} src={staticFile(s.src)} style={{ position: "absolute", width: "100%", top: scroll,
              transform: `translateX(${i === cur ? (cur === 0 ? 0 : (1 - slide) * 100) : -slide * 30}%)`, opacity: i === cur ? 1 : 1 - slide * 0.5 }} />
          ) : null)}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const CodePanel: FX = ({ t, d, p }) => {
  const { fonts } = useBrand();
  const vis = span(t, 0, d, 0.45, 0.35);
  const lines = p.lines as string[];
  const total = lines.join("\n").length;
  const n = Math.floor(interpolate(t, [p.typeFrom ?? 0.3, p.typeTo ?? d - 0.4], [0, total], clamp));
  let left = n;
  return (
    <AbsoluteFill style={{ opacity: vis }}>
      <div style={{ position: "absolute", left: p.x ?? 70, top: (p.y ?? 1120) + (1 - vis) * 120, width: p.w ?? 940, height: p.h ?? 700, transformOrigin: "0 0", transform: `scale(${p.scale ?? 1})`, background: "#1E2127", borderRadius: 30, padding: "30px 40px", boxShadow: "0 30px 70px rgba(0,0,0,.35)" }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => <div key={c} style={{ width: 20, height: 20, borderRadius: 10, background: c }} />)}
          <div style={{ marginLeft: 20, fontFamily: fonts.mono, fontSize: 26, color: "#8A9099" }}>{p.file}</div>
          {p.badge ? <div style={{ marginLeft: "auto", fontFamily: fonts.mono, fontSize: 26, color: "#1E2127", background: "#F2F1EE", padding: "6px 16px", borderRadius: 10 }}>
            {p.badge.replace("{n}", String(Math.round(interpolate(t, [0, d], p.badgeRange ?? [1, 14], clamp))))}</div> : null}
        </div>
        <div style={{ marginTop: 34, fontFamily: fonts.mono, fontSize: 34, lineHeight: 1.7, color: "#E6E6E6", whiteSpace: "pre" }}>
          {lines.map((l, i) => { const s = l.slice(0, Math.max(0, left)); left -= l.length + 1; return <div key={i}><span style={{ color: "#5C6370", marginRight: 26 }}>{i + 1}</span>{s}{left < 0 && left > -l.length - 2 && Math.floor(t * 2) % 2 ? "▍" : ""}</div>; })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Gauge: FX = ({ t, d, p }) => {
  const { colors, fonts } = useBrand();
  const vis = span(t, 0, d, 0.4, 0.3);
  const creep = interpolate(t, [0.25, p.slamAt - 0.15], [-80, -10], { ...clamp, easing: inOut });
  const slam = t < p.slamAt ? 0 : spring({ frame: (t - p.slamAt) * 30, fps: 30, config: { damping: 7, stiffness: 220, mass: 0.6 } });
  const ang = creep + (82 - creep) * slam;
  const st = popAt(t, p.slamAt + 0.1, 9);
  const arc = (a0: number, a1: number, col: string) => {
    const r = 200, cx = 310, cy = 250, q = (a: number) => [cx + r * Math.cos((a - 90) * Math.PI / 180), cy + r * Math.sin((a - 90) * Math.PI / 180)];
    const [x0, y0] = q(a0), [x1, y1] = q(a1);
    return <path d={`M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1}`} stroke={col} strokeWidth={34} fill="none" />;
  };
  return (
    <div style={{ position: "absolute", left: 230, top: p.y ?? 380, width: 620, height: 420, background: colors.bg, borderRadius: 30, opacity: vis, transform: `translateY(${(1 - vis) * 60}px)`, boxShadow: "0 20px 50px rgba(0,0,0,.3)" }}>
      <div style={{ position: "absolute", top: 26, width: "100%", textAlign: "center", fontFamily: fonts.mono, fontSize: 26, letterSpacing: 5, color: colors.muted }}>{p.label}</div>
      <svg width={620} height={420} style={{ position: "absolute", top: 40 }}>
        {arc(-90, -30, colors.success)}{arc(-30, 30, "#E2A93B")}{arc(30, 90, colors.accent)}
        <g transform={`rotate(${ang} 310 250)`}><rect x={304} y={70} width={12} height={185} rx={6} fill={colors.ink} /></g>
        <circle cx={310} cy={250} r={22} fill={colors.ink} />
      </svg>
      {st > 0 ? <div style={{ position: "absolute", left: 250, top: -34, width: 440, textAlign: "center", transform: `rotate(-4deg) scale(${1.6 - 0.6 * st})`, opacity: Math.min(1, st * 1.5),
        border: `5px solid ${colors.accent}`, color: colors.accent, fontFamily: fonts.mono, fontWeight: 500, fontSize: 30, letterSpacing: 2, whiteSpace: "nowrap", padding: "8px 0", borderRadius: 10, background: colors.bg }}>{p.stamp}</div> : null}
    </div>
  );
};

const Stuck: FX = ({ t, d, p }) => {
  const { colors, fonts } = useBrand();
  const vis = span(t, 0, d, 0.35, 0.2);
  const v = interpolate(t, [0.2, 0.8], [0, p.stopAt ?? 0.14], { ...clamp, easing: ease });
  const no = t > p.resultAt;
  const blink = no ? 0.55 + 0.45 * Math.cos((t - p.resultAt) * 14) : 1;
  return (
    <div style={{ position: "absolute", left: 170, top: p.y ?? 260, width: 740, padding: "30px 40px 36px", background: colors.bg, borderRadius: 26, opacity: vis, transform: `translateY(${(1 - vis) * -50}px)`, boxShadow: "0 18px 44px rgba(0,0,0,.3)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: fonts.mono, fontSize: 26, letterSpacing: 3, color: colors.muted }}>
        <span>{p.label}</span><span style={{ color: no ? colors.accent : colors.muted }}>{no ? p.resultTag : `${Math.round(v * 100)}%`}</span>
      </div>
      <div style={{ height: 22, background: "#E3E0DA", borderRadius: 11, marginTop: 20, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${v * 100}%`, background: no ? colors.accent : colors.ink, opacity: blink, borderRadius: 11 }} />
      </div>
      <div style={{ fontFamily: fonts.serif, fontSize: 52, color: colors.accent, marginTop: 18, opacity: no ? ramp(t, p.resultAt, 0.25) : 0 }}>{p.result} <i>{p.resultItalic}</i></div>
    </div>
  );
};

const Notice: FX = ({ t, d, p }) => {
  const { fonts } = useBrand();
  const s = popAt(t, 0, 14);
  const out = ramp(t, d - 0.3, 0.3, Easing.in(Easing.cubic));
  return (
    <div style={{ position: "absolute", left: 60, top: 70 + (1 - s) * -220 - out * 260, width: 960, padding: "26px 30px", borderRadius: 40,
      background: "rgba(245,245,245,.94)", boxShadow: "0 16px 40px rgba(0,0,0,.28)", display: "flex", gap: 26, alignItems: "center" }}>
      <div style={{ width: 92, height: 92, borderRadius: 22, background: "#34C759", display: "grid", placeItems: "center", color: "#fff", fontFamily: fonts.sans, fontSize: 52, fontWeight: 600 }}>✉</div>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: fonts.sans, fontSize: 34, fontWeight: 600, color: "#111" }}><span>{p.from}</span><span style={{ fontWeight: 400, color: "#777", fontSize: 28 }}>ahora</span></div>
        <div style={{ fontFamily: fonts.sans, fontSize: 34, color: "#222", marginTop: 4 }}>{p.text}</div>
      </div>
    </div>
  );
};

const FX_REGISTRY: Record<string, FX> = { Stickers, BehindWord, DocCard, DrawerPanel, PhonePanel, CodePanel, Gauge, Stuck, Notice };

const Layer: React.FC<{ events: LiveEvent[]; layer: LiveEvent["layer"]; t: number }> = ({ events, layer, t }) => (
  <>
    {events.filter((e) => e.layer === layer && t >= e.start - 0.05 && t <= e.end + 0.05).map((e, i) => {
      const C = FX_REGISTRY[e.type];
      if (!C) throw new Error(`Unknown live event ${e.type}`);
      return <AbsoluteFill key={i}><C t={t - e.start} d={e.end - e.start} p={e.props} /></AbsoluteFill>;
    })}
  </>
);

export const Live: React.FC<LiveProps> = (props) => {
  const { brand, camera: moves, events } = props;
  const ready = useBrandFonts(brand);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cam = camera(moves, t);
  const c = brand.colors;
  const bg = cam.bg === "ink" ? c.ink : cam.bg === "bg" ? c.bg : `radial-gradient(120% 80% at 20% 10%, ${c.tint1}, ${c.bg} 55%, ${c.tint2})`;
  const behind = events.filter((e) => e.layer === "behind");
  return (
    <BrandContext.Provider value={brand}>
      <AbsoluteFill style={{ background: bg, fontFamily: brand.fonts.sans }}>
        {ready ? <Layer events={events} layer="panel" t={t} /> : null}
        <AbsoluteFill style={{ clipPath: `inset(0 0 ${cam.clipBottom}px 0 round 0 0 ${cam.radius}px ${cam.radius}px)` }}>
          <AbsoluteFill style={camStyle(cam)}>
            <AbsoluteFill style={{ borderRadius: cam.radius, overflow: "hidden", boxShadow: cam.shadow ? `0 30px 80px rgba(0,0,0,${0.35 * cam.shadow}), 0 0 0 ${10 * cam.shadow / cam.scale}px #fff` : undefined }}>
              <OffthreadVideo src={staticFile(props.base)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </AbsoluteFill>
          </AbsoluteFill>
          {ready ? <Layer events={events} layer="behind" t={t} /> : null}
          {behind.map((e, i) => (
            <Sequence key={i} from={Math.round((e.start - 0.1) * fps)} durationInFrames={Math.round((e.end - e.start + 0.2) * fps)}>
              <AbsoluteFill style={camStyle(cam)}>
                <OffthreadVideo src={staticFile(props.person)} startFrom={Math.round((e.start - 0.1) * fps)} transparent muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </AbsoluteFill>
            </Sequence>
          ))}
        </AbsoluteFill>
        {ready ? <Layer events={events} layer="front" t={t} /> : null}
        {ready ? <OverlayLayer events={props.engine} /> : null}
        {props.sfx.map(([at, name, v], i) => (
          <Sequence key={`s${i}`} from={Math.round(at * fps)}><Audio src={staticFile(`${name}.wav`)} volume={v} /></Sequence>
        ))}
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};
