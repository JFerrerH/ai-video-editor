import React from "react";
import { AbsoluteFill } from "remotion";
import { useBrand } from "../../theme";
import { inOut, ramp, span, useEventTime } from "../fx";

/** A large word rising behind the head, optionally struck through. Draw it on the `behind` layer. */
export const BehindWord: React.FC<{
  durationInFrames: number;
  word: string;
  lead?: string;
  riseAt?: number;
  strikeAt?: number;
  y?: number;
  size?: number;
  color?: string;
}> = ({ durationInFrames, word, lead, riseAt = 0, strikeAt, y = 640, size = 196, color }) => {
  const { colors, fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const vis = span(t, 0, d, 0.3, 0.25);
  const rise = ramp(t, riseAt, 0.4);
  const strike = strikeAt != null ? ramp(t, strikeAt, 0.3, inOut) : 0;
  return (
    <AbsoluteFill style={{ opacity: vis }}>
      {lead ? (
        <div style={{ position: "absolute", top: y - 80, width: "100%", textAlign: "center", fontFamily: fonts.mono, fontWeight: 700, fontSize: 48, letterSpacing: 6, color: color ?? colors.tint1, textTransform: "uppercase" }}>
          {lead}
        </div>
      ) : null}
      <div style={{ position: "absolute", top: y, width: "100%", textAlign: "center", overflow: "hidden", height: 260 }}>
        <div style={{ transform: `translateY(${(1 - rise) * 100}%)`, fontFamily: fonts.serif, fontWeight: 600, fontSize: size, color: color ?? colors.bg, letterSpacing: -4, lineHeight: "240px", textShadow: "0 8px 40px rgba(0,0,0,.25)" }}>
          {word}
        </div>
        {strike > 0 ? <div style={{ position: "absolute", left: 70, top: 128, height: 14, width: 940 * strike, background: colors.accent, borderRadius: 7 }} /> : null}
      </div>
    </AbsoluteFill>
  );
};
