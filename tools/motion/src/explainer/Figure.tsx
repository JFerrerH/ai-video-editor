import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp } from "../anim";
import { BgKind, usePalette } from "../scenes/Bg";
import { useBrand } from "../theme";
import { lerpPose, Pose, POSE_PROP, PoseName, POSES, PropName } from "./poses";
import { Rect } from "./slots";

export type PoseCue = { pose: PoseName; at?: number; prop?: PropName | null };
export type FigureSpec = {
  pose?: PoseName; // a single held pose
  poses?: PoseCue[]; // or a list with start times (s from the scene start; cues resolved by the engine)
  facing?: "left" | "right";
  slot?: string;
  scale?: number;
  phase?: number; // idle-motion phase (s), so figures in consecutive beats don't sway in lockstep
};

// segment lengths in rig units; the whole figure is ~540 units from shoe to cap
const L = { thigh: 112, shin: 108, spine: 150, neck: 24, headR: 44, upper: 92, fore: 88 };
const RIG_H = 540;
const FLOOR = 26; // rig units kept under the feet, so the ground shadow stays inside the box
const STROKE = 11;
const BLEND_S = 0.4; // a pose change settles within this
const IDLE_S = 2.4; // period of the idle sway and breath

const rad = (d: number) => (d * Math.PI) / 180;
/** Unit vector for a screen angle: 0 = down, +90 = front (+x), 180 = up. */
const dir = (a: number): [number, number] => [Math.sin(rad(a)), Math.cos(rad(a))];
const add = (p: [number, number], a: number, len: number): [number, number] => {
  const [dx, dy] = dir(a);
  return [p[0] + dx * len, p[1] + dy * len];
};

/** Joint positions for a pose (rig units, feet on y = 0, x = 0 between the hips). */
export const rig = (p: Pose, breath = 0) => {
  const hip: [number, number] = [0, 0];
  const legs = (["b", "f"] as const).map((s) => {
    const knee = add(hip, p[`${s}H`], L.thigh);
    return { knee, foot: add(knee, p[`${s}H`] + p[`${s}K`], L.shin) };
  });
  const floor = Math.max(legs[0].foot[1], legs[1].foot[1]);
  const shift = (q: [number, number]): [number, number] => [q[0], q[1] - floor];
  const top = add(hip, 180 - p.lean, L.spine + breath); // spine tilts forwards with +lean
  const shoulder = add(top, 180 - p.lean, p.lift - 12); // a little under the neck; `lift` raises it
  const arms = (["b", "f"] as const).map((s) => {
    // arm angles are absolute (they hang, whatever the spine does)
    const elbow = add(shoulder, p[`${s}S`], L.upper);
    return { elbow, hand: add(elbow, p[`${s}S`] + p[`${s}E`], L.fore) };
  });
  const head = add(top, 180 - p.lean - p.head, L.neck + L.headR - p.look);
  return {
    hip: shift(hip),
    top: shift(top),
    shoulder: shift(shoulder),
    head: shift(head),
    headTilt: p.lean + p.head,
    legs: legs.map((l) => ({ knee: shift(l.knee), foot: shift(l.foot) })),
    arms: arms.map((a) => ({ elbow: shift(a.elbow), hand: shift(a.hand) })),
  };
};

/** Pose at `frame`: each cue springs from wherever the figure is towards its pose. */
const poseAt = (cues: PoseCue[], frame: number, fps: number) => {
  let v: Pose = POSES[cues[0].pose];
  let cur = 0;
  let p = 1;
  for (let k = 1; k < cues.length; k++) {
    const f = Math.round((cues[k].at ?? 0) * fps);
    if (frame < f) break;
    p = spring({ frame: frame - f, fps, config: { damping: 15, stiffness: 160, mass: 0.7 }, durationInFrames: Math.round(BLEND_S * fps) });
    v = lerpPose(v, POSES[cues[k].pose], p);
    cur = k;
  }
  return { pose: v, cur, p };
};

const pt = (q: [number, number]) => `${q[0].toFixed(1)},${q[1].toFixed(1)}`;

/**
 * The explainer character: a neutral vector stick figure posed from a joint-angle table. Pose
 * changes spring in (≤ 0.4 s); a slow sway and breath keep it alive while a pose holds. Cap and
 * shoes take the brand accent. Fits its `box` (feet on the box's bottom edge), mirrored for
 * `facing: "left"`.
 */
