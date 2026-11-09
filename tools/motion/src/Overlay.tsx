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
import { BackdropContext, Brand, BrandContext, readableKit } from "./theme";
import { Backdrop } from "./components/Backdrop";
import { Captions } from "./components/Captions";
import { CodeEditor } from "./components/CodeEditor";
import { DocumentCard } from "./components/DocumentCard";
import { Drawer } from "./components/Drawer";
import { STAGE } from "./stage";
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
  index?: number; // the event's position in the short-form spec (error messages); not read here
};

export type OverlayProps = {
  durationInSeconds: number;
  brand: Brand;
  events: OverlayEvent[];
  measure?: boolean; // stills only: log each event's visible text (see MeasureText)
  hideText?: boolean; // stills only: draw every glyph transparent, layout unchanged (the legibility probe's blank)
};

// the probe's blank: same layout and pixels, no glyphs (numbers and SVG text included)
export const HIDE_TEXT = `* { color: transparent !important; text-shadow: none !important;
  -webkit-text-stroke-color: transparent !important; } text, tspan { fill: transparent !important;
  stroke: transparent !important; }`;

type Box = [number, number, number, number]; // x0, y0, x1, y1 in composition px

export type MeasuredText = {
  text: string;
  box: Box;
  size: number; // font size × every ancestor's scale, in composition px
  card?: Box; // the nearest ancestor that draws a background, border or image (the event's root excluded)
};

/** An element that draws something: a background colour, an image or a border. */
export type MeasuredShape = { tag: string; box: Box; card?: Box };

const round = (r: DOMRect): Box => [r.left, r.top, r.right, r.bottom].map((v) => Math.round(v)) as Box;

const draws = (cs: CSSStyleDeclaration): boolean => {
  const bg = cs.backgroundColor.match(/[\d.]+/g)?.map(Number) ?? [];
  const solid = bg.length >= 3 && (bg.length < 4 || bg[3] > 0.05);
  const border = ["Top", "Right", "Bottom", "Left"].some(
    (side) =>
      parseFloat(cs.getPropertyValue(`border-${side.toLowerCase()}-width`)) > 0 &&
      cs.getPropertyValue(`border-${side.toLowerCase()}-style`) !== "none" &&
      (cs.getPropertyValue(`border-${side.toLowerCase()}-color`).match(/[\d.]+/g)?.map(Number)[3] ?? 1) > 0.05,
  );
  return solid || cs.backgroundImage !== "none" || border;
};

/** `r` cut to what its ancestors below `root` let show: an `overflow: hidden` (or clip) parent hides the rest, so a
 *  thumbnail scaled up inside its frame is not drawn past it. Null when nothing of it shows. */
const visibleBox = (r: DOMRect, el: Element, root: HTMLElement): Box | null => {
  let [x0, y0, x1, y1] = [r.left, r.top, r.right, r.bottom];
  for (let a = el.parentElement; a && a !== root; a = a.parentElement) {
    const cs = getComputedStyle(a);
    if (cs.overflowX === "visible" && cs.overflowY === "visible") continue;
    const c = a.getBoundingClientRect();
    if (cs.overflowX !== "visible") [x0, x1] = [Math.max(x0, c.left), Math.min(x1, c.right)];
    if (cs.overflowY !== "visible") [y0, y1] = [Math.max(y0, c.top), Math.min(y1, c.bottom)];
  }
  return x1 - x0 < 1 || y1 - y0 < 1 ? null : ([x0, y0, x1, y1].map((v) => Math.round(v)) as Box);
};

/** The box of the card `el` sits on: the nearest element from `from` up (below `root`) that draws a background, border
 *  or image. Text starts at its own element (a pill is its text's card), a shape at its parent. An element marked
 *  `data-overhang` (a stamp across a card's edge, by design) is a card of its own: it is held to the frame only. */
const cardOf = (from: HTMLElement | null, root: HTMLElement): Box | undefined => {
  for (let a = from; a && a !== root; a = a.parentElement) {
    if (draws(getComputedStyle(a))) return round(a.getBoundingClientRect());
  }
  return undefined;
};

/** How visible `el` is: the product of its ancestors' opacity (0 when hidden), and their summed scale. */
const visibility = (el: HTMLElement, root: HTMLElement) => {
  let scale = 1;
  let opacity = 1;
  for (let a: HTMLElement | null = el; a && a !== root.parentElement; a = a.parentElement) {
    const cs = getComputedStyle(a);
    opacity *= parseFloat(cs.opacity);
    if (cs.visibility === "hidden" || cs.display === "none") opacity = 0;
    if (cs.transform && cs.transform !== "none") {
      const m = new DOMMatrixReadOnly(cs.transform);
      scale *= Math.hypot(m.b, m.d);
    }
    if (cs.scale && cs.scale !== "none") scale *= parseFloat(cs.scale.split(" ").pop() ?? "1");
  }
  return { scale, opacity };
};

