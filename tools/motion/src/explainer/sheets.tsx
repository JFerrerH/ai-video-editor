import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { useBrandFonts } from "../Overlay";
import { Aspect } from "../layout";
import { BeatScene, WidgetSpec } from "../scenes/BeatScene";
import { Brand, BrandContext } from "../theme";
import { Figure } from "./Figure";
import { GridBg, GridTone } from "./GridBg";
import { POSE_NAMES } from "./poses";

export type SheetProps = { brand: Brand; bg?: GridTone };

export const POSE_SHEET = { width: 2000, height: 1100, cols: 5 };

/** Verification sheet: every pose, labelled, each figure in its own cell (with its default prop). */
export const PoseSheet: React.FC<SheetProps> = ({ brand, bg = "light" }) => {
  const ready = useBrandFonts(brand);
  const { width, height, cols } = POSE_SHEET;
  const rows = Math.ceil(POSE_NAMES.length / cols);
  const cw = width / cols;
  const ch = height / rows;
  return (
    <BrandContext.Provider value={brand}>
      <AbsoluteFill style={{ fontFamily: brand.fonts.sans }}>
        <GridBg kind={bg} />
        {ready
          ? POSE_NAMES.map((p, i) => {
              const x = (i % cols) * cw;
              const y = Math.floor(i / cols) * ch;
              return (
                <React.Fragment key={p}>
                  <div style={{ position: "absolute", left: x + 4, top: y + 4, width: cw - 8, height: ch - 8, border: "2px dashed rgba(127,127,127,0.35)", borderRadius: 12 }} />
                  <Figure pose={p} box={{ x: x + 20, y: y + 30, w: cw - 40, h: ch - 100 }} bg={bg} />
                  <div style={{ position: "absolute", left: x, top: y + ch - 62, width: cw, textAlign: "center", fontSize: 34, fontWeight: 700, color: bg === "dark" ? "#F5F4F0" : brand.colors.ink }}>
                    {p}
                  </div>
                </React.Fragment>
              );
            })
          : null}
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};

/** One sample of every widget (settled by 2 s), for the widget sheet; the last segment is empty. */
export const WIDGET_SAMPLES: WidgetSpec[] = [
  { type: "Terminal", title: "deploy", lines: [{ text: "npm run deploy" }, { text: "building 42 pages", kind: "out" }, { text: "live in 9.8s", kind: "ok" }] },
  { type: "Checklist", title: "Launch plan", items: [{ text: "Write the brief" }, { text: "Book the venue", state: "struck", at: 0.4 }, { text: "Ship the page", state: "done", at: 0.5 }, { text: "Tell the team" }] },
  { type: "Stamp", text: "Skip it", at: 0.2 },
  { type: "Counter", label: "lines of code", to: 1200, spark: true },
  { type: "Gauge", value: 72, label: "test coverage" },
  { type: "Stopwatch", seconds: 5400, label: "build time" },
  { type: "FunnelBars", drop: true, rows: [{ label: "Visits", value: 10000 }, { label: "Signups", value: 1800 }, { label: "Paid", value: 240 }] },
  { type: "TileGrid", count: 100, cols: 10, highlight: 12, label: "12 of 100" },
  { type: "Badge", text: "All green", tone: "ok", slot: "side" },
  { type: "ProductCard", name: "Headphones", price: "$240", icon: "cart", pressAt: 0.8 },
  { type: "Calendar", title: "Oct", pages: [{ label: "Today" }, { label: "Tomorrow", at: 0.6 }] },
  { type: "Balance", left: "Head", right: "Heart", leftIcon: "brain", rightIcon: "heart", tilts: [{ to: "right", at: 0.3 }] },
  { type: "ThoughtBubble", icon: "brain", slot: "side" },
];
export const WIDGET_SEG = 60; // frames per sample: still at the segment's last frame

export const WidgetSheet: React.FC<SheetProps & { aspect: Aspect }> = ({ brand, bg = "light" }) => {
  const ready = useBrandFonts(brand);
  const words = ["One", "widget", "per", "beat."].map((text, i) => ({ text, t: 0, emph: i === 1, phrase: 0 }));
  return (
    <BrandContext.Provider value={brand}>
      <AbsoluteFill style={{ fontFamily: brand.fonts.sans }}>
        {ready
          ? [...WIDGET_SAMPLES, null].map((w, i) => (
              <Sequence key={i} from={i * WIDGET_SEG} durationInFrames={WIDGET_SEG}>
                <BeatScene durationInFrames={WIDGET_SEG} bg={bg} words={words} figure={{ pose: "point" }} widgets={w ? [w] : []} />
              </Sequence>
            ))
          : null}
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};
