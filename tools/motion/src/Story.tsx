import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { TransitionSeries } from "@remotion/transitions";
import { OverlayEvent, OverlayLayer, REGISTRY, useBrandFonts } from "./Overlay";
import { Aspect } from "./layout";
import { Bg, BgKind } from "./scenes/Bg";
import { SCENES } from "./scenes";
import { makeTransition, TransitionSpec, transitionFrames } from "./scenes/transitions";
import { Brand, BrandContext } from "./theme";

/**
 * A video made from scratch: scenes back to back, joined by transitions, with global overlay
 * events (captions, flashes, any component) on top. Written by tools/storyboard.py from
 * `edit/storyboard.json`.
 *
 * Timing: a transition belongs to the scene it leads INTO and overlaps both neighbours, so
 * scene i starts at  start(i-1) + frames(i-1) - transitionFrames(i)  and the total is
 * sum(scene frames) - sum(transition frames). storyboard.py computes the same numbers.
 */
export type StoryScene = {
  type: string;
  duration: number; // s
  bg?: BgKind;
  grain?: number;
  transition?: TransitionSpec;
  props?: Record<string, unknown>;
  name?: string;
};

export type StoryProps = {
  aspect: Aspect;
  fps?: number;
  brand: Brand;
  scenes: StoryScene[];
  events?: OverlayEvent[];
  grain?: number; // default film grain for every scene (0–1)
};

export const sceneFrames = (s: StoryScene, fps: number) => Math.max(1, Math.round(s.duration * fps));

export const storyFrames = (scenes: StoryScene[], fps: number) =>
  scenes.reduce((n, s, i) => n + sceneFrames(s, fps) - (i > 0 ? transitionFrames(s.transition, fps) : 0), 0);

const SceneView: React.FC<{ scene: StoryScene; grain: number; durationInFrames: number }> = ({ scene, grain, durationInFrames }) => {
  const { width, height } = useVideoConfig();
  const C = SCENES[scene.type] ?? REGISTRY[scene.type];
  if (!C) throw new Error(`Unknown scene type: ${scene.type}`);
  if (!SCENES[scene.type] && !(width === 1080 && height === 1920)) {
    // the overlay components are laid out for 1080x1920 only
    throw new Error(`${scene.type} is a 9:16 overlay component; use a scene primitive in ${width}x${height}`);
  }
  const bg = scene.bg ?? (scene.type === "ImageScene" ? "none" : "light");
  return (
    <AbsoluteFill>
      <Bg kind={bg} grain={scene.type === "ImageScene" ? 0 : (scene.grain ?? grain)} />
      <C durationInFrames={durationInFrames} bg={bg} {...(scene.props ?? {})} />
      {scene.type === "ImageScene" && (scene.grain ?? grain) > 0 ? <Bg kind="none" grain={scene.grain ?? grain} /> : null}
    </AbsoluteFill>
  );
};

export const Story: React.FC<StoryProps> = ({ brand, scenes, events = [], grain = 0 }) => {
  const { fps, width, height } = useVideoConfig();
  useBrandFonts(brand);
  return (
    <BrandContext.Provider value={brand}>
      <AbsoluteFill style={{ fontFamily: brand.fonts.sans, background: brand.colors.ink }}>
        <TransitionSeries>
          {scenes.flatMap((s, i) => {
            const d = sceneFrames(s, fps);
            const out: React.ReactNode[] = [];
            if (i > 0 && transitionFrames(s.transition, fps) > 0) {
              const t = makeTransition(s.transition!, fps, width, height);
              out.push(<TransitionSeries.Transition key={`t${i}`} presentation={t.presentation} timing={t.timing} />);
            }
            out.push(
              <TransitionSeries.Sequence key={`s${i}`} durationInFrames={d} name={s.name ?? s.type} premountFor={fps}>
                <SceneView scene={s} grain={grain} durationInFrames={d} />
              </TransitionSeries.Sequence>,
            );
            return out;
          })}
        </TransitionSeries>
        <OverlayLayer events={events} />
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};
