import { Easing, interpolate, spring } from "remotion";
import { clamp, easeInOut, easeOut } from "../anim";
import type { PoseCue } from "../explainer/Figure";
import type { PoseName, PropName } from "../explainer/poses";

/**
 * World scenes: a storyboard-level world (terrain + objects) acted on by cued actions. Everything
 * here is a pure function of time `t` (seconds from the start of the world run): no state is kept
 * between frames, so any frame renders on its own. World units: x along the ground (0 = start),
 * ground at y = 0, up is negative y.
 */

export type BlockObj = { id: string; kind: "block"; x: number; w: number; h: number; label: string; tag?: string; tone?: "ice" | "alert"; burst?: string; hidden?: boolean };
export type BallObj = { id: string; kind: "ball"; x: number; r?: number; grow?: number; value?: number; prefix?: string; suffix?: string; locale?: string; hidden?: boolean };
export type FigureObj = { id: string; kind: "figure"; x: number; pose?: PoseName; facing?: "left" | "right"; scale?: number; hidden?: boolean };
export type SignObj = { id: string; kind: "sign"; x: number; text: string; sub?: string; hidden?: boolean };
export type PropItem = "paper" | "towel" | "dumbbell" | "calculator";
export type PropObj = { id: string; kind: "prop"; x: number; item: PropItem; label?: string; size?: number; hidden?: boolean };
export type CalloutObj = { id: string; kind: "callout"; x?: number; text: string; target: string; dx?: number; dy?: number; hidden?: boolean };
export type WorldObj = BlockObj | BallObj | FigureObj | SignObj | PropObj | CalloutObj;

export type WorldDef = { terrain?: { kind?: "snow"; slope?: number }; objects: WorldObj[] };

export type Action = {
  at: number;
  target: string;
  do: string;
  // roll
  to?: number | string;
  arrive?: number;
  dur?: number;
  // grow / value
  by?: number;
  v?: number;
  chip?: string;
  // break
  into?: string;
  // push / pile
  dx?: number;
  amount?: number;
  // pose
  pose?: PoseName;
  prop?: PropName | null;
  // walk / throw
  x?: number;
  item?: string;
  // hold
  on?: string; // hold: the figure holding it
  // camera
  follow?: string;
  zoom?: number;
  // timelapse
  steps?: string[];
  until?: number;
};

export const WORLD_KINDS = ["block", "ball", "figure", "sign", "prop", "callout"] as const;

/** Which actions apply to which kinds (mirrored in tools/storyboard.py). */
export const ACTIONS: Record<string, readonly string[]> = {
  roll: ["ball"],
  grow: ["ball"],
  value: ["ball"],
  break: ["block"],
  push: ["block"],
  pile: ["block"],
  highlight: ["block"],
  pose: ["figure"],
  walk: ["figure"],
  throw: ["figure"],
  fall: ["prop"],
  hold: ["prop"],
  show: WORLD_KINDS,
  hide: WORLD_KINDS,
  timelapse: ["sky"],
  camera: ["camera"],
};

export const DEFAULT_GROW = 1.45;
export const ABSORB_S = 0.38; // the ball grows once the pieces are in
export const ROLL_SPEED = 650; // world units/s when a roll has no `dur`/`arrive`
export const COAST_S = 0.7; // after breaking a block the ball rolls on through its place

const springAt = (t: number, at: number, fps: number, config = { damping: 11, stiffness: 140, mass: 0.7 }) =>
  t < at ? 0 : spring({ frame: Math.round((t - at) * fps), fps, config });

type Seg = { t0: number; t1: number; x0: number; x1: number; ease: (u: number) => number };

