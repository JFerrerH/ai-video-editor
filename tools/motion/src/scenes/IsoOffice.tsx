import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, easeOut } from "../anim";
import { IconKind, LineIcon } from "../components/icons";
import { useFrameLayout } from "../layout";
import { textOn, useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";
import { SceneHeader, useHeaderSize } from "./header";
import { NODE_COLORS } from "./NetworkScene";

/** A floor position: a desk id (standing at its front) or a tile [u, v] (standing at its centre). */
export type OfficePos = string | [number, number];
export type OfficeDesk = { id: string; u: number; v: number };
export type OfficeAgent = { id: string; label: string; color?: string; at?: number; pos: OfficePos };
export type OfficeWalk = { agent: string; to: OfficePos; at: number; dur?: number; carry?: boolean };
export type OfficeBubble = { agent: string; text?: string; icon?: IconKind; at: number; until?: number };
/** Rewind the floor: from `at`, for `dur` s, the content clock runs back to `to`, then forward again. */
export type OfficeReplay = { at: number; dur: number; to?: number };

const COLS = 8; // default floor, mirrored by OFFICE_GRID in tools/storyboard.py
const ROWS = 6;
const WALK_S = 1.0;
const STRIDE_S = 0.42;
const BACK_SHARE = 0.6; // share of a replay spent rewinding; the rest plays forward again
const LABEL_FS = 28;
const SCRUB_H = 76;
const K = 1.3; // characters and desk furniture, relative to a tile (reads at 8x6 in portrait too)

type Pt = [number, number];
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

const hex = (c: string) => {
  const h = c.replace("#", "");
  const f = h.length === 3 ? h.split("").map((x) => x + x).join("") : h.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(f.slice(i, i + 2), 16));
};
/** Blend two hex colours (p = 0 → a, 1 → b). */
const mixHex = (a: string, b: string, p: number) => {
  const [x, y] = [hex(a), hex(b)];
  return `rgb(${x.map((v, i) => Math.round(lerp(v, y[i], p))).join(",")})`;
};

/** Desks along the back rows, two tiles apart, when the storyboard gives none (ids desk1, desk2…). */
export const autoDesks = (n: number, cols: number): OfficeDesk[] => {
  const per = Math.max(1, Math.floor((cols - 1) / 2));
  return Array.from({ length: n }, (_, k) => ({ id: `desk${k + 1}`, u: 1 + (k % per) * 2, v: 1 + Math.floor(k / per) * 2 }));
};

/** Content time for a real time: equal to it, except a replay winds it back to `to` and forward
 *  again, after which it runs `dur` behind (so cues after the replay still meet the narration). */
export const replayClock = (t: number, r?: OfficeReplay) => {
  if (!r || t < r.at) return t;
  const to = r.to ?? 0;
  if (t >= r.at + r.dur) return t - r.dur;
  const k = (t - r.at) / r.dur;
  return k < BACK_SHARE ? lerp(r.at, to, k / BACK_SHARE) : lerp(to, r.at, easeInOut((k - BACK_SHARE) / (1 - BACK_SHARE)));
};

/**
 * An isometric office in flat vector shapes: floor grid, two back walls, desks with monitors, and
 * block-built `agents` (colour + mono label) that appear (`at`), `walks` in straight lines between
 * desks or tiles (`carry: true` holds a document), and `bubbles` (text or an icon, `at`…`until`)
 * over their heads. `replay` shows a scrub bar while the floor's clock runs backwards and forwards
 * again; every element is a function of that clock, so walks and bubbles reverse with it.
 */
