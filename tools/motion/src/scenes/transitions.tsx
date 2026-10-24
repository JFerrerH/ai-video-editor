import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { linearTiming, TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import { fade } from "@remotion/transitions/fade";
import { flip } from "@remotion/transitions/flip";
import { iris } from "@remotion/transitions/iris";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { easeInOut } from "../anim";

export type TransitionType = "cut" | "fade" | "slide" | "wipe" | "flip" | "iris" | "clockWipe" | "zoom";
export type TransitionSpec = { type: TransitionType; duration?: number; direction?: string };

/** Zoom-through: the outgoing scene pushes past the camera while the next settles in from
 *  slightly larger (never smaller than the frame, so no scene edge ever shows). */
const ZoomThrough: React.FC<TransitionPresentationComponentProps<Record<string, never>>> = ({
  children,
  presentationDirection,
  presentationProgress: p,
}) => {
  const entering = presentationDirection === "entering";
  return (
    <AbsoluteFill
      style={{
        opacity: entering ? interpolate(p, [0, 0.6], [0, 1], { extrapolateRight: "clamp" }) : interpolate(p, [0.4, 1], [1, 0], { extrapolateLeft: "clamp" }),
        scale: String(entering ? interpolate(p, [0, 1], [1.12, 1]) : interpolate(p, [0, 1], [1, 1.18])),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
const zoom = (): TransitionPresentation<Record<string, never>> => ({ component: ZoomThrough, props: {} });

/** Default length (s) per transition: quick ones feel snappy, shape wipes need a beat longer. */
export const DEFAULT_TRANSITION_S: Record<TransitionType, number> = {
  cut: 0,
  fade: 0.4,
  slide: 0.45,
  wipe: 0.5,
  flip: 0.6,
  iris: 0.6,
  clockWipe: 0.7,
  zoom: 0.45,
};

export const transitionFrames = (t: TransitionSpec | undefined, fps: number) =>
  !t || t.type === "cut" ? 0 : Math.round((t.duration ?? DEFAULT_TRANSITION_S[t.type]) * fps);

export const makeTransition = (t: TransitionSpec, fps: number, width: number, height: number) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- direction strings come from storyboard JSON
  const dir = (t.direction ?? "from-right") as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- each presentation has its own props type
  const presentation: TransitionPresentation<any> =
    t.type === "fade"
      ? fade()
      : t.type === "slide"
        ? slide({ direction: dir })
        : t.type === "wipe"
          ? wipe({ direction: dir })
          : t.type === "flip"
            ? flip({ direction: dir })
            : t.type === "iris"
              ? iris({ width, height })
              : t.type === "clockWipe"
                ? clockWipe({ width, height })
                : t.type === "zoom"
                  ? zoom()
                  : (() => {
                      throw new Error(`Unknown transition: ${t.type}`);
                    })();
  return { presentation, timing: linearTiming({ durationInFrames: transitionFrames(t, fps), easing: easeInOut }) };
};
