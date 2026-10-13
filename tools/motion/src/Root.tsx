import { CalculateMetadataFunction, Composition } from "remotion";
import { Overlay, OverlayProps } from "./Overlay";
import { defaultBrand } from "./theme";

const calculateMetadata: CalculateMetadataFunction<OverlayProps> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.ceil(props.durationInSeconds * 30)),
  defaultCodec: "prores",
  defaultProResProfile: "4444",
  defaultVideoImageFormat: "png",
  defaultPixelFormat: "yuva444p10le",
});

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
    </>
  );
};
