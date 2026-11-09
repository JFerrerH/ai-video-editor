import React from "react";
import { Easing } from "remotion";
import { useBrand } from "../../theme";
import { popAt, ramp, useEventTime } from "../fx";

/** A phone notification quoting what the speaker reports. `when` is the small time label on the right. */
export const Notice: React.FC<{ durationInFrames: number; from: string; text: string; when?: string }> = ({ durationInFrames, from, text, when }) => {
  const { fonts } = useBrand();
  const { t, d } = useEventTime(durationInFrames);
  const s = popAt(t, 0, 14);
  const out = ramp(t, d - 0.3, 0.3, Easing.in(Easing.cubic));
  return (
    // inside the safe sides and just under the top limit (shortform PLACE_TOP), where the engine needn't move or shrink it
    <div style={{ position: "absolute", left: 130, top: 110 + (1 - s) * -220 - out * 260, width: 820, padding: "26px 30px", borderRadius: 40, background: "rgba(245,245,245,.94)", boxShadow: "0 16px 40px rgba(0,0,0,.28)", display: "flex", gap: 26, alignItems: "center" }}>
      <div style={{ width: 92, height: 92, borderRadius: 22, background: "#34C759", display: "grid", placeItems: "center", color: "#fff", fontFamily: fonts.sans, fontSize: 52, fontWeight: 600 }}>✉</div>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: fonts.sans, fontSize: 34, fontWeight: 600, color: "#111" }}>
          <span>{from}</span>
          {when ? <span style={{ fontWeight: 400, color: "#5E5E5E", fontSize: 30 }}>{when}</span> : null}
        </div>
        <div style={{ fontFamily: fonts.sans, fontSize: 34, color: "#222", marginTop: 4 }}>{text}</div>
      </div>
    </div>
  );
};
