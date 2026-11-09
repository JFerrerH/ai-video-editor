/**
 * The short-form frame, composed in one place (live-stage): the cut base video under a camera, the events on
 * three layers, the speaker's cut-out between `behind` and `front`, and the captions on top.
 *
 *   panel → footage → behind → speaker cut-out → front → captions
 *
 * ffmpeg still cuts and concatenates the footage (`base`) and mixes the audio; this composition draws the
 * frames only. Every time is in output seconds; times inside an event's props are relative to its start.
 */
import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { HIDE_TEXT, MeasureText, OverlayLayer, useBrandFonts, type OverlayEvent } from "../Overlay";
import { BrandContext, readableKit, type Brand } from "../theme";
import { camStyle, camera, type CamMove } from "./camera";

export type Layer = "front" | "behind" | "panel";
export type StageEvent = OverlayEvent & { layer?: Layer };
/** A stretch of the speaker's cut-out (ProRes 4444 with alpha), output seconds. */
export type PersonWindow = { start: number; end: number; src: string };

export type StageProps = {
  durationInSeconds: number;
  brand: Brand;
  base: string; // the cut base video, a file in the public dir
  baseImage?: string; // stills only: one frame of the cut, instead of the video
  persons: PersonWindow[];
  personImage?: string; // stills only: the speaker's cut-out (PNG with alpha) at that frame, instead of `persons`
  camera: CamMove[];
  events: StageEvent[]; // captions last
  measure?: boolean; // stills only: log each event's visible text
  hideText?: boolean; // stills only: draw every glyph transparent (the legibility probe's blank)
};

const layerOf = (e: StageEvent): Layer => e.layer ?? (e.props?.behind ? "behind" : "front");

export const Stage: React.FC<StageProps> = ({ brand, base, baseImage, persons, personImage, camera: moves, events, measure, hideText }) => {
  const ready = useBrandFonts(brand);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cam = camera(moves, frame / fps);
  const c = brand.colors;
  const bg = cam.bg === "ink" ? c.ink : `radial-gradient(120% 80% at 20% 10%, ${c.tint1}, ${c.bg} 55%, ${c.tint2})`;
  const on = (layer: Layer) => events.filter((e) => layerOf(e) === layer);
  return (
    <BrandContext.Provider value={readableKit(brand)}>
      <AbsoluteFill style={{ background: bg, fontFamily: brand.fonts.sans }}>
        {hideText ? <style>{HIDE_TEXT}</style> : null}
        {ready ? <OverlayLayer events={on("panel")} measure={measure} /> : null}
        <AbsoluteFill style={camStyle(cam)}>
          <AbsoluteFill
            style={{
              borderRadius: cam.radius,
              overflow: "hidden",
              boxShadow: cam.shadow
                ? `0 30px 80px rgba(0,0,0,${0.35 * cam.shadow}), 0 0 0 ${(10 * cam.shadow) / cam.scale}px #fff`
                : undefined,
            }}
          >
            {baseImage ? (
              <Img src={staticFile(baseImage)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
              <OffthreadVideo src={staticFile(base)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            )}
          </AbsoluteFill>
        </AbsoluteFill>
        {ready ? <OverlayLayer events={on("behind")} measure={measure} /> : null}
        {persons.map((w, i) => (
          <Sequence key={i} from={Math.round(w.start * fps)} durationInFrames={Math.max(1, Math.round((w.end - w.start) * fps))}>
            <AbsoluteFill style={camStyle(cam)}>
              <OffthreadVideo src={staticFile(w.src)} transparent muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </AbsoluteFill>
          </Sequence>
        ))}
        {personImage ? (
          <AbsoluteFill style={camStyle(cam)}>
            <Img src={staticFile(personImage)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </AbsoluteFill>
        ) : null}
        {ready ? <OverlayLayer events={on("front")} measure={measure} /> : null}
        {ready && measure ? <MeasureText /> : null}
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};

// round, not ceil: the base has a whole number of frames, and 2.267 s × 30 is 68.01
export const stageFrames = (seconds: number, fps = 30) => Math.max(1, Math.round(seconds * fps));
