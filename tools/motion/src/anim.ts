import { Easing, interpolate, spring } from "remotion";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

/** 0→1 spring entrance starting at `delay` frames. */
export const enter = (frame: number, fps: number, delay = 0, damping = 16) =>
  spring({ frame: frame - delay, fps, config: { damping, stiffness: 170, mass: 0.8 } });

/** 1→0 over the last `len` frames of a sequence. */
export const exit = (frame: number, duration: number, len = 7) =>
  interpolate(frame, [duration - len, duration], [1, 0], { ...clamp, easing: Easing.in(Easing.cubic) });

export const sec = (s: number, fps: number) => Math.round(s * fps);
