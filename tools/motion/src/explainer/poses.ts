/**
 * Pose library for the explainer figure: one joint-angle table per pose.
 *
 * Angles are degrees in screen space, 0 = straight down, +90 = towards the figure's front (screen
 * right when facing right), 180 = straight up. Shoulders and hips are absolute; elbows and knees are
 * relative to their upper segment. The rig keeps the lowest foot on the ground, so bent knees
 * lower the body. `lean` tilts the spine (+ = forwards), `head` tilts the head,
 * `lift` raises the shoulders (a shrug), `look` drops
 * the head towards the chest.
 * "b" = the back arm/leg (screen left when facing right), "f" = the front one.
 */
export type Pose = {
  lean: number;
  head: number;
  bS: number;
  bE: number;
  fS: number;
  fE: number;
  bH: number;
  bK: number;
  fH: number;
  fK: number;
  lift: number;
  look: number;
};

export type PropName = "desk" | "megaphone" | "box";

const P = (p: Partial<Pose>): Pose => ({
  lean: 0, head: 0, bS: -10, bE: 3, fS: 10, fE: -3, bH: -5, bK: 0, fH: 5, fK: 0, lift: 0, look: 0,
  ...p,
});

export const POSES = {
  stand: P({}),
  wave: P({ fS: 112, fE: 62, head: 6 }),
  cheer: P({ bS: -132, bE: -18, fS: 132, fE: 18, head: -6, bH: -9, fH: 9, lift: 4 }),
  point: P({ fS: 96, fE: -4, bS: -14, lean: 4, head: 6 }),
  shrug: P({ bS: -38, bE: -88, fS: 38, fE: 88, head: 12, lift: 12 }),
  slump: P({ bS: -2, bE: 0, fS: 4, fE: 0, lean: 9, head: 22, look: 18, bH: -3, fH: 3, lift: -8 }),
  think: P({ fS: 62, fE: 142, bS: 40, bE: 72, head: -12 }),
  type: P({ bS: 18, bE: 58, fS: 38, fE: 48, lean: 8, head: 10, look: 6 }),
  push: P({ bS: 70, bE: 16, fS: 82, fE: 8, lean: 16, bH: -26, bK: 6, fH: 12, fK: -10 }),
  shout: P({ fS: 75, fE: 105, bS: -40, bE: 80, lean: -8, head: -12, bH: -8, fH: 8 }),
} satisfies Record<string, Pose>;

export type PoseName = keyof typeof POSES;
export const POSE_NAMES = Object.keys(POSES) as PoseName[];

/** The prop a pose brings with it unless the pose entry says otherwise. */
export const POSE_PROP: Partial<Record<PoseName, PropName>> = { type: "desk", push: "box", shout: "megaphone" };
export const PROP_NAMES: PropName[] = ["desk", "megaphone", "box"];

export const lerpPose = (a: Pose, b: Pose, t: number): Pose => {
  const out = {} as Pose;
  for (const k of Object.keys(a) as (keyof Pose)[]) out[k] = a[k] + (b[k] - a[k]) * t;
  return out;
};