/** Everything about a world that doesn't change per frame: objects by id, sorted actions, ball paths. */
export const buildWorld = (def: WorldDef, actions: Action[], fps: number) => {
  const objs = new Map(def.objects.map((o) => [o.id, o]));
  const acts = [...actions].sort((a, b) => a.at - b.at);
  const of = (id: string) => acts.filter((a) => a.target === id);

  // break times: explicit `break`, or a roll that arrives at the block
  const breaks = new Map<string, { at: number; into?: string }>();
  // ball paths, built in order so each roll starts wherever the ball is
  const paths = new Map<string, Seg[]>();
  const radiusFns = new Map<string, (t: number) => number>();

  for (const o of def.objects) {
    if (o.kind !== "ball") continue;
    const segs: Seg[] = [];
    paths.set(o.id, segs);
    const r0 = o.r ?? 70;
    const grow = o.grow ?? DEFAULT_GROW;
    const growAts: { at: number; by: number }[] = [];
    const radius = (t: number) => growAts.reduce((r, g) => r * (1 + (g.by - 1) * springAt(t, g.at, fps)), r0);
    radiusFns.set(o.id, radius);
    const xAt = (t: number) => segX(segs, o.x, t);
    for (const a of of(o.id)) {
      if (a.do === "grow") growAts.push({ at: a.at, by: a.by ?? grow });
      if (a.do !== "roll") continue;
      const x0 = xAt(a.at);
      const blk = typeof a.to === "string" ? objs.get(a.to) : undefined;
      if (blk && blk.kind === "block") {
        // contact: the ball's front reaches the block's face, at the radius it has then
        const rNow = radius(a.at);
        const x1 = blk.x - rNow * 0.92;
        const t1 = a.arrive ?? a.at + (a.dur ?? Math.max(0.4, Math.abs(x1 - x0) / ROLL_SPEED));
        segs.push({ t0: a.at, t1, x0, x1, ease: Easing.bezier(0.5, 0, 0.85, 0.75) }); // picks up speed
        segs.push({ t0: t1, t1: t1 + COAST_S, x0: x1, x1: blk.x + blk.w * 0.55, ease: easeOut });
        breaks.set(blk.id, { at: t1, into: o.id });
        growAts.push({ at: t1 + ABSORB_S, by: grow });
      } else {
        const x1 = typeof a.to === "number" ? a.to : x0;
        const t1 = a.arrive ?? a.at + (a.dur ?? Math.max(0.4, Math.abs(x1 - x0) / ROLL_SPEED));
        segs.push({ t0: a.at, t1, x0, x1, ease: easeInOut });
      }
    }
  }
  for (const a of acts) if (a.do === "break" && !breaks.has(a.target)) breaks.set(a.target, { at: a.at, into: a.into });

  return { def, objs, acts, of, breaks, paths, radiusFns, fps, slope: def.terrain?.slope ?? 9 };
};
export type World = ReturnType<typeof buildWorld>;

const segX = (segs: Seg[], x0: number, t: number) => {
  let x = x0;
  for (const s of segs) {
    if (t < s.t0) break;
    x = s.x0 + (s.x1 - s.x0) * s.ease(Math.min(1, (t - s.t0) / Math.max(1e-3, s.t1 - s.t0)));
  }
  return x;
};

/** Visible at t: `hidden` objects appear on `show`, anything vanishes on `hide`; falls/throws reveal their prop. */
export const visibleAt = (w: World, id: string, t: number) => {
  const o = w.objs.get(id);
  if (!o) return false;
  let vis = !o.hidden;
  for (const a of w.acts) {
    if (a.at > t) break;
    if (a.target === id && a.do === "show") vis = true;
    if (a.target === id && a.do === "hide") vis = false;
    if (a.target === id && (a.do === "fall" || a.do === "hold")) vis = true;
    if (a.do === "throw" && a.item === id) vis = true;
  }
  return vis;
};

/** First time an object is shown (for entrance springs); 0 if visible from the start. */
export const shownAt = (w: World, id: string) => {
  const o = w.objs.get(id);
  if (!o?.hidden) return 0;
  const a = w.acts.find((a) => (a.target === id && ["show", "fall", "hold"].includes(a.do)) || (a.do === "throw" && a.item === id));
  return a ? a.at : 0;
};

