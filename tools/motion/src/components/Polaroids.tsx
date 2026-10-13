import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, enter, exit, sec } from "../anim";
import { SAFE, useBrand } from "../theme";

type Photo = { src: string; label: string; at: number; rotate?: number };

/** Polaroid photos drop in one by one (with a camera-flash), plus an optional chip. */
export const Polaroids: React.FC<{
  durationInFrames: number;
  photos: Photo[];
  chip?: string;
  chipAt?: number;
}> = ({ durationInFrames, photos, chip, chipAt = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { colors, fonts } = useBrand();
  const out = exit(frame, durationInFrames, 6);
  const chipIn = enter(frame, fps, sec(chipAt, fps), 12);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{ position: "absolute", top: SAFE.top + 20, width: "100%", display: "flex", justifyContent: "center", gap: 30 }}>
        {photos.map((p, i) => {
          const s = enter(frame, fps, sec(p.at, fps), 13);
          const flash = interpolate(frame - sec(p.at, fps), [0, 2, 8], [0, 1, 0], clamp);
          if (frame < sec(p.at, fps)) return <div key={i} style={{ width: 330 }} />;
          return (
            <div
              key={i}
              style={{
                width: 330,
                background: "white",
                padding: "18px 18px 22px",
                borderRadius: 6,
                boxShadow: "0 24px 50px rgba(0,0,0,0.35)",
                rotate: `${interpolate(s, [0, 1], [(p.rotate ?? 0) * 3, p.rotate ?? 0])}deg`,
                translate: `0px ${interpolate(s, [0, 1], [-300, 0])}px`,
                scale: interpolate(s, [0, 1], [1.3, 1]),
                opacity: Math.min(1, s * 2),
                position: "relative",
              }}
            >
              <Img src={staticFile(p.src)} style={{ width: 294, height: 330, objectFit: "cover", display: "block" }} />
              <div style={{ position: "absolute", left: 18, top: 18, width: 294, height: 330, background: "white", opacity: flash }} />
              <div style={{ fontFamily: fonts.serif, fontStyle: "italic", fontSize: 40, color: colors.ink, textAlign: "center", marginTop: 12 }}>
                {p.label}
              </div>
            </div>
          );
        })}
      </div>
      {chip ? (
        <div style={{ position: "absolute", top: SAFE.top + 470, width: "100%", display: "flex", justifyContent: "center" }}>
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: 30,
              letterSpacing: 4,
              color: colors.bg,
              background: colors.ink,
              padding: "12px 28px",
              borderRadius: 999,
              opacity: frame >= sec(chipAt, fps) ? Math.min(1, chipIn * 1.5) : 0,
              scale: interpolate(chipIn, [0, 1], [0.6, 1]),
            }}
          >
            {chip}
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
