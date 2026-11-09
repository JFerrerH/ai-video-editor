import React from "react";
import { AbsoluteFill, Easing } from "remotion";
import { Doc, type DocProps } from "./Doc";
import { ramp, span, useEventTime } from "../fx";
import { SAFE } from "../../theme";

/** A card falls into a drawer at the bottom of the frame, which shuts at `shutAt`. The card rests with its bottom
 *  edge REST px above the safe text limit and grows upward with its text, so no title length or font takes its text
 *  below the limit; it enters and drops by moving, not by its anchor. */
const CLIP = 1600; // the drawer's mouth: the card is cut off below it as it drops in
const REST = 16;

export const StageDrawer: React.FC<{ durationInFrames: number; card: DocProps; dropAt: number; shutAt: number }> = ({ durationInFrames, card, dropAt, shutAt }) => {
  const { t, d } = useEventTime(durationInFrames);
  const vis = span(t, 0, d, 0.45, 0.35);
  const cardIn = ramp(t, 0.15, 0.5);
  const drop = ramp(t, dropAt, 0.45, Easing.in(Easing.quad));
  const shut = ramp(t, shutAt - 0.16, 0.16, Easing.in(Easing.cubic));
  const th = t > shutAt ? Math.sin((t - shutAt) * 40) * 6 * Math.exp(-(t - shutAt) * 9) : 0;
  return (
    <AbsoluteFill style={{ opacity: vis, transform: `translateY(${(1 - vis) * 120}px)` }}>
      <div style={{ position: "absolute", left: 160, top: 1560 + th, width: 760, height: 300, background: "#2B2F35", borderRadius: 18 }} />
      <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: CLIP + th, overflow: "hidden" }}>
        <div
          style={{
            position: "absolute",
            left: 220,
            bottom: CLIP - (SAFE.textBottom - REST),
            opacity: cardIn,
            transform: `translateY(${(1 - cardIn) * 80 + drop * 420}px) rotate(${-2 + drop * 4}deg)`,
          }}
        >
          <Doc p={card} t={t} />
        </div>
      </div>
      <div style={{ position: "absolute", left: 130, top: 1660 - 110 * shut + th, width: 820, height: 210, background: "#3A3F46", borderRadius: 18, boxShadow: "0 -6px 24px rgba(0,0,0,.25)" }}>
        <div style={{ position: "absolute", left: 330, top: 92, width: 160, height: 22, background: "#8A9099", borderRadius: 11 }} />
      </div>
    </AbsoluteFill>
  );
};
