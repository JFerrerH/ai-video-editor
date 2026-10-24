import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut } from "../anim";
import { useFrameLayout } from "../layout";
import { useBrand } from "../theme";
import { BgKind, usePalette } from "./Bg";
import { RevealLine } from "./text";

const KICKER_GAP = 14;
const TITLE_GAP = 28; // under the header, before the diagram

/** Sizes of the optional kicker/title at the top of a diagram scene (NetworkScene, IsoOffice). */
export const useHeaderSize = (kicker?: string, title?: string) => {
  const { aspect, innerW } = useFrameLayout();
  const kickerFs = aspect === "16:9" ? 28 : 32;
  const titleFs = aspect === "16:9" ? 62 : aspect === "9:16" ? 76 : 68;
  // wrapped line count from an average glyph width of ~0.48 em (serif)
  const lines = title ? title.split("\n").reduce((n, l) => n + Math.max(1, Math.ceil((l.length * titleFs * 0.48) / innerW)), 0) : 0;
  const height =
    (kicker ? kickerFs * 1.2 + (title ? KICKER_GAP : 0) : 0) + (title ? lines * titleFs * 1.08 : 0) + (kicker || title ? TITLE_GAP : 0);
  return { kickerFs, titleFs, height };
};

/** Kicker (small caps, accent) over a serif title whose words rise in; drawn at the top of the safe box. */
export const SceneHeader: React.FC<{ bg?: BgKind; kicker?: string; title?: string; emphasis?: string }> = ({ bg, kicker, title, emphasis }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fonts } = useBrand();
  const pal = usePalette(bg);
  const { safe, aspect } = useFrameLayout();
  const { kickerFs, titleFs } = useHeaderSize(kicker, title);
  if (!kicker && !title) return null;
  const k = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: easeOut });
  const al = aspect === "16:9" ? "left" : "center";
  return (
    <div style={{ position: "absolute", left: safe.left, right: safe.right, top: safe.top, textAlign: al }}>
      {kicker ? (
        <div
          style={{
            fontFamily: fonts.sans,
            fontSize: kickerFs,
            fontWeight: 600,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: pal.accent,
            lineHeight: 1.2,
            marginBottom: title ? KICKER_GAP : 0,
            opacity: k,
            translate: `0px ${(1 - k) * 12}px`,
          }}
        >
          {kicker}
        </div>
      ) : null}
      {title
        ? title.split("\n").map((l, i) => (
            <div
              key={i}
              style={{
                fontFamily: fonts.serif,
                fontSize: titleFs,
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                color: pal.fg,
                display: "flex",
                justifyContent: al === "center" ? "center" : "flex-start",
              }}
            >
              <RevealLine text={l} emphasis={emphasis} frame={frame} fps={fps} startFrame={3 + i * 5} emphStyle={{ fontStyle: "italic", color: pal.accent }} />
            </div>
          ))
        : null}
    </div>
  );
};
