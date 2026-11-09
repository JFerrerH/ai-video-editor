import React from "react";
import { interpolate } from "remotion";
import { FIT_WRAP, accentOn, fitSize, useBrand } from "../../theme";
import { clamp, inOut, ramp } from "../fx";

/** What identifies a recurring document and how far its fill got. */
export type DocProps = {
  kicker: string;
  title: string;
  italic?: string;
  fillAt?: number;
  fillDur?: number;
  fillFrom?: number;
  fillTo?: number;
  fillColor?: string;
};

/** A document-like object that can come back later in the story (the fill shows how far it got). */
export const Doc: React.FC<{ p: DocProps; t: number; w?: number }> = ({ p, t, w = 640 }) => {
  const { colors, fonts } = useBrand();
  const inner = w - 76; // the padding on each side
  // long text shrinks to fit the card's width before it wraps (theme fitSize), so the card stays short
  const kickerSize = fitSize(p.kicker, { fontFamily: fonts.mono, fontWeight: 700, letterSpacing: "2px", max: 36, width: inner });
  const titleSize = fitSize(`${p.title} ${p.italic ?? ""}`.trim(), { fontFamily: fonts.serif, max: 50, width: inner });
  const from = p.fillFrom ?? 0;
  const fill = p.fillAt != null ? interpolate(ramp(t, p.fillAt, p.fillDur ?? 0.6, inOut), [0, 1], [from, p.fillTo ?? 0], clamp) : from;
  return (
    <div style={{ width: w, background: "#fff", borderRadius: 22, padding: "30px 38px 36px", boxShadow: "0 22px 50px rgba(31,35,40,.25)", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, width: `${fill * 100}%`, background: p.fillColor ?? colors.tint1 }} />
      <div style={{ position: "relative" }}>
        <div style={{ fontFamily: fonts.mono, fontSize: kickerSize, fontWeight: 700, letterSpacing: 2, color: colors.ink, ...FIT_WRAP }}>{p.kicker}</div>
        <div style={{ fontFamily: fonts.serif, fontSize: titleSize, lineHeight: 1.08, color: colors.ink, marginTop: 12, ...FIT_WRAP }}>
          {p.title} {p.italic ? <i>{p.italic}</i> : null}
        </div>
        {[0.9, 0.75, 0.82].map((k, i) => (
          <div key={i} style={{ height: 10, width: `${k * 100}%`, background: "#E6E3DD", borderRadius: 5, marginTop: i ? 12 : 26 }} />
        ))}
      </div>
      {fill > 0.03 ? (
        <div style={{ position: "absolute", right: 30, top: 22, fontFamily: fonts.sans, fontWeight: 600, fontSize: 50, color: accentOn(colors, fill > 0.5 ? p.fillColor ?? colors.tint1 : "#FFFFFF", 4.5) }}>
          {Math.round(fill * 100)}%
        </div>
      ) : null}
    </div>
  );
};