export const ballAt = (w: World, id: string, t: number) => {
  const o = w.objs.get(id) as BallObj;
  const x = segX(w.paths.get(id) ?? [], o.x, t);
  const r = w.radiusFns.get(id)!(t);
  // value: count up over 0.6 s from each `value` action
  const vals = w.of(id).filter((a) => a.do === "value");
  let prev = o.value ?? 0;
  let value = prev;
  let pop = 1;
  let lastAt = -1;
  for (const a of vals) {
    if (a.at > t) break;
    const u = interpolate(t, [a.at, a.at + 0.6], [0, 1], { ...clamp, easing: easeOut });
    value = prev + ((a.v ?? prev) - prev) * u;
    if (u >= 1) prev = a.v ?? prev;
    lastAt = a.at;
  }
  if (lastAt >= 0) pop = 0.85 + 0.15 * spring({ frame: Math.round((t - lastAt) * w.fps), fps: w.fps, config: { damping: 9, stiffness: 220 } });
  // squash on the latest impact
  const hit = [...w.breaks.values()].filter((b) => b.into === id && b.at <= t).pop();
  const since = hit ? t - hit.at : 99;
  const squash = since < 0.25 ? 1 - 0.12 * Math.sin((since / 0.25) * Math.PI) : 1;
  return { x, r, r0: o.r ?? 70, value: Math.round(value), pop, squash, rot: (x / r) * (180 / Math.PI) };
};

export const blockAt = (w: World, id: string, t: number) => {
  const o = w.objs.get(id) as BlockObj;
  let dx = 0;
  let pile = 0;
  let glow = 0;
  for (const a of w.of(id)) {
    if (a.at > t) break;
    const u = Math.min(1, (t - a.at) / Math.max(0.01, a.dur ?? 1));
    if (a.do === "push") dx += (a.dx ?? 12) * easeInOut(u) + (u < 1 ? Math.sin((t - a.at) * 40) * 2.5 : 0);
    if (a.do === "pile") pile += (a.amount ?? 40) * easeOut(u);
    if (a.do === "highlight" && (a.until === undefined || t < a.until)) glow = 0.55 + 0.45 * Math.sin((t - a.at) * 5);
  }
  const brk = w.breaks.get(id);
  const near = brk ? interpolate(t, [brk.at - 0.25, brk.at], [0, 1], clamp) : 0;
  return { x: o.x + dx + Math.sin(t * 60) * 3 * near, pile, glow, broken: brk && t >= brk.at ? brk : undefined };
};

/** The figure's world x and whether it's walking (walk cycle weight, time in the walk, direction). */
export const figureAt = (w: World, id: string, t: number) => {
  const o = w.objs.get(id) as FigureObj;
  let x = o.x;
  let walking: { w: number; since: number; dir: number } | null = null;
  for (const a of w.of(id)) {
    if (a.do !== "walk" || a.at > t) continue;
    const dur = a.dur ?? Math.max(0.6, Math.abs((a.x ?? x) - x) / 380);
    const u = Math.min(1, (t - a.at) / dur);
    const from = x;
    x = from + ((a.x ?? from) - from) * easeInOut(u);
    if (u < 1) walking = { w: Math.min(1, (t - a.at) / 0.15, (a.at + dur - t) / 0.15), since: t - a.at, dir: Math.sign((a.x ?? from) - from) };
  }
  const poses: PoseCue[] = [{ pose: o.pose ?? "stand" }];
  for (const a of w.of(id)) if (a.do === "pose" && a.pose) poses.push({ pose: a.pose, at: a.at, ...(a.prop !== undefined ? { prop: a.prop } : {}) });
  return { x, walking, poses, scale: o.scale ?? 1 };
};