export const IsoOffice: React.FC<{
  durationInFrames: number;
  bg?: BgKind;
  kicker?: string;
  title?: string;
  emphasis?: string;
  cols?: number;
  rows?: number;
  desks?: OfficeDesk[];
  agents: OfficeAgent[];
  walks?: OfficeWalk[];
  bubbles?: OfficeBubble[];
  replay?: OfficeReplay;
}> = ({ durationInFrames, bg, kicker, title, emphasis, cols = COLS, rows = ROWS, desks, agents, walks = [], bubbles = [], replay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const real = frame / fps;
  const t = replayClock(real, replay);
  const { colors, fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, innerW, innerH, width, height } = useFrameLayout();
  const head = useHeaderSize(kicker, title);
  const dark = bg === "dark" || bg === "none";
  const base = bg === "dark" ? colors.ink : bg === "accent" ? colors.accent : bg === "none" ? "#202124" : colors.bg;
  const deskList = desks?.length ? desks : autoDesks(Math.max(4, agents.length), cols);
  const deskById = new Map(deskList.map((d) => [d.id, d]));

  // ── fit the room: floor diamond + walls + headroom for bubbles + labels under the front row ──
  const box = { x: safe.left, y: safe.top + head.height, w: innerW, h: innerH - head.height - (replay ? SCRUB_H + 16 : 0) };
  const span = cols + rows;
  const TOP_ROOM = 70;
  const FOOT_ROOM = 56;
  const tw = Math.min(box.w / (span / 2), (box.h - TOP_ROOM - FOOT_ROOM) / (1.25 + span / 4));
  const th = tw / 2;
  const wallH = tw * 1.25;
  const roomH = wallH + (span * th) / 2;
  const x0 = box.x + box.w / 2 - ((cols - rows) * tw) / 4;
  const y0 = box.y + TOP_ROOM + wallH + (box.h - TOP_ROOM - FOOT_ROOM - roomH) / 2;
  const P = (u: number, v: number, z = 0): Pt => [x0 + ((u - v) * tw) / 2, y0 + ((u + v) * th) / 2 - z];
  const pts = (ps: Pt[]) => ps.map((p) => p.join(",")).join(" ");

  /** An axis-aligned box on the floor: top, +v face (front-left) and +u face (front-right). */
  const Box = (key: string, u: number, v: number, su: number, sv: number, z: number, h: number, c: string, faces?: { left?: string; right?: string }) => (
    <g key={key}>
      <polygon points={pts([P(u, v + sv, z), P(u + su, v + sv, z), P(u + su, v + sv, z + h), P(u, v + sv, z + h)])} fill={faces?.left ?? mixHex(c, "#000000", 0.12)} />
      <polygon points={pts([P(u + su, v, z), P(u + su, v + sv, z), P(u + su, v + sv, z + h), P(u + su, v, z + h)])} fill={faces?.right ?? mixHex(c, "#000000", 0.26)} />
      <polygon points={pts([P(u, v, z + h), P(u + su, v, z + h), P(u + su, v + sv, z + h), P(u, v + sv, z + h)])} fill={mixHex(c, "#FFFFFF", 0.12)} />
    </g>
  );

  const place = (p: OfficePos): Pt => {
    if (typeof p === "string") {
      const d = deskById.get(p);
      return d ? [d.u + 0.5, Math.min(rows - 0.25, d.v + 1.3)] : [cols / 2, rows / 2];
    }
    return [p[0] + 0.5, p[1] + 0.5];
  };

  // ── agents: where each one is at content time t ──
  const sortedWalks = [...walks].sort((a, b) => a.at - b.at);
  const states = agents.map((a, i) => {
    let p = place(a.pos);
    let walking = false;
    let carry = false;
    let dir: Pt = [0, 1];
    for (const w of sortedWalks) {
      if (w.agent !== a.id || t < w.at) continue;
      const to = place(w.to);
      const d = w.dur ?? WALK_S;
      const k = Math.min(1, (t - w.at) / d);
      if (to[0] !== p[0] || to[1] !== p[1]) dir = [to[0] - p[0], to[1] - p[1]];
      if (k < 1) {
        walking = true;
        carry = !!w.carry;
        p = [lerp(p[0], to[0], easeInOut(k)), lerp(p[1], to[1], easeInOut(k))];
        break;
      }
      p = to;
    }
    const at = a.at ?? 0;
    const pop = t < at ? 0 : spring({ frame: (t - at) * fps, fps, config: { damping: 14, stiffness: 160, mass: 0.8 } });
    return { a, i, p, walking, carry, dir, pop, color: a.color ?? NODE_COLORS[i % NODE_COLORS.length] };
  });

  // ── colours of the room ──
  const floor = dark ? mixHex(base, "#FFFFFF", 0.07) : mixHex(base, colors.ink, 0.05);
  const wallL = dark ? mixHex(base, "#FFFFFF", 0.12) : mixHex(base, colors.ink, 0.11);
  const wallR = dark ? mixHex(base, "#FFFFFF", 0.17) : mixHex(base, colors.ink, 0.07);
  const grid = dark ? "rgba(255,255,255,0.08)" : "rgba(26,26,26,0.08)";
  const desk = dark ? "#4A4C53" : "#D9CDBB";
  const skin = "#EFE3D3";

  const items: { depth: number; el: React.ReactNode }[] = [];
  deskList.forEach((d) => {
    const busy = states.some((s) => s.pop > 0.5 && Math.hypot(s.p[0] - (d.u + 0.5), s.p[1] - Math.min(rows - 0.25, d.v + 1.3)) < 0.3);
    items.push({
      depth: d.u + d.v + 1,
      el: (
        <g key={`d${d.id}`}>
          {Box("top", d.u + 0.04, d.v + 0.1, 0.92, 0.8, 0, th * 0.62 * K, desk)}
          {Box("mon", d.u + 0.2, d.v + 0.28, 0.6, 0.08, th * 0.62 * K, th * 0.7 * K, "#2A2C31", {
            left: busy ? "#9FD8FF" : dark ? "#3B4A57" : "#C4D3DE",
          })}
          {Box("stand", d.u + 0.46, d.v + 0.32, 0.08, 0.05, th * 0.62 * K - 1, 6, "#2A2C31")}
        </g>
      ),
    });
  });
  states.forEach((s) => {
    if (s.pop <= 0.01) return;
    const [pu, pv] = s.p;
    const lift = (1 - s.pop) * tw * 0.7;
    const phase = (t / STRIDE_S) * Math.PI * 2;
    const step = s.walking ? Math.abs(Math.sin(phase)) * th * 0.18 : 0;
    const la = s.walking ? Math.max(0, Math.sin(phase)) * th * 0.14 : 0;
    const lb = s.walking ? Math.max(0, -Math.sin(phase)) * th * 0.14 : 0;
    const legH = th * 0.42 * K;
    const bodyH = th * 0.62 * K;
    const headH = th * 0.5 * K;
    const z = lift + step * 0.3;
    // eyes on the face turned the way it last walked: screen-right → +u face, else the +v face
    const right = s.dir[0] - s.dir[1] > 0.01;
    const hz = z + legH + bodyH;
    const hs = 0.3 * K;
    const [hu, hv] = [pu - hs / 2, pv - hs / 2];
    const eye = (k0: number): Pt[] => {
      const [k, e] = [k0 * K, 0.05 * K];
      const [zt, zb] = [hz + headH * 0.62, hz + headH * 0.42];
      return right
        ? [P(hu + hs, hv + k, zt), P(hu + hs, hv + k + e, zt), P(hu + hs, hv + k + e, zb), P(hu + hs, hv + k, zb)]
        : [P(hu + k, hv + hs, zt), P(hu + k + e, hv + hs, zt), P(hu + k + e, hv + hs, zb), P(hu + k, hv + hs, zb)];
    };
    const legC = mixHex(s.color, colors.ink, 0.55);
    items.push({
      depth: pu + pv,
      el: (
        <g key={`a${s.a.id}`} opacity={interpolate(s.pop, [0, 0.4], [0, 1], clamp)}>
          <ellipse cx={P(pu, pv)[0]} cy={P(pu, pv)[1]} rx={tw * 0.2 * K} ry={th * 0.2 * K} fill="#000" opacity={0.14 * s.pop} />
          {Box("lb", pu - 0.02 * K, pv - 0.16 * K, 0.14 * K, 0.14 * K, z + lb, legH, legC)}
          {Box("la", pu - 0.16 * K, pv - 0.02 * K, 0.14 * K, 0.14 * K, z + la, legH, legC)}
          {Box("body", pu - 0.18 * K, pv - 0.18 * K, 0.36 * K, 0.36 * K, z + legH, bodyH, s.color)}
          {Box("head", hu, hv, hs, hs, hz, headH, skin)}
          <polygon points={pts(eye(0.07))} fill="#22252A" />
          <polygon points={pts(eye(0.18))} fill="#22252A" />
          {s.carry ? Box("doc", pu + 0.16 * K, pv + 0.04, 0.05, 0.26 * K, z + legH + bodyH * 0.2, bodyH * 0.75, "#FFFFFF", { left: "#F1F1F1", right: "#FFFFFF" }) : null}
        </g>
      ),
    });
  });
  items.sort((a, b) => a.depth - b.depth);

  // gentle camera drift on real time (the replay doesn't rewind the camera)
  const drift = interpolate(frame, [0, durationInFrames], [1, 1.03], clamp);
  const origin = `${box.x + box.w / 2}px ${box.y + box.h / 2}px`;

  // ── scrub bar (real time) ──
  let scrub: React.ReactNode = null;
  if (replay) {
    const a = interpolate(real, [replay.at - 0.2, replay.at, replay.at + replay.dur, replay.at + replay.dur + 0.35], [0, 1, 1, 0], clamp);
    if (a > 0) {
      const back = real < replay.at + replay.dur * BACK_SHARE;
      const contentEnd = Math.max(0.1, durationInFrames / fps - replay.dur);
      const played = Math.min(1, Math.max(0, t / contentEnd));
      const tw2 = Math.min(760, innerW * 0.7);
      const sx = safe.left + (innerW - tw2) / 2 + 150;
      const trackW = tw2 - 150;
      // just under the room's front corner (and its labels), never below the reserved band
      const sy = Math.min(box.y + box.h + 16, y0 + (span * th) / 2 + FOOT_ROOM + 24) + SCRUB_H / 2;
      scrub = (
        <div style={{ position: "absolute", left: 0, top: 0, width, height, opacity: a }}>
          <div
            style={{
              position: "absolute",
              left: sx - 150,
              top: sy - 28,
              height: 56,
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontFamily: fonts.mono,
              fontSize: LABEL_FS,
              fontWeight: 700,
              color: pal.accent,
            }}
          >
            <svg width={36} height={28} viewBox="0 0 36 28">
              {back ? (
                <path d="M17 2 3 14l14 12zM33 2 19 14l14 12z" fill={pal.accent} />
              ) : (
                <path d="M8 2l22 12L8 26z" fill={pal.accent} />
              )}
            </svg>
            {back ? "replay" : "play"}
          </div>
          <div style={{ position: "absolute", left: sx, top: sy - 4, width: trackW, height: 8, borderRadius: 4, background: pal.track }} />
          <div style={{ position: "absolute", left: sx, top: sy - 4, width: trackW * played, height: 8, borderRadius: 4, background: pal.accent }} />
          <div style={{ position: "absolute", left: sx + trackW * played - 14, top: sy - 14, width: 28, height: 28, borderRadius: 14, background: pal.accent, boxShadow: "0 3px 10px rgba(0,0,0,0.25)" }} />
        </div>
      );
    }
  }

  return (
    <AbsoluteFill>
      <SceneHeader bg={bg} kicker={kicker} title={title} emphasis={emphasis} />
      <AbsoluteFill style={{ scale: String(drift), transformOrigin: origin }}>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0 }}>
          {/* back walls, then the floor diamond and its grid */}
          <polygon points={pts([P(0, 0), P(0, rows), P(0, rows, wallH), P(0, 0, wallH)])} fill={wallL} />
          <polygon points={pts([P(0, 0), P(cols, 0), P(cols, 0, wallH), P(0, 0, wallH)])} fill={wallR} />
          {/* a window on each wall */}
          <polygon points={pts([P(0, rows * 0.3), P(0, rows * 0.62), P(0, rows * 0.62, wallH * 0.82), P(0, rows * 0.3, wallH * 0.82)])} fill={dark ? "rgba(159,216,255,0.16)" : "rgba(159,200,230,0.45)"} />
          <polygon points={pts([P(cols * 0.42, 0, wallH * 0.3), P(cols * 0.72, 0, wallH * 0.3), P(cols * 0.72, 0, wallH * 0.82), P(cols * 0.42, 0, wallH * 0.82)])} fill={dark ? "rgba(159,216,255,0.16)" : "rgba(159,200,230,0.45)"} />
          <polygon points={pts([P(0, 0), P(cols, 0), P(cols, rows), P(0, rows)])} fill={floor} />
          {Array.from({ length: cols + 1 }, (_, k) => (
            <line key={`gu${k}`} x1={P(k, 0)[0]} y1={P(k, 0)[1]} x2={P(k, rows)[0]} y2={P(k, rows)[1]} stroke={grid} strokeWidth={2} />
          ))}
          {Array.from({ length: rows + 1 }, (_, k) => (
            <line key={`gv${k}`} x1={P(0, k)[0]} y1={P(0, k)[1]} x2={P(cols, k)[0]} y2={P(cols, k)[1]} stroke={grid} strokeWidth={2} />
          ))}
          {items.map((it) => it.el)}
        </svg>
        {/* labels under the feet, bubbles over the heads (HTML: brand fonts) */}
        {states.map((s) => {
          if (s.pop <= 0.01) return null;
          const [x, y] = P(s.p[0], s.p[1]);
          return (
            <div key={`l${s.a.id}`} style={{ position: "absolute", left: x - 200, top: y + th * 0.3 * K, width: 400, display: "flex", justifyContent: "center", opacity: interpolate(s.pop, [0.3, 1], [0, 1], clamp) }}>
              <span style={{ fontFamily: fonts.mono, fontSize: LABEL_FS, fontWeight: 700, lineHeight: 1.25, padding: "2px 12px", borderRadius: 8, background: s.color, color: textOn(s.color, colors.ink), whiteSpace: "nowrap" }}>
                {s.a.label}
              </span>
            </div>
          );
        })}
        {bubbles.map((b, k) => {
          const s = states.find((q) => q.a.id === b.agent);
          if (!s || s.pop <= 0.01 || t < b.at) return null;
          const inS = spring({ frame: (t - b.at) * fps, fps, config: { damping: 13, stiffness: 190, mass: 0.7 } });
          const outS = b.until === undefined ? 1 : interpolate(t, [b.until, b.until + 0.2], [1, 0], { ...clamp, easing: easeOut });
          const sc = inS * outS;
          if (sc <= 0.01) return null;
          const [x, y] = P(s.p[0], s.p[1], th * 1.54 * K + tw * 0.05);
          const surf = dark ? "#2B2D32" : "#FFFFFF";
          return (
            <div key={`b${k}`} style={{ position: "absolute", left: x - 300, width: 600, top: y - 14, display: "flex", justifyContent: "center" }}>
              <div style={{ translate: "0 -100%", scale: String(sc), transformOrigin: "50% 100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  style={{
                    background: surf,
                    color: dark ? "#F5F4F0" : colors.ink,
                    borderRadius: 18,
                    padding: b.icon && !b.text ? "10px 14px" : "8px 18px",
                    fontFamily: fonts.sans,
                    fontSize: LABEL_FS,
                    fontWeight: 600,
                    lineHeight: 1.25,
                    whiteSpace: "nowrap",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    boxShadow: dark ? "0 10px 24px rgba(0,0,0,0.45)" : "0 10px 24px rgba(30,30,20,0.16)",
                  }}
                >
                  {b.icon ? <LineIcon kind={b.icon} size={40} color={s.color} stroke={2.2} /> : null}
                  {b.text ?? null}
                </div>
                <svg width={26} height={14} viewBox="0 0 26 14" style={{ marginTop: -1 }}>
                  <path d="M0 0h26L13 14z" fill={surf} />
                </svg>
              </div>
            </div>
          );
        })}
      </AbsoluteFill>
      {scrub}
    </AbsoluteFill>
  );
};