/** The visible text nodes under `root`: box, rendered size, text and card. Invisible ones (opacity, hidden,
 *  zero size) are skipped: they can't cover a face or be unreadable. */
const measureText = (root: HTMLElement): MeasuredText[] => {
  const out: MeasuredText[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = n.textContent?.trim();
    const el = n.parentElement;
    if (!text || !el) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const { scale, opacity } = visibility(el, root);
    const box = visibleBox(r, el, root);
    if (opacity < 0.05 || !box) continue;
    out.push({
      text,
      box,
      size: Math.round(parseFloat(getComputedStyle(el).fontSize) * scale * 10) / 10,
      card: cardOf(el, root),
    });
  }
  return out;
};

/** Every visible element under `root` that draws a background, border or image, with its card. */
const measureShapes = (root: HTMLElement): MeasuredShape[] => {
  const out: MeasuredShape[] = [];
  root.querySelectorAll<HTMLElement>("*").forEach((el) => {
    if (!draws(getComputedStyle(el))) return;
    const box = visibleBox(el.getBoundingClientRect(), el, root);
    if (!box || visibility(el, root).opacity < 0.05) return;
    const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    const card = el.closest("[data-overhang]") === el ? undefined : cardOf(el.parentElement, root);
    out.push({ tag: el.tagName.toLowerCase() + (cls ? "." + cls : ""), box, card });
  });
  return out;
};

/** Measure mode: once the frame has laid out, logs one line `MEASURE [{event, texts, shapes}]` (each event's
 *  `measureText` and `measureShapes`), which tools/shortform.py reads from the still render's output. */
export const MeasureText: React.FC = () => {
  const [handle] = useState(() => delayRender("Measuring text"));
  useEffect(() => {
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        const roots = Array.from(document.querySelectorAll<HTMLElement>("[data-event]"));
        const out = roots.map((r) => ({ event: Number(r.dataset.event), texts: measureText(r), shapes: measureShapes(r) }));
        console.log("MEASURE " + JSON.stringify(out));
        continueRender(handle);
      }),
    );
  }, [handle]);
  return null;
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
export const OverlayLayer: React.FC<{ events: OverlayEvent[]; measure?: boolean }> = ({ events, measure }) => {
  const { fps, width } = useVideoConfig();
  return (
    <>
      {events.map((ev, i) => {
        const C = REGISTRY[ev.type] ?? SCENES[ev.type] ?? STAGE[ev.type];
        if (!C) throw new Error(`Unknown overlay type: ${ev.type}`);
        const durationInFrames = Math.max(1, Math.round(ev.duration * fps));
        const full = Boolean(ev.props?.full);
        const frameBox = ev.props?.frame as { scale?: number; x?: number; y?: number } | undefined;
        // measure mode: one marked, layout-neutral wrapper per event (the backdrop stays outside it)
        const Wrap: React.FC<{ children: React.ReactNode }> = measure
          ? ({ children }) => <AbsoluteFill data-event={ev.index ?? i}>{children}</AbsoluteFill>
          : ({ children }) => <>{children}</>;
        return (
          <Sequence
            key={i}
            name={ev.name ?? ev.type}
            from={Math.round(ev.start * fps)}
            durationInFrames={durationInFrames}
            premountFor={fps}
          >
            {full ? <Backdrop durationInFrames={durationInFrames} {...(ev.props ?? {})} /> : null}
            <BackdropContext.Provider value={{ full, dark: Boolean(ev.props?.dark) }}>
            <Wrap>
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
            </Wrap>
            </BackdropContext.Provider>
          </Sequence>
        );
      })}
    </>
  );
};

export const Overlay: React.FC<OverlayProps> = ({ brand, events, measure, hideText }) => {
  const ready = useBrandFonts(brand);
  return (
    <BrandContext.Provider value={readableKit(brand)}>
      <AbsoluteFill style={{ fontFamily: brand.fonts.sans }}>
        {hideText ? <style>{HIDE_TEXT}</style> : null}
        {ready ? <OverlayLayer events={events} measure={measure} /> : null}
        {ready && measure ? <MeasureText /> : null}
      </AbsoluteFill>
    </BrandContext.Provider>
  );
};