export const Figure: React.FC<FigureSpec & { box: Rect; bg?: BgKind }> = ({ pose, poses, facing = "right", scale = 1, phase = 0, box, bg }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors } = useBrand();
  const pal = usePalette(bg);
  const cues: PoseCue[] = poses?.length ? [...poses].sort((a, b) => (a.at ?? 0) - (b.at ?? 0)) : [{ pose: pose ?? "stand" }];
  const { pose: base, cur, p } = poseAt(cues, frame, fps);
  const t = frame / fps + phase;
  const wave = Math.sin((2 * Math.PI * t) / IDLE_S);
  const pz: Pose = { ...base, lean: base.lean + 1.5 * wave };
  if (cues[cur].pose === "wave") pz.fE += 16 * Math.sin(2 * Math.PI * t * 1.7) * p; // the hand waves
  const r = rig(pz, 2 * Math.sin((2 * Math.PI * t) / IDLE_S + Math.PI / 2));
  const prop = cues[cur].prop !== undefined ? cues[cur].prop : (POSE_PROP[cues[cur].pose] ?? null);
  const propIn = interpolate(p, [0.3, 1], [0, 1], clamp);

  const k = (box.h * 0.94 * scale) / (RIG_H + FLOOR);
  // centre figure + prop in the box, from the pose without idle motion (so the sway doesn't slide it)
  const still = rig(base);
  const xs = [still.head[0] - L.headR, still.head[0] + L.headR + 30, ...still.arms.map((a) => a.hand[0]), ...still.legs.map((l) => l.foot[0] + 32)];
  if (prop === "box") xs.push((Math.max(still.arms[0].hand[0], still.arms[1].hand[0]) + 190) * propIn);
  if (prop === "desk") xs.push(-150 * propIn, 210 * propIn);
  if (prop === "megaphone") xs.push((still.head[0] + L.headR + 80) * propIn);
  const cx = -(Math.min(...xs) + Math.max(...xs)) / 2;
  const ink = pal.fg;
  const dark = bg === "dark";
  const line = { stroke: ink, strokeWidth: STROKE, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill: "none" };
  const limb = (a: [number, number], b: [number, number], c: [number, number]) => <polyline points={`${pt(a)} ${pt(b)} ${pt(c)}`} {...line} />;
  const [bArm, fArm] = r.arms;

  const propEl = (() => {
    if (!prop || propIn <= 0) return null;
    const s = { opacity: propIn, transform: `scale(${interpolate(propIn, [0, 1], [0.85, 1])})`, transformBox: "fill-box" as const, transformOrigin: "50% 100%" };
    if (prop === "desk") {
      const y = -250;
      return (
        <g style={s}>
          <rect x={-40} y={y - 128} width={190} height={124} rx={10} fill={ink} />
          <circle cx={55} cy={y - 66} r={9} fill={colors.accent} />
          <rect x={-70} y={y - 6} width={250} height={14} rx={4} fill={ink} />
          <line x1={-150} y1={y} x2={210} y2={y} {...line} />
          <line x1={-130} y1={y} x2={-130} y2={0} {...line} />
          <line x1={190} y1={y} x2={190} y2={0} {...line} />
        </g>
      );
    }
    if (prop === "megaphone") {
      // held at the mouth, the bell pointing forwards (tilted with the head)
      const [dx, dy] = dir(90 - r.headTilt * 0.6);
      const [nx, ny] = [-dy, dx];
      const mouth: [number, number] = [r.head[0] + L.headR - 6, r.head[1] + 16];
      const at = (u: number, v: number): [number, number] => [mouth[0] + dx * u + nx * v, mouth[1] + dy * u + ny * v];
      return (
        <g style={s}>
          <polygon points={[at(0, -12), at(84, -40), at(84, 40), at(0, 12)].map(pt).join(" ")} fill={ink} stroke={ink} strokeWidth={6} strokeLinejoin="round" />
          <polyline points={[at(84, -40), at(84, 40)].map(pt).join(" ")} stroke={colors.accent} strokeWidth={10} strokeLinecap="round" />
        </g>
      );
    }
    const x0 = Math.max(bArm.hand[0], fArm.hand[0]) + STROKE / 2;
    const top = Math.min(bArm.hand[1], fArm.hand[1]) - 36;
    const w = 180;
    return (
      <g style={s}>
        <rect x={x0} y={top} width={w} height={-top} rx={8} fill={dark ? "rgba(255,255,255,0.06)" : colors.bg} stroke={ink} strokeWidth={STROKE} strokeLinejoin="round" />
        <line x1={x0 + w / 2} y1={top} x2={x0 + w / 2} y2={top + 70} stroke={colors.accent} strokeWidth={12} />
        <line x1={x0 + 26} y1={top + 26} x2={x0 + w - 26} y2={top + 26} stroke={ink} strokeWidth={5} strokeLinecap="round" opacity={0.35} />
      </g>
    );
  })();

  const [hx, hy] = r.head;
  return (
    <svg
      style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, overflow: "visible" }}
      viewBox={`${-box.w / 2 / k} ${FLOOR - box.h / k} ${box.w / k} ${box.h / k}`}
    >
      <g transform={`${facing === "left" ? "scale(-1,1) " : ""}translate(${cx.toFixed(1)},0)`}>
        <ellipse cx={r.hip[0] + 10} cy={6} rx={120} ry={15} fill={dark ? "rgba(0,0,0,0.45)" : "rgba(20,20,10,0.10)"} />
        {prop === "box" ? propEl : null}
        {/* legs, shoes */}
        {r.legs.map((l, i) => (
          <g key={i}>
            {limb(r.hip, l.knee, l.foot)}
            <rect x={l.foot[0] - 14} y={l.foot[1] - 15} width={46} height={20} rx={10} fill={colors.accent} />
          </g>
        ))}
        {/* back arm behind the body, spine, front arm */}
        {limb(r.shoulder, bArm.elbow, bArm.hand)}
        <polyline points={`${pt(r.hip)} ${pt(r.top)} ${pt(r.head)}`} {...line} strokeWidth={STROKE + 3} />
        {limb(r.shoulder, fArm.elbow, fArm.hand)}
        {prop === "desk" ? propEl : null}
        {prop === "megaphone" ? propEl : null}
        {/* head: solid, an eye towards the front, an accent cap with its brim forwards */}
        <g transform={`translate(${hx.toFixed(1)},${hy.toFixed(1)}) rotate(${(r.headTilt * 0.6).toFixed(2)})`}>
          <circle r={L.headR} fill={ink} />
          <circle cx={20} cy={4} r={5.5} fill={dark ? colors.ink : colors.bg} />
          <path d={`M ${-L.headR - 3} -8 A ${L.headR + 3} ${L.headR + 3} 0 0 1 ${L.headR + 3} -8 Z`} fill={colors.accent} />
          <rect x={L.headR - 14} y={-16} width={44} height={11} rx={5.5} fill={colors.accent} />
        </g>
      </g>
    </svg>
  );
};
