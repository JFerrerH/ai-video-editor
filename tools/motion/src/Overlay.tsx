import { loadFont } from "@remotion/fonts";
import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Sequence,
  cancelRender,
  continueRender,
  delayRender,
  staticFile,
  useVideoConfig,
} from "remotion";
import { Brand, BrandContext } from "./theme";
import { Backdrop } from "./components/Backdrop";
import { Captions } from "./components/Captions";
import { CodeEditor } from "./components/CodeEditor";
import { DocumentCard } from "./components/DocumentCard";
import { Drawer } from "./components/Drawer";
import { Flash } from "./components/Flash";
import { HandleCard } from "./components/HandleCard";
import { HookTitle } from "./components/HookTitle";
import { PhoneMockup } from "./components/PhoneMockup";
import { Polaroids } from "./components/Polaroids";
import { ProgressCard } from "./components/ProgressCard";
import { Receipt } from "./components/Receipt";
import { RingStat } from "./components/RingStat";
import { Waitlist } from "./components/Waitlist";
import { IdCard } from "./components/IdCard";
import { BoardingPass } from "./components/BoardingPass";
import { PostPile } from "./components/PostPile";
import { Milestones } from "./components/Milestones";
import { AgeBars } from "./components/AgeBars";
import { AiWorkflow } from "./components/AiWorkflow";
import { SkillSlots } from "./components/SkillSlots";
import { RoomDots } from "./components/RoomDots";
import { ContentGrid } from "./components/ContentGrid";
import { FrameworkCard } from "./components/FrameworkCard";
import { SearchBar } from "./components/SearchBar";
import { ChatThread } from "./components/ChatThread";
import { DotTrack } from "./components/DotTrack";
import { TopicCards } from "./components/TopicCards";
import { NameTitle } from "./components/NameTitle";
import { ProgressBar } from "./explainer/ProgressBar";
import { SCENES } from "./scenes";

/**
 * One transparent layer for the whole edit. Each event:
 *   { type, start, duration, props }   (seconds on the OUTPUT timeline)
 * `full: true` in props draws the brand backdrop under the component (a cutaway).
 * `frame: {scale, x, y}` shrinks/moves the component (origin: top centre) — use it to
 * float a big graphic over the footage, above the head, instead of a full cutaway.
 * Components receive `durationInFrames` so they can animate their own exit.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- props come from storyboard JSON
export const REGISTRY: Record<string, React.FC<any>> = {
  Captions,
  HookTitle,
  PhoneMockup,
  DocumentCard,
  Receipt,
  ProgressCard,
  Drawer,
  RingStat,
  Flash,
  Polaroids,
  CodeEditor,
  Waitlist,
  HandleCard,
  IdCard,
  BoardingPass,
  PostPile,
  Milestones,
  AgeBars,
  AiWorkflow,
  SkillSlots,
  RoomDots,
  ContentGrid,
  FrameworkCard,
  SearchBar,
  ChatThread,
  DotTrack,
  TopicCards,
  NameTitle,
  ProgressBar,
};

export type OverlayEvent = {
  type: keyof typeof REGISTRY | string;
  start: number;
  duration: number;
  props?: Record<string, unknown>;
  name?: string;
};

export type OverlayProps = {
  durationInSeconds: number;
  brand: Brand;
  events: OverlayEvent[];
};

/** Loads the brand's font files; true once they're in. Render text only after that, so anything
 *  measured (headline wrapping) is measured in the real face, not a fallback. */
export const useBrandFonts = (brand: Brand) => {
  const [handle] = useState(() => delayRender("Loading brand fonts"));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    Promise.all(
      brand.fontFiles.map((f) => {
        // props are untyped JSON: a weight can still arrive as a number
        const weight = String(f.weight ?? "400");
        const style = f.style ?? "normal";
        const failed = () =>
          new Error(`Font did not load: ${style} ${weight} "${f.family}" (${f.url.split("/").pop()})`);
        return loadFont({ family: f.family, url: staticFile(f.url), weight, style }).then(
          () => {
            // Fonts fail silently into a fallback face — assert instead.
            const desc = `${style === "italic" ? "italic " : ""}${weight.split(" ")[0]} 40px "${f.family}"`;
            if (!document.fonts.check(desc)) throw failed();
          },
          () => {
            throw failed();
          },
        );
      }),
    )
      .then(() => {
        setReady(true);
        continueRender(handle);
      })
      .catch((e) => cancelRender(e));
  }, [brand, handle]);
  return ready;
};

/** The events on their own (no brand provider, no font loading): shared by `Overlay` and `Story`.
 *  Scene primitives (`SCENES`) work as events too; they draw no background there. */
export const OverlayLayer: React.FC<{ events: OverlayEvent[] }> = ({ events }) => {
  const { fps, width } = useVideoConfig();
  return (
    <>
      {events.map((ev, i) => {
        const C = REGISTRY[ev.type] ?? SCENES[ev.type];
        if (!C) throw new Error(`Unknown overlay type: ${ev.type}`);
        const durationInFrames = Math.max(1, Math.round(ev.duration * fps));
        const full = Boolean(ev.props?.full);
        const frameBox = ev.props?.frame as { scale?: number; x?: number; y?: number } | undefined;
        return (
          <Sequence
            key={i}
            name={ev.name ?? ev.type}
            from={Math.round(ev.start * fps)}
            durationInFrames={durationInFrames}
            premountFor={fps}
          >
            {full ? <Backdrop durationInFrames={durationInFrames} {...(ev.props ?? {})} /> : null}
            {frameBox ? (
              // `frame: {scale, y}` shrinks a full-layout graphic into the band above the
              // speaker's head so it can float over the footage without covering the face
              <AbsoluteFill
                style={{
                  transformOrigin: `${width / 2}px 0px`,
                  scale: String(frameBox.scale ?? 1),
                  translate: `${frameBox.x ?? 0}px ${frameBox.y ?? 0}px`,
                }}
              >
                <C durationInFrames={durationInFrames} {...(ev.props ?? {})} />
              </AbsoluteFill>
            ) : (
              <C durationInFrames={durationInFrames} {...(ev.props ?? {})} />
            )}
          </Sequence>
        );
      })}
    </>
  );
};

export const Overlay: React.FC<OverlayProps> = ({ brand, events }) => {
  const ready = useBrandFonts(brand);
  return (
    <BrandContext.Provider value={brand}>
      <AbsoluteFill style={{ fontFamily: brand.fonts.sans }}>
        {ready ? <OverlayLayer events={events} /> : null}
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};
