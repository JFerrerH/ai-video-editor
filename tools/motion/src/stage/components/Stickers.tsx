import React from "react";
import { useBrand } from "../../theme";
import { popAt, ramp, useEventTime } from "../fx";

type Item = { text: string; at: number; x: number; y: number; rot?: number; size?: number };

/** Key words pop in as stickers, each on its own spoken beat. */
export const Stickers: React.FC<{ durationInFrames: number; items: Item[] }> = ({ durationInFrames, items }) => {
  const { colors, fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const o = 1 - ramp(t, d - 0.2, 0.2);
  return (
    <>
      {items.map((s, i) => {
        const k = popAt(t, s.at);
        if (k <= 0) return null;
        return (
          <div
            key={i}
            style={{
              position: "absolute", left: s.x, top: s.y, transform: `rotate(${s.rot ?? 0}deg) scale(${0.6 + 0.4 * k})`,
              opacity: Math.min(1, k * 2) * o, background: colors.ink, color: colors.bg, padding: "14px 34px 20px", borderRadius: 26,
              fontFamily: fonts.serif, fontStyle: "italic", fontSize: s.size ?? 84, boxShadow: "0 18px 40px rgba(0,0,0,.35)", whiteSpace: "nowrap",
            }}
          >
            {s.text}
          </div>
        );
      })}
    </>
  );
};
