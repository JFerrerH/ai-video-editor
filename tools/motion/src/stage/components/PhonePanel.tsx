import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile } from "remotion";
import { clamp, inOut, ramp, span, useEventTime } from "../fx";

/** Real screens in a phone; the screen changes on cue. `corner`: the hero while a corner move is on (layer
 *  `panel`); `side`: beside a side move, on the free wall. */
export const PhonePanel: React.FC<{
  durationInFrames: number;
  mode: "corner" | "side";
  screens: { src: string; at: number }[];
  scroll?: number;
}> = ({ durationInFrames, mode, screens, scroll }) => {
  const { t, d } = useEventTime(durationInFrames);
  const vis = span(t, 0, d, 0.45, 0.35);
  const corner = mode === "corner";
  const W = corner ? 520 : 380;
  const H = W * 2.164;
  const top = corner ? 200 : 470;
  const left = corner ? (1080 - W) / 2 - 130 : 650 + (1 - vis) * 420;
  const bob = corner ? 0 : Math.sin(t * 1.6) * 8;
  const cur = screens.reduce((k, s, i) => (t >= s.at ? i : k), 0);
  const slide = ramp(t, screens[cur].at, 0.45, inOut);
  const scrollY = scroll ? interpolate(t, [0, d], [0, -scroll], clamp) : 0;
  return (
    <AbsoluteFill style={{ opacity: vis }}>
      <div style={{ position: "absolute", left, top: top + bob + (corner ? (1 - vis) * 140 : 0), width: W, height: H, borderRadius: 64, background: "#111", padding: 14, boxShadow: "0 30px 70px rgba(31,35,40,.35)", transform: `rotate(${corner ? -3 : 4}deg)` }}>
        <div style={{ width: "100%", height: "100%", borderRadius: 52, overflow: "hidden", position: "relative", background: "#fff" }}>
          {screens.map((s, i) =>
            i === cur || i === cur - 1 ? (
              <Img
                key={i}
                src={staticFile(s.src)}
                style={{ position: "absolute", width: "100%", top: scrollY, transform: `translateX(${i === cur ? (cur === 0 ? 0 : (1 - slide) * 100) : -slide * 30}%)`, opacity: i === cur ? 1 : 1 - slide * 0.5 }}
              />
            ) : null,
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
