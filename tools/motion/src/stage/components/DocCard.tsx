import React from "react";
import { Easing } from "remotion";
import { textOn, useBrand } from "../../theme";
import { Doc, type DocProps } from "./Doc";
import { popAt, ramp, useEventTime } from "../fx";

/** A story object that can come back: its fill shows how far it got. Events sharing `object` keep one identity. */
export const DocCard: React.FC<DocProps & {
  durationInFrames: number;
  tag?: string;
  tagAt?: number;
  pulseAt?: number;
  x?: number;
  y?: number;
  rot?: number;
}> = ({ durationInFrames, tag, tagAt, pulseAt, x = 220, y = 210, rot = -2, ...doc }) => {
  const { colors, fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const s = popAt(t, 0, 13);
  const out = ramp(t, d - 0.3, 0.3, Easing.in(Easing.cubic));
  const pulse = pulseAt != null && t > pulseAt ? 1 + 0.05 * Math.exp(-(t - pulseAt) * 6) : 1;
  const tagIn = tagAt != null ? ramp(t, tagAt, 0.3) : 0;
  return (
    <div style={{ position: "absolute", left: x, top: y, opacity: Math.min(1, s * 2) * (1 - out), transform: `scale(${(0.8 + 0.2 * s) * pulse}) rotate(${rot}deg)` }}>
      {tag ? (
        <div style={{ fontFamily: fonts.sans, fontWeight: 600, fontSize: 34, color: textOn(colors.accent, colors.ink), background: colors.accent, display: "inline-block", padding: "8px 20px", borderRadius: 12, marginBottom: 14, opacity: tagIn, transform: `translateY(${(1 - tagIn) * 16}px)` }}>
          {tag}
        </div>
      ) : null}
      <Doc p={doc} t={t} />
    </div>
  );
};
