import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, easeOut } from "../anim";

export { clamp };
export const ease = easeOut;
export const inOut = easeInOut;

/** 0→1 over `len` s from `a` (clamped), eased. */
export const ramp = (t: number, a: number, len = 0.35, e: (x: number) => number = ease) =>
  interpolate(t, [a, a + len], [0, 1], { ...clamp, easing: e });

/** 1 while on screen between `a` and `b`, easing in over `inLen` and out over `outLen`. */
export const span = (t: number, a: number, b: number, inLen = 0.35, outLen = 0.25) =>
  Math.min(ramp(t, a, inLen), 1 - ramp(t, b - outLen, outLen, Easing.in(Easing.cubic)));

/** A spring that pops 0→1 at `at` seconds (0 before it). */
export const popAt = (t: number, at: number, damping = 11) =>
  t < at ? 0 : spring({ frame: (t - at) * 30, fps: 30, config: { damping, stiffness: 180, mass: 0.7 } });

/** Seconds since the event started, and the event's length in seconds. Stage components are drawn inside a
 *  `Sequence` (see OverlayLayer), so the frame is relative to the event's start, like every overlay component. */
export const useEventTime = (durationInFrames: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { t: frame / fps, d: durationInFrames / fps };
};