/** A prop's place: where it lies, falling from the sky, thrown along an arc, or held over a figure's head. */
export const propAt = (w: World, id: string, t: number, figH: number) => {
  const o = w.objs.get(id) as PropObj;
  let x = o.x;
  let y = 0;
  let rot = 0;
  for (const a of w.acts) {
    if (a.at > t) break;
    if (a.target === id && a.do === "fall") {
      const dur = a.dur ?? 1.2;
      const u = Math.min(1, (t - a.at) / dur);
      const tx = typeof a.to === "number" ? a.to : o.x;
      x = tx + Math.sin(u * Math.PI * 3) * 60 * (1 - u);
      y = -1500 * (1 - Easing.in(Easing.quad)(u));
      rot = Math.sin(u * Math.PI * 4) * 25 * (1 - u);
    }
    if (a.do === "throw" && a.item === id) {
      const f = figureAt(w, a.target, a.at);
      const dur = a.dur ?? 0.7;
      const u = Math.min(1, (t - a.at) / dur);
      const tx = typeof a.to === "number" ? a.to : f.x + 220;
      x = f.x + (tx - f.x) * u;
      y = -figH * 0.75 * (1 - u) - Math.sin(u * Math.PI) * 220;
      rot = u * 300;
    }
    if (a.target === id && a.do === "hold" && a.on) {
      const f = figureAt(w, a.on, t);
      x = f.x;
      y = -figH * f.scale * 1.08;
    }
  }
  return { x, y, rot };
};

/** Sky timelapse at t: active step label and the sun/moon phase (0–1 per step), or null. */
export const skyAt = (w: World, t: number) => {
  const a = [...w.of("sky")].reverse().find((a) => a.do === "timelapse" && a.at <= t);
  if (!a || !a.steps?.length) return null;
  const dur = a.dur ?? a.steps.length;
  const per = dur / a.steps.length;
  const k = Math.min(a.steps.length - 1, Math.floor((t - a.at) / per));
  const done = t - a.at > dur;
  return { label: a.steps[k], k, phase: done ? 1 : ((t - a.at) % per) / per, done, stepAt: a.at + k * per, end: a.at + dur };
};

/** Camera target at t: x, zoom and whether it follows a ball (for the pull-back), blended between targets. */
export const cameraAt = (w: World, t: number) => {
  const cams = w.of("camera").filter((a) => a.do === "camera");
  const firstBall = w.def.objects.find((o) => o.kind === "ball");
  const targetOf = (a: Action | undefined, s: number) => {
    const follow = a ? a.follow : firstBall?.id;
    if (follow) {
      const o = w.objs.get(follow);
      if (o?.kind === "ball") {
        // lagged follow, looking ahead of a rolling ball
        let x = 0;
        for (let k = 0; k < 7; k++) x += ballAt(w, o.id, s - k * 0.06).x;
        const b = ballAt(w, o.id, s);
        return { x: x / 7 + 160, y: -b.r * 0.6, zoom: (a?.zoom ?? 1.3) * (b.r0 / b.r) ** 0.25 };
      }
      if (o?.kind === "figure") return { x: figureAt(w, o.id, s).x, y: -150, zoom: a?.zoom ?? 1.3 };
      if (o?.kind === "block") return { x: o.x + o.w / 2, y: -o.h / 2 + 40, zoom: a?.zoom ?? 1.3 };
      if (o) return { x: o.x ?? 0, y: -120, zoom: a?.zoom ?? 1.3 };
    }
    return { x: a?.x ?? 0, y: -120, zoom: a?.zoom ?? 1.3 };
  };
  let cur = targetOf(undefined, t);
  for (const a of cams) {
    if (a.at > t) break;
    const next = targetOf(a, t);
    const u = easeInOut(Math.min(1, (t - a.at) / Math.max(0.01, a.dur ?? 0.8)));
    cur = { x: cur.x + (next.x - cur.x) * u, y: cur.y + (next.y - cur.y) * u, zoom: cur.zoom + (next.zoom - cur.zoom) * u };
  }
  // punch + shake from the latest break
  const last = [...w.breaks.values()].filter((b) => b.at <= t).sort((a, b) => a.at - b.at).pop();
  const since = last ? t - last.at : 99;
  const punch = 1 + 0.06 * Math.exp(-since * 5) * (since < 2 ? 1 : 0);
  const shake = since < 0.6 ? 16 * Math.exp(-since * 7) : 0;
  return { ...cur, zoom: cur.zoom * punch, sx: shake * Math.sin(since * 70), sy: shake * Math.cos(since * 53) };
};

export const rnd = (i: number) => {
  const v = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return v - Math.floor(v);
};
