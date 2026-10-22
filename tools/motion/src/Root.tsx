import { CalculateMetadataFunction, Composition } from "remotion";
import { Overlay, OverlayProps } from "./Overlay";
import { Story, StoryProps, storyFrames } from "./Story";
import { ASPECTS } from "./layout";
import { defaultBrand } from "./theme";

const calculateMetadata: CalculateMetadataFunction<OverlayProps> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.ceil(props.durationInSeconds * 30)),
  defaultCodec: "prores",
  defaultProResProfile: "4444",
  defaultVideoImageFormat: "png",
  defaultPixelFormat: "yuva444p10le",
});

// Size, fps and length all come from the storyboard props (written by tools/storyboard.py).
const storyMetadata: CalculateMetadataFunction<StoryProps> = ({ props }) => {
  const fps = props.fps ?? 30;
  const { width, height } = ASPECTS[props.aspect] ?? ASPECTS["9:16"];
  return { fps, width, height, durationInFrames: Math.max(1, storyFrames(props.scenes, fps)), defaultCodec: "h264" };
};

const demoStory: StoryProps = {
  aspect: "9:16",
  fps: 30,
  brand: defaultBrand,
  grain: 0.4,
  scenes: [
    { type: "TitleCard", duration: 2.6, bg: "light", props: { kicker: "Chapter one", title: "Made from\nscratch", emphasis: "scratch", sub: "No footage, only motion." } },
    { type: "KineticType", duration: 2.4, bg: "dark", transition: { type: "slide", direction: "from-bottom" }, props: { lines: [{ text: "Every scene" }, { text: "moves on purpose", emphasis: "on purpose" }] } },
    { type: "StatScene", duration: 2.4, bg: "accent", transition: { type: "zoom" }, props: { value: 87, suffix: "%", label: "of viewers decide\nin the first 3 seconds" } },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Overlay"
        component={Overlay}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{ durationInSeconds: 10, brand: defaultBrand, events: [] }}
        calculateMetadata={calculateMetadata}
      />
      <Composition
        id="Story"
        component={Story}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={demoStory}
        calculateMetadata={storyMetadata}
      />
    </>
  );
};
