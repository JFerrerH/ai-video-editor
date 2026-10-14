import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";
import { IconKind, LineIcon } from "./icons";

type Slot = { icon: IconKind; at?: number }; // `at` (s): the icon fills the slot; omitted = stays empty

/** Numbered slots ("01", "02"…) floating above the head; each fills with a line icon on cue.
 *  `active` highlights one slot (ink) — reuse the same card across the video as a progress tracker. */
export const SkillSlots: React.FC<{ durationInFrames: number; slots: Slot[]; active?: number; top?: number }> = ({
  durationInFrames,
  slots,
  active,
  top = SAFE.top + 20,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const s = enter(frame, fps, 0, 14);
  const out = exit(frame, durationInFrames, 6);
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: out }}>
      <div
        style={{
          position: "absolute",
          top,
          display: "flex",
          gap: 34,
          opacity: Math.min(1, s * 1.5),
          translate: `0px ${interpolate(s, [0, 1], [-60, 0])}px`,
        }}
      >
        {slots.map((sl, i) => {
          const f0 = sl.at != null ? sec(sl.at, fps) : Infinity;
          const filled = frame >= f0;
          const k = filled ? enter(frame, fps, f0, 11) : 0;
          const on = active === i && filled;
          return (
            <div
              key={i}
              style={{
                width: 230,
                height: 250,
                borderRadius: 30,
                boxSizing: "border-box",
                background: on ? colors.ink : filled ? "white" : "rgba(255,255,255,0.82)",
                border: filled ? "none" : `3px dashed ${colors.muted}`,
                boxShadow: filled ? "0 22px 50px rgba(31,35,40,0.25)" : "none",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 14,
                scale: String(filled ? interpolate(k, [0, 1], [0.85, 1]) : 1),
                rotate: `${(i % 2 ? 1 : -1) * 2}deg`,
              }}
            >
              <div style={{ fontFamily: fonts.serif, fontStyle: "italic", fontSize: 44, color: on ? colors.tint1 : colors.muted }}>
                {String(i + 1).padStart(2, "0")}
              </div>
              <div style={{ opacity: filled ? k : 0, scale: String(interpolate(k, [0, 1], [0.4, 1])) }}>
                <LineIcon kind={sl.icon} size={104} color={on ? colors.bg : colors.ink} stroke={1.6} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
