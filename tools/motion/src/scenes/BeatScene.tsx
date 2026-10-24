import React from "react";
import { AbsoluteFill } from "remotion";
import { Figure, FigureSpec } from "../explainer/Figure";
import { GridBg, GridTone } from "../explainer/GridBg";
import { HeadWord, Headline } from "../explainer/Headline";
import { slotRects, SlotName } from "../explainer/slots";
import { WIDGETS } from "../explainer/widgets";
import { useFrameLayout } from "../layout";

const CARD_SHADOW = 40; // px under a card that its shadow reaches

export type WidgetSpec = { type: string; slot?: SlotName; at?: number; out?: number } & Record<string, unknown>;

/**
 * One beat of a narrated explainer: grid background → widgets → figure → headline (top layer).
 * Widgets and the figure sit in named slots (`main`, `side`, `figure`) laid out per aspect
 * (explainer/slots.ts). `words` are injected by tools/storyboard.py from the scene's narration clip.
 */
export const BeatScene: React.FC<{
  durationInFrames: number;
  bg?: GridTone;
  grain?: number;
  words?: HeadWord[];
  headline?: boolean;
  headlineSize?: number;
  figure?: FigureSpec | null;
  widgets?: WidgetSpec[];
}> = ({ bg = "light", grain = 0, words = [], headline = true, headlineSize, figure, widgets = [] }) => {
  const { aspect, width, height, safe } = useFrameLayout();
  const mainOnly = !figure && widgets.every((w) => (w.slot ?? "main") === "main");
  const slots = slotRects(aspect, width, height, safe, widgets.some((w) => w.slot === "side"), mainOnly);
  return (
    <AbsoluteFill>
      <GridBg kind={bg} grain={grain} />
      {widgets.map(({ type, slot = "main", ...p }, i) => {
        const W = WIDGETS[type];
        if (!W) throw new Error(`Unknown widget: ${type}`);
        const r = slots[slot] ?? slots.main;
        // keep each card's drop shadow inside the slot too
        return <W key={i} {...p} slot={slot} box={{ ...r, h: r.h - CARD_SHADOW }} bg={bg} />;
      })}
      {figure ? <Figure {...figure} box={slots[(figure.slot as SlotName) ?? "figure"] ?? slots.figure} bg={bg} /> : null}
      {headline && words.length ? <Headline words={words} bg={bg} size={headlineSize} /> : null}
    </AbsoluteFill>
  );
};
